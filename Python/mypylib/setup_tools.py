"""
Author: Jack Connor 
Date Created: 4/14/2021
Last Modified: 1/27/2023
"""

import time
import sys
import datetime
import serial
import socket
import struct
import minimalmodbus
import numpy as np
from pyModbusTCP.client import ModbusClient
from os import path

def read_daq_config(instrument_name, config_dir = 'C:\\Python\\daq\\config'):
    """
    Reads an instrument configuration file and writes data to a dictionary
    Args:
        read_file (str): path to configuration text file
    Returns:
        config_dic (dict): dictionary containing configuration data
    """
    read_file = f'{config_dir}\\{instrument_name}.txt'
    config_dic = {}
    conditional_read_list = [
            'Instrument Name',
            'Communication Type',
            'Output Directory',
            ]
    with open(read_file) as f:
        for line in f:
            sep = line.find("=")
            object_name = line[0:sep]
            object_value = line[sep+1:line.find("\n")]
            if object_name in conditional_read_list:
                object_value = f'"{object_value}"'
            exec(f'config_dic["{object_name}"] = {object_value}')
    return config_dic

def process_instrument_list(config_path = "C:\\Python\\daq\\config\\"):
    """
    Reads in an instrument list from the configuration file directory and creates 
    a dictionary with instrument names as keys and instrument config file paths as values
    Args:
        config_path (str): path to configuration file directory
    Returns:
        config_file_dic (dict): dictionary of instrument configuration file paths keyed by instrument name
    """
    fname = config_path + "Instrument List.txt"
    config_file_dic = {}
    with open(fname, 'r') as f:
        for line in f:
            if line.find('\n') > 0:
                instrument = line[:-1]
            else:
                instrument = line
            config_file_dic[instrument] = config_path + instrument + '.txt'
    return config_file_dic

def get_timestamp(current_time):
    """
    Uses clock to make a timestamp
    Args:
        None
    Returns:
        dt (str): string containing timestamp
    """
    Y = str(current_time.year)
    m =str(current_time.month)
    d =str(current_time.day)
    H =str(current_time.hour)
    M =str(current_time.minute)
    S =str(current_time.second)
    if current_time.month < 10:
        _m = "0"
    else:
        _m = ""
    if current_time.day < 10:
        _d = "0"
    else:
        _d = ""
    if current_time.hour < 10:
        _H = "0"
    else:
        _H = ""
    if current_time.minute < 10:
        _M = "0"
    else:
        _M = ""
    if current_time.second < 10:
        _S = "0"
    else:
        _S = ""
    dt = Y+"-"+_m+m+"-"+_d+d+" "+_H+H+":"+_M+M+":"+_S+S
    return dt

def serial_init(config):
    """
    Closes [python] serial connection to specified device (if it exists).
    Opens a new serial connection to the device
    Args:
        config (dictionary): dictionary of device parameters
    Returns:
        serial_object (Serial object): serial connection object
    """
    port = config['Connection Information']['Port']
    baud = config['Connection Information']['Baud']
    timeout = config['Connection Information']['Timeout']
    serial.Serial(port, baud, timeout = timeout).close()
    serial_object = serial.Serial(port, baud, timeout = timeout)
    #Set 42C command format
    if config['Instrument Name'] == '42C':
        thermo_ID = config['Connection Information']['Thermo Instrument ID']
        format_command = 'set lrec format 00 01\r'
        hex_command_prefix = hex(thermo_ID + 128)[2:]
        command = bytes.fromhex(hex_command_prefix) + format_command.encode('ascii')
        serial_object.write(command)
        time.sleep(.2)
    #Some instruments send bad data at first
    elif config.get('Startup Purge') != None:
        it = 0
        while it < config['Startup Purge']:
            if not config['Stream']:
                serial_object.write(config['Connection Information']['Command'].encode('ascii'))
            it += 1
            time.sleep(1)
            serial_object.read(serial_object.in_waiting)
        return serial_object
    #Clear instrument buffers
    while serial_object.in_waiting > 0:
        serial_object.read(serial_object.in_waiting)
    return serial_object

