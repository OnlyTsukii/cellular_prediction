#!/bin/bash
# Cellular Network Dial-Up Script for Multiple Devices

MAX_RETRIES=12      # Maximum number of retries for interface detection
RETRY_INTERVAL=5    # Retry interval in seconds
AT_DEVICES=("/dev/ttyUSB2" "/dev/ttyUSB3")  # List of AT command device nodes
APN="cmnet"         # Carrier APN name
MAX_RETRIES_AT=5    # Maximum retries for AT commands
LOG_FILE="/var/log/cellular.log" # Log file path

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
  local at_device=$1
  local cmd=$2
  local expect=$3
  local timeout=${4:-5} # Default timeout: 5 seconds
  
  for ((i=1; i<=MAX_RETRIES_AT; i++)); do
    log "Sending AT command to $at_device: $cmd (Attempt $i/$MAX_RETRIES_AT)"
    response=$(timeout $timeout echo -e "${cmd}\r" | socat - $at_device,raw,crnl 2>&1)
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
  for at_device in "${AT_DEVICES[@]}"; do
    [ -c $at_device ] || die "Device not found: $at_device"
  done
}

# Operate on all enx interfaces
operate_interfaces() {
  local action=$1
  for interface in $(ip link show | grep -oP 'enx[0-9a-f]{12}'); do
    log "$action network interface $interface"
    ip link set dev $interface $action 2>>$LOG_FILE || {
      log "Warning: Failed to $action interface $interface"
    }
  done
}

# Dial-up process for all devices
dial_up() {
  log "=== Starting Dial-Up Process ==="

  # Step 1: Bring down all enx interfaces
  operate_interfaces "down"

  # Step 2: Configure modems on all AT devices
  for at_device in "${AT_DEVICES[@]}"; do
    send_at $at_device "AT" "OK" || die "Modem not responding on $at_device"
    send_at $at_device "AT+CGDCONT=1,\"IP\",\"$APN\"" "OK" || die "Failed to configure APN on $at_device"
    send_at $at_device "AT+QCFG=\"usbnet\",1" "OK" || die "Failed to set USB mode on $at_device"
    send_at $at_device "AT+QNETDEVCTL=1,1,1" "OK" || die "Failed to start data connection on $at_device"
  done

  # Step 3: Bring up all enx interfaces
  operate_interfaces "up"

  # Step 4: Obtain IP addresses on all enx interfaces
  for interface in $(ip link show | grep -oP 'enx[0-9a-f]{12}'); do
    for ((i=1; i<=MAX_RETRIES; i++)); do
      log "Attempting to obtain IP on $interface (Attempt $i/$MAX_RETRIES)"
      udhcpc -i $interface -t 5 -n -q 2>>$LOG_FILE && {
        log "Successfully obtained IP address on $interface"
        break
      }
      log "Failed to obtain IP address on $interface"
      sleep 3
    done
  done

  log "=== Dial-Up Process Completed ==="
}

# Entry point
check_deps
dial_up