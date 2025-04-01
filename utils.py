import os
import time

from datetime import datetime

LOG_DIR = "/home/ccl/cellular_prediction/log/"
LOG_FILE = ""

def init_log():
    global LOG_FILE

    LOG_FILE = os.path.join(LOG_DIR, f"cellular_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
    os.makedirs(LOG_DIR, exist_ok=True)

def log(prefix, message):
    if LOG_FILE == "":
        init_log()
    
    log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][{prefix}] {message}"
    print(log_entry)
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry + '\n')

