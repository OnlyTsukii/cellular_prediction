import os
import time
import json
import subprocess
import serial

from datetime import datetime

# Configuration
BAUDRATE = 115200           
TIMEOUT = 5                 
MAX_RETRIES = 3         
RETRY_INTERVAL = 3       
APN = "cmnet"            
MAX_RETRIES_AT = 5        
SYSTEM_PASSWORD = '123'
LOG_FILE = "/home/ccl/cellular_prediction/log/cellular.log" 

AT_DEVICE = None    
AT_CMD = {
    "AT": "OK",
     f"AT+CGDCONT=1,\"IP\",\"{APN}\"": "OK",
    "AT+QCFG=\"usbnet\",1": "OK",
    "AT+QNETDEVCTL=1,1,1": "OK"
}    


def log(message):
    """Log messages with timestamp to both console and log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry + '\n')

def die(error_message):
    """Handle fatal errors"""
    log(f"Error: {error_message}")
    exit(1)

def send_at_command(ser, command, expected_response="OK", timeout=TIMEOUT):
    try:
        ser.reset_input_buffer()
        
        full_command = command + "\r\n"
        ser.write(full_command.encode('utf-8'))
        log(f"Sent: {command}")
        
        start_time = time.time()
        response = ""
        
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                response += data
                
                if expected_response in response:
                    log(f"Success: {command} -> Received: {expected_response}")
                    return True
            
            time.sleep(0.1)
        
        log(f"Timeout: {command} -> Response: {response.strip()}")
        return False
    
    except Exception as e:
        log(f"Error sending {command}: {str(e)}")
        return (False, str(e))

def check_deps(config):
    """Check for required tools and devices"""
    global AT_DEVICE
    
    required_tools = ['socat', 'udhcpc', 'jq']
    for tool in required_tools:
        if not shutil.which(tool):
            die(f"Missing dependency: {tool}")
    
    try:
        AT_DEVICE = config['CELLULAR_PORT']
        log(f"CONFIGURED DEVICE: {AT_DEVICE}")

        if not os.path.exists(AT_DEVICE):
            AT_DEVICE = None
            die("No valid devices found!")
            
        log(f"FOUND DEVICE: {AT_DEVICE}")
        
    except Exception as e:
        die(f"Failed to read config.json: {str(e)}")

def operate_interfaces(action, config):
    """Bring up or down all cellular interfaces"""
    try:
        if action != 'up' and action != 'down':
            log(f"Wrong interface action: {action}")
            return
        
        prefix = config["INTERFACE_PREFIX"]
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        interfaces = [line.split(':')[1].strip() 
                     for line in result.stdout.split('\n') 
                     if prefix in line and ':' in line]
        
        for interface in interfaces:
            log(f"{action} network interface {interface}")
            result = subprocess.run(
                f'echo {SYSTEM_PASSWORD} | sudo ip link set dev {interface} {action}',
                shell=True,
                stderr=subprocess.PIPE,  
                stdout=subprocess.PIPE, 
                text=True     
            )

            if result.returncode != 0:
                log(f"Error output: {result.stderr.strip()}")
                return False
            
            log(f"Command executed successfully: {action} interface {interface}")

        return True
            
    except Exception as e:
        log(f"Warning: Failed to {action} interfaces: {str(e)}")
        return False

def dial_up(config):
    """Dial-up process for cellular device"""
    log("========= Starting Dial-Up Process =========")

    try:
        ser = serial.Serial(
            port=AT_DEVICE,
            baudrate=BAUDRATE,
            timeout=3,         
            write_timeout=3, 
        )
        log(f"Serial port {AT_DEVICE} opened at {BAUDRATE} baud")
    except Exception as e:
        log(f"Failed to open serial port: {str(e)}")
        return
    
    if not operate_interfaces("down", config):
        die('Down interfaces failed')

    time.sleep(1)

    for cmd, expected in AT_CMD.items():
        success = False
        
        for attempt in range(1, MAX_RETRIES + 1):
            log(f"Attempt {attempt}/{MAX_RETRIES} for command: {cmd}")
            success = send_at_command(ser, cmd, expected)
            if success:
                break
            time.sleep(1)
        
        if not success:
            die(f"Failed after {MAX_RETRIES} attempts for command: {cmd}")

    time.sleep(1)

    if not operate_interfaces("up", config):
        die('Up interfaces failed')

    time.sleep(1)
    
    try:
        prefix = config["INTERFACE_PREFIX"]
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        interfaces = [line.split(':')[1].strip() 
                     for line in result.stdout.split('\n') 
                     if prefix in line and ':' in line]
        
        for interface in interfaces:
            for attempt in range(1, MAX_RETRIES + 1):
                log(f"Attempting to obtain IP on {interface} (Attempt {attempt}/{MAX_RETRIES})")
                try:
                    result = subprocess.run(
                        f'echo {SYSTEM_PASSWORD} | sudo udhcpc -i {interface} -t 5 -n -q',
                        shell=True,
                        stderr=subprocess.PIPE,  
                        stdout=subprocess.PIPE, 
                        text=True     
                    )
                    if result.returncode != 0:
                        log(f"Error output: {result.stderr.strip()}")
                        continue
                    
                    log(f"Command executed successfully: udhcpc ip address for {interface}")
                    break

                except subprocess.CalledProcessError:
                    log(f"Failed to obtain IP address on {interface}")
                    time.sleep(3)
    
    except Exception as e:
        log(f"Error during DHCP process: {str(e)}")
    
    log("=== Dial-Up Process Completed ===")

if __name__ == "__main__":
    import shutil  # Import here to use shutil.which for dependency checking

    with open('config.json') as f:
        config = json.load(f)

    check_deps(config)
    dial_up(config)