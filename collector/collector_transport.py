import subprocess
import json
import time
import threading
import math
import select

from utils import *


LOG_PREFIX = "collector_transport"

class TransportCollector:
    def __init__(self, ip):
        with open('config.json', 'r') as file:
            config = json.load(file)

        self.server_ip = config["SERVER_IP"]
        self.tcp_port = config["TCP_PORT"]
        self.interface = ip

        self.ul_throughput = math.nan
    
    def run_iperf_test(self):
        """Run netperf test and continuously parse results."""
        cmd = [
            "netperf",
            "-H", self.server_ip,
            "-L", self.interface,
            "-D", "0.8",
            "-l", "0",
            "-f", "k"
        ]
    
        log(LOG_PREFIX, cmd)

        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        while True:
            try:
                rlist, _, _ = select.select([process.stdout], [], [], 3.0)
                line = ''
                if len(rlist) > 0:
                    line = process.stdout.readline()
                    if line.strip() == "":
                        continue
                    elif "Interim" not in line and "MIGRATED" not in line:
                        self.ul_throughput= 0.0
                        process = subprocess.Popen(
                            cmd, 
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        continue
                else:
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    continue

                if "Interim" in line and "sender" not in line:
                    # print(line)
                    combine_data = line.split(' ')
                    combine_data = [x.strip() for x in combine_data if x != '']
                    self.ul_throughput= float(combine_data[2])

            except Exception as e:
                log(LOG_PREFIX, f"run_iperf_test error: {str(e)}")
                time.sleep(1)

    def start_services(self):
        """Start all background services."""
        threading.Thread(target=self.run_iperf_test).start()

# def main():

#     collector = TransportCollector('192.168.218.128')
#     collector.start_services()
    
#     while True:
#         try:
#             # print(f"Throughput: {collector.ul_throughput:.2f} Kbits/s")
#             # print(f"----------------------------------------------")
            
#             time.sleep(1)
            
#         except KeyboardInterrupt:
#             print("\nMeasurement stopped.")
#             break

# if __name__ == "__main__":
#     main()