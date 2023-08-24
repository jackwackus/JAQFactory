"""
Author: Jack Connor 
Date Created: 4/14/2021
Last Modified: 8/23/2023
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

def read_daq_config(instrument, config_dir = 'C:\\JAQFactory\\daq\\config'):
    """
    Reads an instrument configuration file and writes data to a dictionary
    Args:
        instrument (str): instrument name
        config_dir (str): path to configuration file directory
    Returns:
        config_dic (dict): dictionary containing configuration data
    """
    if not path.exists(config_dir):
        message = '\n'.join([
            'Config file directory:',
            f'{config_dir}',
            'does not exist.',
            'Specify the proper config file directory as the second argument of this function.'
            ])
        print(message)
        return
    read_file = f'{config_dir}\\{instrument}.txt'
    config_dic = {}
    conditional_read_list = [
            'Instrument Name',
            'Communication Type',
            'Output Directory',
            ]
    with open(read_file) as f:
        for line in f:
            if line.find('\n') > 0:
                line = line[:-1]
            sep = line.find("=")
            object_name = line[0:sep]
            if len(object_name) < 1:
                continue
            object_value = line[sep+1:]
            if object_name in conditional_read_list:
                object_value = f'"{object_value}"'
            exec(f'config_dic["{object_name}"] = {object_value}')
    return config_dic

def process_instrument_list(config_path = "C:\\JAQFactory\\daq\\config\\"):
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

def read_ModbusSerial_registers(device_dict, config):
    """
    Reads modbus registers over serial and compiles a data string.
    Args:
        device_dict (dict): dictionary of minimalmodbus.Instrument objects
        config (dict): instrument configuration dictionary
    Returns:
        data_string (str): data string consisting of register values 
            separated by delimiter specified in config
    """
    #NOTE: These processes will have to be elaborated when new register types are encountered.
    data_string = ""
    n_parameter = 0
    for device in device_dict:
        for register in config['Integer Register Dictionary']: 
            factor = config['Integer Register Dictionary'][register]
            val = device_dict[device].read_register(register, factor)
            if n_parameter == 0:
                data_string += str(val)
                n_parameter += 1
            else:
                data_string += config['Delimiter'] + str(val)
    return data_string

def read_ModbusIEEE(modbusTCP_object, start_register, float_register_type, LoSigFirst = True):
    """
    Adapted from https://stackoverflow.com/questions/59883083/convert-two-raw-values-to-32-bit-ieee-floating-point-number
    Reads modbus data encoded with IEEE 754 (Institute of Electrical and Electronics Engineers Standard for Floating Point Arithmetic).
    Reads 32 bits from two 16 bit registers and converts data to a floating point number.
    Args:
        modbusTCP_object (ModbusClient): modbus TCP/IP communication object
        start_register (int): register address to begin reading from
        float_register_type (str): register type - Input or Holding
        LoSigFirst (bool): boolean indicating if less significant (lower order) register is first in the pair of registers
            True: low significance register first
            False: high significance register first
    Returns:
        value (float): floating point number encoded by data in registers
        None if a decoding error occurs
    """
    if modbusTCP_object.open():
        if float_register_type == 'Holding':
            raw_data = modbusTCP_object.read_holding_registers(start_register, 2)
        elif float_register_type == 'Input':
            raw_data = modbusTCP_object.read_input_registers(start_register, 2)
    else:
        time.sleep(0.01)
        return None
    if not LoSigFirst:
        raw_data.reverse()
    LoSig_reg = raw_data[0]
    HiSig_reg = raw_data[1]
    try:
        value = round(struct.unpack(
                '!f',
                bytes.fromhex(
                    '{0:04x}'.format(HiSig_reg) + '{0:04x}'.format(LoSig_reg)
                    )
                )[0],6)
    except:
        print(f'Error parsing {start_register} {raw_data}')
        modbusTCP_object.close()
        time.sleep(.1)
        return None
    return value

def read_ModbusTCP_registers(modbusTCP_object, config, write_metric_name = False):
    """
    Reads modbus TCP/IP registers specified in config and adds each value to a string, separated by the delimiter specified in config
    Reads each register according to register type indicated in config
    Args:
        modbusTCP_object (ModbusClient): instrument modbus TCP/IP object
        config (dict): instrument configuration dictionary
        write_metric_name (bool): boolean directing whether or not to include metric names in data string
    Returns:
        data_string (str): data string consisting of all metrics contained by registers, separated by delimiter
    """

    data_string = ''
    LoSigFirst = config['Connection Information']['LoSigFirst']
    first_loop = True
    if config.get('Float Register Dictionary'):
        for element in config['Float Register Dictionary']:
            if element == 'Float Register Type':
                float_register_type = config['Float Register Dictionary'][element]
                continue
            if write_metric_name:
                metric_name = element + ','
            else:
                metric_name = ''
            address = config['Float Register Dictionary'][element] - config['Connection Information']['Register Address Offset']
            value = None
            n_try = 1
            while value == None:
                if n_try > 5:
                    break
                value = read_ModbusIEEE(modbusTCP_object, address, float_register_type, LoSigFirst)
                n_try += 1
            if first_loop:
                data_string += f'{metric_name}{value}'
                first_loop = False
            else:
                data_string += f',{metric_name}{value}'
    if config.get('Unsigned 16 Bit Register Dictionary'):
        for element in config['Unsigned 16 Bit Register Dictionary']:
            if element == 'Unsigned 16 Register Type':
                unsigned_register_type = config['Unsigned 16 Bit Register Dictionary'][element]
                continue
            if write_metric_name:
                metric_name = element + ','
            else:
                metric_name = ''
            address = config['Unsigned 16 Bit Register Dictionary'][element] - config['Connection Information']['Register Address Offset']
            value = None
            n_try = 1
            while value == None:
                if n_try > 5:
                    break
                if modbusTCP_object.open():
                    if unsigned_register_type == 'Holding':
                        value = modbusTCP_object.read_holding_registers(address, 1)[0]
                    elif unsigned_register_type == 'Input':
                        value = modbusTCP_object.read_input_registers(address, 1)[0]
                else:
                    value = None
                    time.sleep(0.01)
                n_try += 1
            if data_string == '':
                data_string += f'{metric_name}{value}'
            else:
                data_string += f',{metric_name}{value}'
    if config.get('Unsigned 32 Bit Register Dictionary'):
        for element in config['Unsigned 32 Bit Register Dictionary']:
            if element == 'Unsigned 32 Register Type':
                unsigned_register_type = config['Unsigned 32 Bit Register Dictionary'][element]
                continue
            if write_metric_name:
                metric_name = element + ','
            else:
                metric_name = ''
            address = config['Unsigned 32 Bit Register Dictionary'][element] - config['Connection Information']['Register Address Offset']
            value = None
            n_try = 1
            while value == None:
                if n_try > 5:
                    break
                if modbusTCP_object.open():
                    if unsigned_register_type == 'Holding':
                        data = modbusTCP_object.read_holding_registers(address, 2)
                    elif unsigned_register_type == 'Input':
                        data = modbusTCP_object.read_input_registers(address, 2)
                    if not LoSigFirst:
                        data.reverse()
                    [RegLo, RegHi] = data
                    value = '0x' + '{:04x}'.format(RegLo) + '{:04x}'.format(RegHi)
                else:
                    value = None
                    time.sleep(0.01)
                n_try += 1
            if value == None:
                value = 'NaN'
            if data_string == '':
                data_string += f'{metric_name}{value}'
            else:
                data_string += f',{metric_name}{value}'
    return data_string

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