def modbus_init(config):
    """
    Establishes modbus objects and connections for serial or TCP/IP Modbus devices
    Args:
        config (dictionary): dictionary of device parameters
    Returns:
        device_dic (dict): if communication type is serial,
            dictionary of minimalmodbus.Instrument modbus connection objects keyed by f'Device {address}'
        modbus_object (ModbusClient): if communication typ is TCP/IP,
            pyModbusTCP connection object
    """
    if config['Communication Type'] == 'Modbus Serial':
        device_dic = {}
        for address in config['Connection Information']['Addresses']:
            device = minimalmodbus.Instrument(
                    config['Connection Information']['Port'],
                    address,
                    config['Connection Information']['Protocol']
                    )
            device.serial.baudrate = config['Connection Information']['Baud']
            device.serial.bytesize = config['Connection Information']['DataLen']
            device.serial.parity = config['Connection Information']['Parity']
            device.serial.stopbits = config['Connection Information']['StopBits']
            device.serial.timeout = config['Connection Information']['Timeout']
            device_dic[f'Device {address}'] = device
        return device_dic
    elif config['Communication Type'] == 'Modbus TCP/IP':
        host = config['Connection Information']['HOST']
        port = config['Connection Information']['PORT']
        modbus_object = ModbusClient(host = host, port = port)
        modbus_object.open()
        return modbus_object

def TCPIP_stream_init(config):
    """
    Initializes a TCP/IP connection for streaming.
    Clears data buffer.
    Args:
        config (dict): instrument configuration dictionary
    Returns:
        socket_object (socket.socket): TCP/IP connection object
    """
    HOST = config['Connection Information']['HOST']
    PORT = config['Connection Information']['PORT']
    socket_object = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_object.connect((HOST, PORT))
    data = socket_object.recv(1024)
    return socket_object

def create_serial_command(config):
    """
     Certain instruments require command prefixes to read recieved commands. This function adds prefixes where necessary

         Thermo instruments need a decimal integer prefix.
         Python conveniently converts decimal integers to hex, then to bytes.

    Args:
        config (dict): instrument configuration dictionary
    Returns:
        command(bytes): command with prefix added if necessary, converted to bytes
    """
    if config['Connection Information'].get('Thermo Instrument ID') is not None:
        thermo_ID = config['Connection Information']['Thermo Instrument ID']
        thermo_command = config['Connection Information']['Command']
        hex_command_prefix = hex(thermo_ID + 128)[2:]
        command = bytes.fromhex(hex_command_prefix) + thermo_command.encode('ascii')
    elif config['Connection Information'].get('Command Prefix') is not None:
        instrument_command = config['Connection Information']['Command']
        command_prefix  = config['Connection Information']['Command Prefix']
        hex_command_prefix = hex(command_prefix)[2:]
        command = bytes.fromhex(hex_command_prefix) + instrument_command.encode('ascii')
    else:
        command = config['Connection Information'].get('Command')
        if command != None:
            command = command.encode('ascii')
    return command

def read_TCPIP_data(config):
    """
    Opens socket. Sends a command if config['Stream'] is False. Reads serial data. 
    Args:
        config (dict): dictionary containing all device connection information
    Returns:
        data_string: data string pulled from device
    """
    HOST = config['Connection Information']['HOST']
    PORT = config['Connection Information']['PORT']
    if not config['Stream']:
        command = config['Connection Information']['Command']
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(command.encode('ascii'))
            if config['Connection Information'].get('Command Delay'):
                time.sleep(config['Connection Information'].get('Command Delay'))
            data_string = s.recv(1024)
        return data_string

def EndOfString_serial_read(serial_object, config):
    """
    Reads serial buffer until end of line character indicated by config.
    Args:
        serial_object (serial.Serial): serial connection object
        config (dict): instrument configuration dictionary
    Returns:
       data_string (str): decoded instrument data line 
    """
    EOS = config['Connection Information']['End of String']
    data_string = ''
    while data_string.find(EOS) < 0:
        time.sleep(0.05)
        data = serial_object.read(serial_object.in_waiting)
        data_string += data.decode('ascii')
    return data_string

def read_serial_stream(serial_object, read_interval):
    """
    Reads serial stream at interval specified and print line and length of line
    Args:
        serial_object (serial.Serial): serial connection object
        read_interval (int): period to read data
    Returns:
        prints dataline and length of line every read interval
    """
    while True:
        data = serial_object.read(serial_object.in_waiting)
        print(f'\nString: {data}')
        print(f'\nString length: {len(data)}')
        time.sleep(read_interval)

