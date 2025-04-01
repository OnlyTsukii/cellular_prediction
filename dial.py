import os
import time
import json
import subprocess
import serial
import shutil

from datetime import datetime
from utils import log

# Configuration
BAUDRATE = 115200           
TIMEOUT = 5                 
MAX_RETRIES = 3         
RETRY_INTERVAL = 3               
MAX_RETRIES_AT = 5        
SYSTEM_PASSWORD = '123'
LOG_PREFIX = "dial"

AT_DEVICE = None    
AT_CMD = {
    "AT": "OK",
     f"AT+CGDCONT=1,\"IP\"": "OK",
    "AT+QCFG=\"usbnet\",1": "OK",
    "AT+QNETDEVCTL=1,3,1": "OK"
}    

def die(error_message):
    """Handle fatal errors"""
    log(LOG_PREFIX, f"Error: {error_message}")
    exit(1)

def send_at_command(ser, command, expected_response="OK", timeout=TIMEOUT):
    try:
        ser.reset_input_buffer()
        
        full_command = command + "\r\n"
        ser.write(full_command.encode('utf-8'))
        log(LOG_PREFIX, f"Sent: {command}")
        
        start_time = time.time()
        response = ""
        
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                response += data
                
                if expected_response in response:
                    log(LOG_PREFIX, f"Success: {command} -> Received: {expected_response}")
                    return True
            
            time.sleep(0.1)
        
        log(LOG_PREFIX, f"Timeout: {command} -> Response: {response.strip()}")
        return False
    
    except Exception as e:
        log(LOG_PREFIX, f"Error sending {command}: {str(e)}")
        return (False, str(e))

def check_device():
    global AT_DEVICE
    
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        AT_DEVICE = config['CELLULAR_PORT']
        log(LOG_PREFIX, f"CONFIGURED DEVICE: {AT_DEVICE}")

        if not os.path.exists(AT_DEVICE):
            AT_DEVICE = None
            die("No valid devices found!")
            
        log(LOG_PREFIX, f"FOUND DEVICE: {AT_DEVICE}")
        
    except Exception as e:
        die(f"Failed to read config.json: {str(e)}")

def operate_interfaces(action):
    """Bring up or down all enx interfaces"""
    try:
        if action != 'up' and action != 'down':
            log(LOG_PREFIX, f"Wrong interface action: {action}")
            return
        
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        interfaces = [line.split(':')[1].strip() 
                     for line in result.stdout.split('\n') 
                     if 'enx' in line and ':' in line]
        
        for interface in interfaces:
            log(LOG_PREFIX, f"{action} network interface {interface}")
            result = subprocess.run(
                f'echo {SYSTEM_PASSWORD} | sudo ip link set dev {interface} {action}',
                shell=True,
                stderr=subprocess.PIPE,  
                stdout=subprocess.PIPE, 
                text=True     
            )

            if result.returncode != 0:
                log(LOG_PREFIX, f"Error output: {result.stderr.strip()}")
                return False
            
            log(LOG_PREFIX, f"Command executed successfully: {action} interface {interface}")

        return True
            
    except Exception as e:
        log(LOG_PREFIX, f"Warning: Failed to {action} interfaces: {str(e)}")
        return False

def dial_up():
    """Dial-up process for cellular device"""
    log(LOG_PREFIX, "========= Starting Dial-Up Process =========")

    check_device()

    try:
        ser = serial.Serial(
            port=AT_DEVICE,
            baudrate=BAUDRATE,
            timeout=3,         
            write_timeout=3, 
        )
        log(LOG_PREFIX, f"Serial port {AT_DEVICE} opened at {BAUDRATE} baud")
    except Exception as e:
        log(LOG_PREFIX, f"Failed to open serial port: {str(e)}")
        return
    
    if not operate_interfaces("down"):
        die('Down interfaces failed')

    time.sleep(1)

    for cmd, expected in AT_CMD.items():
        success = False
        
        for attempt in range(1, MAX_RETRIES + 1):
            log(LOG_PREFIX, f"Attempt {attempt}/{MAX_RETRIES} for command: {cmd}")
            success = send_at_command(ser, cmd, expected)
            if success:
                break
            time.sleep(1)
        
        if not success:
            die(f"Failed after {MAX_RETRIES} attempts for command: {cmd}")

    time.sleep(1)

    if not operate_interfaces("up"):
        die('Up interfaces failed')

    time.sleep(1)
    
    try:
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        interfaces = [line.split(':')[1].strip() 
                     for line in result.stdout.split('\n') 
                     if 'enx' in line and ':' in line]
        
        for interface in interfaces:
            for attempt in range(1, MAX_RETRIES + 1):
                log(LOG_PREFIX, f"Attempting to obtain IP on {interface} (Attempt {attempt}/{MAX_RETRIES})")
                try:
                    result = subprocess.run(
                        f'echo {SYSTEM_PASSWORD} | sudo udhcpc -i {interface} -t 5 -n -q',
                        shell=True,
                        stderr=subprocess.PIPE,  
                        stdout=subprocess.PIPE, 
                        text=True     
                    )
                    if result.returncode != 0:
                        log(LOG_PREFIX, f"Error output: {result.stderr.strip()}")
                        continue
                    
                    log(LOG_PREFIX, f"Command executed successfully: udhcpc ip address for {interface}")
                    break

                except subprocess.CalledProcessError:
                    log(LOG_PREFIX, f"Failed to obtain IP address on {interface}")
                    time.sleep(3)
    
    except Exception as e:
        log(LOG_PREFIX, f"Error during DHCP process: {str(e)}")
    
    log(LOG_PREFIX, "=== Dial-Up Process Completed ===")