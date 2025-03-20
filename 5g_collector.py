import serial
import datetime
import time
import csv
import math
import os
from collections import defaultdict

SERIAL_PORT = '/dev/ttyUSB2'
BAUD_RATE = 115200
PREFIX = '/home/jetson/data_collector/dataset/5g'

CSV_HEADER = [
    "timestamp", "network_mode", "cell_id",
    "rsrp", "rsrq", "sinr", "avg_neighbor_rsrp",
    "avg_neighbor_rsrq", "avg_neighbor_sinr",
    "echng", "rssi", "band",
]

def parse_servingcell(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+QENG:'):
                continue
        
            line = line.replace('+QENG:', '').strip()

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 12:
                return None
            
            mode = ''
            cell_id = ''
            rsrp = ''
            rsrq = ''
            sinr = ''

            if parts[2] == 'NR5G-SA':
                mode = 'NR5G-SA'
                cell_id = parts[6]
                rsrp = parts[12]
                rsrq = parts[13]
                sinr = parts[14]
            elif parts[2] == 'LTE':
                mode = 'LTE'
                cell_id = parts[6]
                rsrp = parts[13]
                rsrq = parts[14]
                sinr = parts[16]
            elif parts[0] == 'LTE':
                mode = 'LTE'
                cell_id = parts[4]
                rsrp = parts[11]
                rsrq = parts[12]
                sinr = parts[14]
            elif parts[0] == 'NR5G-NSA':
                mode = 'NR5G-NSA'
                cell_id = parts[9]
                rsrp = parts[4]
                rsrq = parts[6]
                sinr = parts[5]
                
            return {
                'network_mode': mode,
                'cell_id': cell_id,
                'rsrp': rsrp,
                'rsrq': rsrq,
                'sinr': sinr,
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

        if len(parts) == 9:
            if parts[4] != '-':
                stats['rsrp'].append(float(parts[4]))
            if parts[5] != '-':
                stats['rsrq'].append(float(parts[5]))
            if parts[6] != '-':
                stats['sinr'].append(float(parts[6]))
        elif len(parts) == 12 and parts[1] == 'LTE':
            if parts[4] != '-':
                stats['rsrp'].append(float(parts[4]))
            if parts[5] != '-':
                stats['rsrq'].append(float(parts[5]))
            if parts[7] != '-':
                stats['sinr'].append(float(parts[7]))

    return {
        'avg_rsrq': int(sum(stats['rsrq'])/len(stats['rsrq'])) if stats['rsrq'] else 'N/A',
        'avg_rsrp': int(sum(stats['rsrp'])/len(stats['rsrp'])) if stats['rsrp'] else 'N/A',
        'avg_sinr': int(sum(stats['sinr'])/len(stats['sinr'])) if stats['sinr'] else 'N/A',
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
                'band': int(parts[2]),
            }
        return None
    except Exception as e:
        print(f"resolve csq failed: {str(e)}")
        return None

def main():
    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        timeout=1
    )
    
    last_cell_id = None

    current_date = datetime.datetime.now().strftime('%Y-%m-%d-%h')
    file_path = os.path.join(PREFIX, f'network_stats_{current_date}.csv')
    csv_file = open(file_path, 'a', newline='')
    writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        writer.writerow(CSV_HEADER)

    count = 0
    
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
            echng = 1 if current_cell_id and (current_cell_id != last_cell_id) else 0
            last_cell_id = current_cell_id

            rssi = csq_data.get('csq_rssi', math.nan) if csq_data else math.nan
            if not math.isnan(rssi):
                rssi = int(rssi)
            else:
                rssi = 'N/A'
            
            writer.writerow([
                ts,
                serving_data.get('network_mode', 'N/A') if serving_data else 'N/A',
                serving_data.get('cell_id', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrp', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrq', 'N/A') if serving_data else 'N/A',
                serving_data.get('sinr', 'N/A') if serving_data else 'N/A', 
                neighbor_data['avg_rsrq'],
                neighbor_data['avg_rsrp'],
                neighbor_data['avg_sinr'],
                echng,
                rssi,
                qnwinfo_data.get('band', 'N/A') if qnwinfo_data else 'N/A'
            ])
            csv_file.flush()
            
            # count += 1
            # if count == 30:
            #     break

            time.sleep(1) 
        
        except KeyboardInterrupt:
            print("\n user interrupted")
        except Exception as e:
            print(f"error: {str(e)}")

if __name__ == "__main__":
    main()