def print_serial_command_response_loop(serial_object, t, config):
    """
    Continually writes command to instrument and reads response.
    Args:
        serial_object (serial.Serial): serial connection object
        t (float): sampling period in seconds
    Returns:
        prints dataline when each line is recieved
    """
    cmd = create_serial_command(config)
    while True:
        time.sleep(t - time.time() % t)
        serial_object.write(cmd)
        line = b''
        elapsed_t = 0
        while True:
            if elapsed_t > t:
                print('missed dataline')
                serial_object.close()
                time.sleep(t - time.time() % t)
                serial_object.open()
                serial_object.read(serial_object.in_waiting)
                serial_object.write(cmd)
                line = b''
                elapsed_t = 0
            data = serial_object.read(serial_object.in_waiting)
            if len(data) > 0:
                line = line + data
                if line.find(b'\n') > 0:
                    print(line)
                    line = b''
                    break
            elapsed_t += .1
            time.sleep(.1)

def print_serial_stream(serial_object):
    """
    Reads serial stream and prints data after each complete line is recieved.
    Args:
        serial_object (serial.Serial): serial connection object
    Returns:
        prints dataline when each line is recieved
    """
    line = b''
    while True:
        data = serial_object.read(serial_object.in_waiting)
        if len(data) > 0:
            line = line + data
            if line.find(b'\n') > 0:
                print(line)
                line = b''
        time.sleep(.1)

def write_serial_stream(serial_object, writeFile):
    """
    Reads serial stream and writes data after each complete line is recieved.
    Args:
        serial_object (serial.Serial): serial connection object
        writeFile (str): filename to write data to
    Returns:
        prints dataline when each line is recieved
    """
    data = serial_object.read(serial_object.in_waiting)
    while len(data) > 0:
        data = serial_object.read(serial_object.in_waiting)
    line = b''
    while True:
        data = serial_object.read(serial_object.in_waiting)
        if len(data) > 0:
            line = line + data
            if line.find(b'\n') > 0:
                cr_index = line.find(b'\r')
                nw_index = line.find(b'\n')
                if cr_index > 0:
                    cut_index = min(cr_index, nw_index)
                else:
                    cut_index = nw_index
                write_line = line[:cut_index].decode('ascii')
                print(write_line)
                with open(writeFile, 'a') as f:
                    f.write(write_line + '\n')
                line = b''
        time.sleep(.01)

def write_arduino_stream(serial_object, writeFile):
    """
    Reads serial stream and writes data after each complete line is recieved.
    Sends Arduino a command first to initialize stream.
    Args:
        serial_object (serial.Serial): serial connection object
        writeFile (str): filename to write data to
    Returns:
        prints dataline when each line is recieved
    """
    serial_object.write('0'.encode('ascii'))
    line = b''
    while True:
        data = serial_object.read(serial_object.in_waiting)
        if len(data) > 0:
            line = line + data
            if line.find(b'\n') > 0:
                cr_index = line.find(b'\r')
                nw_index = line.find(b'\n')
                if cr_index > 0:
                    cut_index = min(cr_index, nw_index)
                else:
                    cut_index = nw_index
                write_line = line[:cut_index].decode('ascii')
                print(write_line)
                with open(writeFile, 'a') as f:
                    f.write(write_line + '\n')
                line = b''
        time.sleep(.01)

def read_TCPIP_stream(socket_object, read_interval):
    """
    Reads TCP/IP stream at interval specified and prints line and length of line
    Args:
        socket_object (socket.socket): socket connection object
        read_interval (int): period to read data
    Returns:
        prints dataline and length of line every read interval
    """
    while True:
        data = socket_object.recv(1024)
        print(f'\nString: {data}')
        print(f'\nString length: {len(data)}')
        time.sleep(read_interval)

def parse_data_line(line, delimiter):
    """
    Parses dataline into dictionary of data elements keyed by index.
    Args:
        line (str): last recorded dataline for instrument
        delimiter (str): delimiter used to parse line, from config
    Returns:
        data_dic (dict): dictionary of data elements keyed by index
    """
    data_list = []
    delimiter_index = line.find(delimiter)
    while delimiter_index  >= 0:
        data_list += [line[:delimiter_index]]
        line = line[delimiter_index+1:]
        delimiter_index = line.find(delimiter)
    data_list += [line]
    data_dic = {}
    i = 0
    for element in data_list:
       data_dic[i] = element
       i += 1
    return data_dic
