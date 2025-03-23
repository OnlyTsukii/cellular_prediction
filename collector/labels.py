import subprocess
import json
import time
import threading
import math


class LabelsCollector:
    def __init__(self):
        with open('config.json', 'r') as file:
            config = json.load(file)

        self.server_ip = config["SERVER_IP"]
        self.tcp_ul_port = config["TCP_UL_PORT"]
        self.tcp_dl_port = config["TCP_DL_PORT"]
        self.udp_port = config["UDP_PORT"]

        self.ul_bandwidth = math.nan
        self.dl_bandwidth = math.nan
        self.rtt = math.nan
        self.jitter = math.nan
        self.loss = math.nan
    
    def run_iperf_test(self, direction, protocol="tcp"):
        """Run iperf3 test and continuously parse results."""
        cmd = [
            "stdbuf", "-oL",  # Disable output buffering
            "iperf3",
            "-c", self.server_ip,
            "-p", str(self.udp_port if protocol == "udp" else self.tcp_ul_port if direction == 'up' else self.tcp_dl_port),
            "-t", "0",  # Infinite duration
            "-i", "1",
        ]
        
        if protocol == "udp":
            cmd.extend(["-u"])  # UDP mode with bandwidth limit
        
        if direction == "up":
            cmd.append("-R")  # Reverse mode for uplink measurement

        print(cmd)

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

                if "Mbits/sec" in line:
                    if protocol == 'udp':
                        self.jitter = float(line.split('Mbits/sec')[1].split('ms')[0].strip())
                        self.loss = float(line.split('ms')[1].split('(')[1].split('%')[0].strip())
                    else:
                        if direction == "up":
                            self.ul_bandwidth = float(line.split('MBytes')[1].split('Mbits/sec')[0].strip())
                        else:
                            self.dl_bandwidth = float(line.split('MBytes')[1].split('Mbits/sec')[0].strip())
                        
            except Exception as e:
                print(f"Error: {str(e)}")
    
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
                print(f"Ping monitor error: {str(e)}")

    def start_services(self):
        """Start all background services."""
        # Start bandwidth tests
        # threading.Thread(
        #     target=self.run_iperf_test, 
        #     args=("up", "tcp"),
        # ).start()

        # threading.Thread(
        #     target=self.run_iperf_test, 
        #     args=("down", "tcp"),
        # ).start()

        # Start UDP test
        threading.Thread(
            target=self.run_iperf_test, 
            args=("up", "udp"),
        ).start()

        # # Start ping monitor
        threading.Thread(target=self.ping_monitor).start()

def main():

    collector = LabelsCollector()
  
    # Start all background services
    collector.start_services()
    
    # Main loop
    while True:
        try:
            # Print metrics to console
            print(f"Uplink: {collector.ul_bandwidth:.2f} Mbps")
            print(f"Downlink: {collector.dl_bandwidth:.2f} Mbps")
            print(f"RTT: {collector.rtt:.2f} ms")
            print(f"Jitter: {collector.jitter:.2f} ms")
            print(f"Loss: {collector.loss:.2f}%")
            print(f"----------------------------------------------")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nMeasurement stopped.")
            break

if __name__ == "__main__":
    main()