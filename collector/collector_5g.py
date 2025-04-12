import serial
import datetime
import time
import csv
import math
import os
import json

from collections import defaultdict
from collector.collector_transport import TransportCollector
from utils import *


LOG_PREFIX = "collector_5g"
AT_QENG_SERVING = 0
AT_QENG_NEIGHBOUR = 1
AT_QCAINFO = 2
AT_QNWINFO = 3
AT_QNWCFG = 4

BAUD_RATE = 115200
PREFIX = '/home/ccl/cellular_prediction/dataset/5g'

CSV_HEADER = [
    "timestamp", "network_mode", "operator", "state", "duplex_mode", 
    "cell_id", "rsrp", "rsrq", "sinr", "tx_power", "srxlev", "channel_id",
    "max_neighbor_rsrp", "max_neighbor_rsrq", "max_neighbor_sinr", 
    "avg_neighbor_rsrp", "avg_neighbor_rsrq", "avg_neighbor_sinr", 
    "bandwidth", "cell_changed", "rssi", "band", "mcs", "ul_throughput"
]

def parse_servingcell(response):
    try:
        last_state = ''
        for line in response.split('\n'):
            if not line.startswith('+QENG:'):
                continue
        
            line = line.replace('+QENG:', '').strip()

            parts = [p.strip() for p in line.split(',')]

            net_mode = ''
            state = ''
            duplex_mode = ''
            cell_id = ''
            rsrp = ''
            rsrq = ''
            sinr = ''
            bandwidth = ''
            tx_power = ''
            srxlev = ''

            if len(parts) == 2:
                last_state = parts[1]
                continue

            if len(parts) < 12:
                return None

            if parts[2] == '"NR5G-SA"':
                net_mode = 'NR5G-SA'
                state = parts[1]
                duplex_mode = parts[3]
                cell_id = parts[6]
                rsrp = parts[12]
                rsrq = parts[13]
                sinr = parts[14]
                bandwidth = parts[11]
                tx_power = parts[15]
                srxlev = parts[16]
            elif parts[2] == '"LTE"':
                net_mode = 'LTE'
                state = parts[1]
                duplex_mode = parts[3]
                cell_id = parts[6]
                rsrp = parts[13]
                rsrq = parts[14]
                sinr = parts[16]
                bandwidth = parts[11]
                tx_power = parts[18]
                srxlev = parts[19]
            elif parts[0] == '"LTE"':
                net_mode = 'EN-DC'
                state = last_state
                duplex_mode = parts[1]
                cell_id = parts[4]
                rsrp = parts[11]
                rsrq = parts[12]
                sinr = parts[14]
                bandwidth = parts[9]
                tx_power = parts[16]
                srxlev = parts[17]
                last_state = ''
                
            return {
                'network_mode': net_mode,
                'state': state[1:-1],
                'duplex_mode': duplex_mode[1:-1],
                'cell_id': cell_id,
                'rsrp': rsrp,
                'rsrq': rsrq,
                'sinr': sinr,
                'bandwidth': bandwidth,
                'tx_power': tx_power,
                'srxlev': srxlev,
            }
        
        return None
    except Exception as e:
        log(LOG_PREFIX, f"resolve serving cell failed: {str(e)}")
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
                stats['rsrp'].append(float(parts[4]))
            if parts[5] != '-':
                stats['rsrq'].append(float(parts[5]))
            if parts[7] != '-':
                stats['sinr'].append(float(parts[7]))
        elif len(parts) >= 9:
            if parts[4] != '-':
                stats['rsrp'].append(float(parts[4]))
            if parts[5] != '-':
                stats['rsrq'].append(float(parts[5]))
            if parts[6] != '-':
                stats['sinr'].append(float(parts[6]))

    return {
        'max_rsrq': int(max(stats['rsrq'])) if stats['rsrq'] else 0,
        'max_rsrp': int(max(stats['rsrp'])) if stats['rsrp'] else 0,
        'max_sinr': int(max(stats['sinr'])) if stats['sinr'] else 0,
        'avg_rsrq': int(sum(stats['rsrq'])/len(stats['rsrq'])) if stats['rsrq'] else 0,
        'avg_rsrp': int(sum(stats['rsrp'])/len(stats['rsrp'])) if stats['rsrp'] else 0,
        'avg_sinr': int(sum(stats['sinr'])/len(stats['sinr'])) if stats['sinr'] else 0,
    }

