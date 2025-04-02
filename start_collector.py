import netifaces
import shutil

from collector.collector_5g import start_5g
from dial import dial_up
from utils import *


LOG_PREFIX = "start_collector"

def check_deps():
    """Check for required tools"""
    required_tools = ['socat', 'udhcpc', 'jq']
    for tool in required_tools:
        if not shutil.which(tool):
            log(LOG_PREFIX, f"Missing dependency: {tool}")
    
def get_enx_ipv4():
    interfaces = netifaces.interfaces()
    enx_interfaces = [iface for iface in interfaces if iface.startswith('enx')]
    
    if not enx_interfaces:
        log(LOG_PREFIX, "No enx interface found")
        return None

    for iface in enx_interfaces:
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            ip = addrs[netifaces.AF_INET][0]['addr']
            log(LOG_PREFIX, f"Interface: {iface}, IPv4: {ip}")
            return ip

    log(LOG_PREFIX, "No IPv4 address assigned to enx interface")
    return None

def main():
    init_log()

    ip = get_enx_ipv4()
    if not ip:
        dial_up()
        time.sleep(1)
        ip = get_enx_ipv4()
    
    start_5g(ip, 1024)

if __name__ == "__main__":
    main()