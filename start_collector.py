import netifaces
import shutil
import json

from collector.collector_5g import start_5g
from dial import dial_up
from utils import *


LOG_PREFIX = "start_collector"

def check_deps():
    """Check for required tools"""
    required_tools = ['netperf']
    for tool in required_tools:
        if not shutil.which(tool):
            log(LOG_PREFIX, f"Missing dependency: {tool}")
    
def get_interface_ipv4(prefix):
    interfaces = netifaces.interfaces()
    enx_interfaces = [iface for iface in interfaces if iface.startswith(prefix)]
    
    if not enx_interfaces:
        log(LOG_PREFIX, f"No {prefix} interface found")
        return None

    for iface in enx_interfaces:
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            ip = addrs[netifaces.AF_INET][0]['addr']
            log(LOG_PREFIX, f"Interface: {iface}, IPv4: {ip}")
            return ip

    log(LOG_PREFIX, f"No IPv4 address assigned to {prefix} interface, waiting...")
    return None

def main():
    init_log()

    with open('config.json') as f:
        config = json.load(f)

    intf_prefix = config['INTERFACE_PREFIX']
    cellular_port = config['CELLULAR_PORT']

    ip = get_interface_ipv4(intf_prefix)
    if not ip:
        cnt = 60
        while cnt > 0:
            time.sleep(1)
            ip = get_interface_ipv4(intf_prefix)
            if ip:
                break
            cnt -= 1
        pass
    
    if not ip:
        log(LOG_PREFIX, f"No IPv4 address assigned to {intf_prefix} interface after 60 tries, exited.")

    start_5g(1024, cellular_port, ip)

if __name__ == "__main__":
    main()