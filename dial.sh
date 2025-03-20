#!/bin/bash
# Cellular Network Dial-Up Script - Supports Retries and Error Handling


MAX_RETRIES=12      # Maximum number of retries
RETRY_INTERVAL=5    # Retry interval in seconds
INTERFACE=""
AT_DEVICE="/dev/ttyUSB2"       # AT command device node
APN="cmnet"                   # Carrier APN name
MAX_RETRIES=5                 # Maximum retries for critical steps
LOG_FILE="/var/log/cellular.log" # Log file path

# Function to detect the cellular interface
detect_interface() {
  for ((i=1; i<=MAX_RETRIES; i++)); do
    INTERFACE=$(ip link show | grep -oP 'enx[0-9a-f]{12}' | head -n 1)
    
    if [ -n "$INTERFACE" ]; then
      echo "Detected cellular interface: $INTERFACE"
      return 0  # Success
    fi

    echo "Cellular interface not found! (Attempt $i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
  done

  echo "Error: Cellular interface not found after $MAX_RETRIES attempts!"
  return 1  # Failure
}

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# Error handling function
die() {
  log "Error: $1"
  exit 1
}

# Send AT command and check response
send_at() {
  local cmd=$1
  local expect=$2
  local timeout=${3:-5} # Default timeout: 5 seconds
  
  for ((i=1; i<=MAX_RETRIES; i++)); do
    log "Sending AT command: $cmd (Attempt $i/$MAX_RETRIES)"
    response=$(timeout $timeout echo -e "${cmd}\r" | socat - $AT_DEVICE,raw,crnl 2>&1)
    echo "$response" | grep -q "$expect" && {
      log "AT command succeeded: $cmd"
      return 0
    }
    log "Did not receive expected response: $expect"
    sleep 2
  done
  return 1
}

# Check for required tools
check_deps() {
  command -v socat >/dev/null || die "Missing dependency: socat"
  command -v udhcpc >/dev/null || die "Missing dependency: udhcpc"
  [ -c $AT_DEVICE ] || die "Device not found: $AT_DEVICE"
}

# Main process
main() {
  log "=== Starting Cellular Network Dial-Up ==="

  # Main logic
  if detect_interface; then
    # If interface is found, continue with the rest of the script
    echo "Using interface: $INTERFACE"
  else
    echo "No cellular interface detected."
    exit 1
  fi
  
  # Step 1: Bring down the interface
  log "Bringing down network interface $INTERFACE"
  ip link set dev $INTERFACE down 2>>$LOG_FILE || {
    log "Warning: Failed to bring down interface, may already be down"
  }

  # Step 2: Configure modem
  send_at "AT" "OK" || die "Modem not responding"
  send_at "AT+CGDCONT=1,\"IP\",\"$APN\"" "OK" || die "Failed to configure APN"
  send_at "AT+QCFG=\"usbnet\",1" "OK" || die "Failed to set USB mode"
  send_at "AT+QNETDEVCTL=1,1,1" "OK" || die "Failed to start data connection"

  # Step 3: Bring up the interface
  log "Bringing up network interface $INTERFACE"
  ip link set dev $INTERFACE up 2>>$LOG_FILE || die "Failed to bring up interface"

  # Step 4: Obtain IP address
  for ((i=1; i<=MAX_RETRIES; i++)); do
    log "Attempting to obtain IP (Attempt $i/$MAX_RETRIES)"
    udhcpc -i $INTERFACE -t 5 -n -q 2>>$LOG_FILE && {
      log "Successfully obtained IP address"
      return 0
    }
    sleep 3
  done
  
  die "Failed to obtain IP address"
}

# Entry point
check_deps
main
log "=== Dial-Up Process Completed ==="