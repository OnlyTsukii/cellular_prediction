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
        self.tcp_port = config["TCP_PORT"]

        self.ul_bandwidth = math.nan
        self.rtt = math.nan
        self.ul_throughput = math.nan
        self.retry = math.nan
        self.cwnd = math.nan
        self.loss_rate = math.nan
    
    def run_iperf_test(self):
        """Run iperf3 test and continuously parse results."""
        cmd = [
            "stdbuf", "-oL",  # Disable output buffering
            "iperf3",
            "-c", self.server_ip,
            "-p", str(self.tcp_port),
            "-t", "0",  # Infinite duration
            "-i", "1",
        ]
    
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

                if "Mbits/sec" in line and "sender" not in line:
                    combine_data = line.split(' ')
                    combine_data = [s for s in combine_data if s != '']
                  
                    self.ul_bandwidth = float(combine_data[6])
                    self.ul_throughput = float(combine_data[4])
                    self.retry = int(float(combine_data[8]))
                    self.cwnd = float(combine_data[9])

                    sent_packets = (self.ul_bandwidth * 1e6) / (8 * 1500)
                    self.loss_rate = f"{(self.retry / sent_packets):.4f}"

            except Exception as e:
                print(f"run_iperf_test error: {str(e)}")
    
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
        threading.Thread(target=self.run_iperf_test).start()
        threading.Thread(target=self.ping_monitor).start()

def main():

    collector = LabelsCollector()
    collector.start_services()
    
    while True:
        try:
            print(f"Uplink Bandwidth: {collector.ul_bandwidth:.2f} Mbits/sec")
            print(f"Throughput: {collector.ul_throughput:.2f} MBytes")
            print(f"RTT: {collector.rtt:.2f} ms")
            print(f"Retry: {collector.retry} times")
            print(f"CongestionWindow: {collector.cwnd} KBytes")
            print(f"----------------------------------------------")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nMeasurement stopped.")
            break

if __name__ == "__main__":
    main()