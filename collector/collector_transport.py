import subprocess
import json
import time
import threading
import math

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
                line = process.stdout.readline()
                if not line:
                    break

                if "Interim" in line and "sender" not in line:
                    combine_data = line.split(' ')
                    combine_data = [x.strip() for x in combine_data if x != '']
                    self.ul_throughput= float(combine_data[2])

            except Exception as e:
                log(LOG_PREFIX, f"run_iperf_test error: {str(e)}")
    
    def ping_monitor(self):
        """Continuously run ping and update RTT."""
        process = subprocess.Popen(
            ["ping", self.server_ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        while True:
            try:
                line = process.stdout.readline()
                if not line:
                    break
                    
                if "time=" in line:
                    rtt = float(line.split("time=")[1].split(" ms")[0])
                    self.rtt = rtt
                elif "Request timeout" in line:
                    self.rtt = math.nan
                        
            except Exception as e:
                log(LOG_PREFIX, f"Ping monitor error: {str(e)}")

    def start_services(self):
        """Start all background services."""
        threading.Thread(target=self.run_iperf_test).start()
        # threading.Thread(target=self.ping_monitor).start()

# def main():

#     collector = TransportCollector()
#     collector.start_services()
    
#     while True:
#         try:
#             print(f"Uplink Bandwidth: {collector.ul_bandwidth:.2f} Kbits/sec")
#             print(f"Throughput: {collector.ul_throughput:.2f} MBytes")
#             print(f"RTT: {collector.rtt:.2f} ms")
#             print(f"Retry: {collector.retry} times")
#             print(f"CongestionWindow: {collector.cwnd} KBytes")
#             print(f"----------------------------------------------")
            
#             time.sleep(1)
            
#         except KeyboardInterrupt:
#             print("\nMeasurement stopped.")
#             break

# if __name__ == "__main__":
#     main()