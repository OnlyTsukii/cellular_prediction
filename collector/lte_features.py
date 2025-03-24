import serial
import datetime
import time
import csv
import math
import os
import json

from collections import defaultdict
from labels import LabelsCollector

BAUD_RATE = 115200
PREFIX = '/home/ccl/cellular_prediction/dataset/lte'

CSV_HEADER = [
    "timestamp", "network_mode", "state", "duplex_mode", 
    "cell_id", "rsrp", "rsrq", "sinr", "max_neighbor_rsrp",
    "max_neighbor_rsrq", "max_neighbor_sinr", "avg_neighbor_rsrp",
    "avg_neighbor_rsrq", "avg_neighbor_sinr", "bandwidth",
    "cell_changed", "rssi", "band", "ul_bandwidth", 
    "ul_throughput", "rtt", "retry", "cwnd", "loss_rate"
]

def parse_servingcell(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+QENG:'):
                continue
        
            line = line.replace('+QENG:', '').strip()

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 18 or parts[2] != '"LTE"':
                return None
                
            return {
                'network_mode': 'LTE',
                "state": parts[1][1:-1],
                "duplex_mode": parts[3][1:-1],
                'cell_id': parts[6],
                'rsrp': parts[13],
                'rsrq': parts[14],
                'sinr': parts[16],
                "bandwidth": parts[11],
                
            }
        
        return None
    except Exception as e:
        print(f"resolve serving cell failed: {str(e)}")
        return None

def parse_neighborcell(response):
    stats = defaultdict(list)
    
    for line in response.split('\n'):
        if not line.startswith('+QENG:'):
            continue
        
        line = line.replace('+QENG:', '').strip()
            
        parts = [p.strip() for p in line.split(',')]
        
        if len(parts) >= 12 and parts[1] == '"LTE"':
            if parts[4] != '-':
                stats['rsrq'].append(float(parts[4]))

            if parts[5] != '-':
                stats['rsrp'].append(float(parts[5]))

            if parts[7] != '-':
                stats['sinr'].append(float(parts[7]))

    
    return {
        'max_rsrq': int(max(stats['rsrq'])) if stats['rsrq'] else 0,
        'max_rsrp': int(max(stats['rsrp'])) if stats['rsrp'] else 0,
        'max_sinr': int(max(stats['sinr'])) if stats['sinr'] else 0,
        'avg_rsrq': int(sum(stats['rsrq'])/len(stats['rsrq'])) if stats['rsrq'] else 0,
        'avg_rsrp': int(sum(stats['rsrp'])/len(stats['rsrp'])) if stats['rsrp'] else 0,
        'avg_sinr': int(sum(stats['sinr'])/len(stats['sinr'])) if stats['sinr'] else 0,
    }

def parse_csq(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+CSQ:'):
                continue
            
            line = line.replace('+CSQ:', '').strip()
                
            parts = [p.strip() for p in line.split(',')]

            if len(parts) < 2:
                return None
            
            return {
                'csq_rssi': int(parts[0]),
            }
        return None
    except Exception as e:
        print(f"resolve csq failed: {str(e)}")
        return None
    
def parse_qnwinfo(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+QNWINFO:'):
                continue
            
            line = line.replace('+QNWINFO:', '').strip()
                
            parts = [p.strip() for p in line.split(',')]

            if len(parts) < 4:
                return None
            
            return {
                'band': parts[2][1:-1],
            }
        return None
    except Exception as e:
        print(f"resolve csq failed: {str(e)}")
        return None

def main():
    with open('config.json', 'r') as file:
        config = json.load(file)

    serial_port = config['Serial_LTE']
    
    ser = serial.Serial(
        port=serial_port,
        baudrate=BAUD_RATE,
        timeout=1
    )

    collector = LabelsCollector()
    collector.start_services()
    
    last_cell_id = None

    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    file_path = os.path.join(PREFIX, f'network_stats_{current_date}.csv')
    csv_file = open(file_path, 'a', newline='')
    writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        writer.writerow(CSV_HEADER)
    
    while True:
        try:
            ts = time.time()
            
            ser.write(b'AT+QENG="servingcell"\r\n')
            serving_response = ser.read_until(b'OK').decode()
            serving_data = parse_servingcell(serving_response)
            
            ser.write(b'AT+QENG="neighbourcell"\r\n')
            neighbor_response = ser.read_until(b'OK').decode()
            neighbor_data = parse_neighborcell(neighbor_response)

            ser.write(b'AT+CSQ\r\n')
            csq_response = ser.read_until(b'OK').decode()
            csq_data = parse_csq(csq_response)

            ser.write(b'AT+QNWINFO\r\n')
            qnwinfo_response = ser.read_until(b'OK').decode()
            qnwinfo_data = parse_qnwinfo(qnwinfo_response)
            
            current_cell_id = serving_data['cell_id'] if serving_data else None
            cell_changed = 1 if current_cell_id and (current_cell_id != last_cell_id) else 0
            last_cell_id = current_cell_id

            rssi = csq_data.get('csq_rssi', math.nan) if csq_data else math.nan
            if not math.isnan(rssi):
                rssi = int(rssi)
            else:
                rssi = 99

            ul_bandwidth = collector.ul_bandwidth
            ul_throughput = collector.ul_throughput
            rtt = collector.rtt
            retry = collector.retry
            cwnd = collector.cwnd
            loss_rate = collector.loss_rate
            
            writer.writerow([
                ts,
                serving_data.get('network_mode', 'N/A') if serving_data else 'N/A',
                serving_data.get('state', 'N/A') if serving_data else 'N/A',
                serving_data.get('duplex_mode', 'N/A') if serving_data else 'N/A',
                serving_data.get('cell_id', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrp', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrq', 'N/A') if serving_data else 'N/A',
                serving_data.get('sinr', 'N/A') if serving_data else 'N/A', 
                neighbor_data['max_rsrp'],
                neighbor_data['max_rsrq'],
                neighbor_data['max_sinr'],
                neighbor_data['avg_rsrp'],
                neighbor_data['avg_rsrq'],
                neighbor_data['avg_sinr'],
                serving_data.get('bandwidth', 'N/A') if serving_data else 'N/A',
                cell_changed,
                rssi,
                qnwinfo_data.get('band', 'N/A') if qnwinfo_data else 'N/A',
                ul_bandwidth,
                ul_throughput,
                rtt,
                retry,
                cwnd,
                loss_rate
            ])
            csv_file.flush()

            time.sleep(1) 
        
        except KeyboardInterrupt:
            print("\n user interrupted")
            break
        except Exception as e:
            print(f"error: {str(e)}")

if __name__ == "__main__":
    main()