def parse_qcainfo(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+QCAINFO:'):
                continue
            
            line = line.replace('+QCAINFO:', '').strip()
                
            parts = [p.strip() for p in line.split(',')]

            if len(parts) < 10:
                return None
            
            if parts[0] == '"PCC"':
                return {
                    'rssi': int(parts[8]),
                }

        return None
    except Exception as e:
        log(LOG_PREFIX, f"resolve qcainfo failed: {str(e)}")
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
                'operator': parts[1],
                'band': parts[2][1:-1],
                'channel_id': parts[3],
            }
        return None
    except Exception as e:
        log(LOG_PREFIX, f"resolve qnwinfo failed: {str(e)}")
        return None
    
def parse_qnwcfg(response):
    try:
        for line in response.split('\n'):
            if not line.startswith('+QNWCFG:'):
                continue
            
            line = line.replace('+QNWCFG:', '').strip()
                
            parts = [p.strip() for p in line.split(',')]

            if len(parts) < 4:
                return None
            
            return {
                'mcs': parts[2],
            }
        return None
    except Exception as e:
        log(LOG_PREFIX, f"resolve qnwcfg failed: {str(e)}")
        return None
    
def send_at_command(serial, type, cmd, expected):
    serial.write(cmd.encode('utf-8') + b'\r\n')
    response = serial.read_until(expected.encode('utf-8')).decode()
    if type == AT_QENG_SERVING:
        return parse_servingcell(response)
    elif type == AT_QENG_NEIGHBOUR:
        return parse_neighborcell(response)
    elif type == AT_QCAINFO:
        return parse_qcainfo(response)
    elif type == AT_QNWINFO:
        return parse_qnwinfo(response)
    elif type == AT_QNWCFG:
        return parse_qnwcfg(response)

def start_5g(lines, serial_port, ip):
    
    ser = serial.Serial(
        port=serial_port,
        baudrate=BAUD_RATE,
        timeout=1
    )

    collector = TransportCollector(ip)
    collector.start_services()
    
    last_cell_id = None

    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    file_path = os.path.join(PREFIX, f'network_stats_{current_time}.csv')
    csv_file = open(file_path, 'a', newline='')
    writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        writer.writerow(CSV_HEADER)
    
    while lines > 0:
        try:
            ts = time.time()
            
            serving_data = send_at_command(ser, AT_QENG_SERVING, 'AT+QENG="servingcell"', 'OK')
            neighbor_data = send_at_command(ser, AT_QENG_NEIGHBOUR, 'AT+QENG="neighbourcell"', 'OK')
            cainfo_data = send_at_command(ser, AT_QCAINFO, 'AT+QCAINFO', 'OK')
            qnwinfo_data = send_at_command(ser, AT_QNWINFO, 'AT+QNWINFO', 'OK')
            
            current_cell_id = serving_data['cell_id'] if serving_data else None
            cell_changed = 1 if current_cell_id and (current_cell_id != last_cell_id) else 0
            last_cell_id = current_cell_id

            rssi = cainfo_data.get('rssi', 'N/A') if cainfo_data else 'N/A'

            ul_throughput = collector.ul_throughput

            net_mode = serving_data.get('network_mode', 'N/A') if serving_data else 'N/A'
            cfg_data = None
            if net_mode == 'NR5G-SA':
                cfg_data = send_at_command(ser, AT_QNWCFG, 'AT+QNWCFG="nr5g_ulMCS"', 'OK')
            elif net_mode != 'N/A':
                cfg_data = send_at_command(ser, AT_QNWCFG, 'AT+QNWCFG="lte_ulMCS"', 'OK')
            
            writer.writerow([
                ts,
                net_mode,
                qnwinfo_data.get('operator', 'N/A') if qnwinfo_data else 'N/A',
                serving_data.get('state', 'N/A') if serving_data else 'N/A',
                serving_data.get('duplex_mode', 'N/A') if serving_data else 'N/A',
                serving_data.get('cell_id', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrp', 'N/A') if serving_data else 'N/A',
                serving_data.get('rsrq', 'N/A') if serving_data else 'N/A',
                serving_data.get('sinr', 'N/A') if serving_data else 'N/A', 
                serving_data.get('tx_power', 'N/A') if serving_data else 'N/A', 
                serving_data.get('srxlev', 'N/A') if serving_data else 'N/A', 
                qnwinfo_data.get('channel_id', 'N/A') if qnwinfo_data else 'N/A',
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
                cfg_data.get('mcs', 'N/A') if qnwinfo_data else 'N/A',
                ul_throughput,
            ])
            csv_file.flush()

            lines -= 1

            time.sleep(1) 
        
        except KeyboardInterrupt:
            log(LOG_PREFIX, "user interrupted")
            break
        except Exception as e:
            log(LOG_PREFIX, f"error: {str(e)}")