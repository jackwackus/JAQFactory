"""
Author: Jack Connor 
Date Created: 1/26/2021
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
from os import path, mkdir

def read_daq_config(read_file = 'C:\\Python\\daq\\config\\G2401.txt'):
    """
    Reads an instrument configuration file and writes data to a dictionary
    Args:
        read_file (str): path to configuration text file
    Returns:
        config_dic (dict): dictionary containing configuration data
    """
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

def create_writeFile_name(config, current_time):
    """
    Creates a data writeFile name based on configuration parameters and the current time
    Args:
        config (dict): instrument configuration dictionary
    Returns:
        writeFile (str): path to write instrument data
    """
    def get_time_string(current_time):
        """
        Uses clock to make a time string to minute
        Args:
            None
        Returns:
            date_string (str): string containing date
        """

        Y = str(current_time.year)
        m =str(current_time.month)
        d =str(current_time.day)
        H =str(current_time.hour)
        M =str(current_time.minute)

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

        time_string = "_" + Y + _m + m + _d + d + "_" + _H + H + _M + M
        return time_string
    time_string = get_time_string(current_time)
    output_dir = config['Output Directory'] + '\\'
    fileName = config['Instrument Name'] + time_string + ".dat"
    writeFile = output_dir + fileName
    return writeFile

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

def HeaderStringToDat(HeaderString, writeFile):
    """
    Writes header string to writeFile. Writes in append mode.
    Args:
        HeaderString (str): header string, usually pulled from configuration dictionary (config['Header String'])
        writeFile (str): path to datafile to write header to
    Returns:
        Writes header to writeFile
    """
    with open (writeFile, 'a') as f:
        f.write(HeaderString)
    return

def determine_new_file_schedule(NewFileInterval):
    """
    Creates a new file write schedule based on the config["New File Interval"] parameter.
    Obeys the following behavior:

        For entered intervals less than or equal to 60 minutes, rounds the interval to the nearest factor of 60. Creates a list of new file creation times, from minute=0 to minute=60,
        spaced by interval.

        For entered intervals greater than 60 minutes and less than or equal to 1080 minutes, converts interval to hours and rounds interval to the nearest factor of 24.
        Creates a list of new file creation times, from hour=0 to hour=24, spaced by interval.

        For entered intervals greater than 1080 minutes, rounds the interval to 24 hours. Sets new file creation for 00:00 each day.

    Args:
        NewFileInterval (int): Number of minutes specified by user to create new file. Usually pulled from config["New File Interval"]
    Returns:
        Dictionary containing type of file schedule (minute, hour, or daily), and if applicable, schedule in numpy array.

    """
    def round_interval(NewFileInterval, upper_bound):
        """
        Rounds NewFileInterval to nearest factor of upper bound
        Args:
            NewFileInterval (int or float): If minutes entered by user were less than or equal to 60, number of minutes selected for new file interval.
                If minutes entered by user were greater than 60 minutes and less than or equal to 1080 minutes, input converted to hours.
            upper_bound (int): Number to factor in order to round interval value. Must be same units as interval
        Returns:
            NewFileInterval (int) if already a factor of upper_bound; closest_element (int): if NewFileInterval not factor of upper bound, returns closest factor to NewFileInterval
        """
        factors_list = []
        for n in range(1, upper_bound+1):
            if upper_bound % n == 0:
                factors_list += [n]
        if NewFileInterval not in factors_list:
            print('New File Intervals below 60 minutes are rounded to nearest factor of 60.\nNew File Intervals greater than 1 hour and less than 24 hours are rounded to nearest factor of 24.')
            proximity_dic = {}
            for factor in factors_list:
                proximity_dic[factor] = abs(NewFileInterval - factor)
            i = 0
            for element in proximity_dic:
                if i == 0:
                    closest_element = element
                    i += 1
                elif proximity_dic[element] < proximity_dic[closest_element]:
                    closest_element = element
            return closest_element
        else:
            return int(NewFileInterval)

    if NewFileInterval <= 60:
        NewFileInterval = round_interval(NewFileInterval, 60)
        return {'type': 'minute', 'value': np.arange(0, 60, NewFileInterval)}
    elif NewFileInterval <= 1080:
        # Convert to hours
        NewFileInterval = NewFileInterval/60
        NewFileInterval = round_interval(NewFileInterval, 24)
        return {'type': 'hour', 'value': np.arange(0, 24, NewFileInterval)}
    else:
        print("New File Intervals above 1080 minutes are rounded up to 24 hours.")
        return {'type': 'daily'}

def determine_FileWriteSchedule(WriteInterval):
    """
    Creates a file write schedule based on the config["Write Interval"] parameter.
    Obeys the following behavior:

        Only allows intervals less than or equal to 60 seconds. Rounds the interval to the nearest factor of
        60. Creates a list of file write times spaced by interval.

    Args:
        WriteInterval (int): Number of seconds specified by user as a writing interval.
        Usually pulled from config["New File Interval"]
    Returns:
        FileWriteSchedule (numpy array): list of seconds to write on 
    """
    def round_interval(WriteInterval, upper_bound):
        """
        Rounds WriteInterval to nearest factor of upper bound
        Args:
            WriteInterval (int): File write interval selected by user in seconds
            upper_bound (int): Number to factor in order to round interval value.
            Must be same units as interval.
        Returns:
            WriteInterval (int): if WriteInterval already a factor of upper_bound
            closest_element (int): if WriteInterval not factor of upper bound
            returns closest factor to WriteInterval
        """
        factors_list = []
        for n in range(1, upper_bound+1):
            if upper_bound % n == 0:
                factors_list += [n]
        if WriteInterval not in factors_list:
            print('\nWrite file intervals are rounded to nearest factor of 60.')
            proximity_dic = {}
            for factor in factors_list:
                proximity_dic[factor] = abs(WriteInterval - factor)
            i = 0
            for element in proximity_dic:
                if i == 0:
                    closest_element = element
                    i += 1
                elif proximity_dic[element] < proximity_dic[closest_element]:
                    closest_element = element
            return closest_element
        else:
            return int(WriteInterval)

    if WriteInterval > 60:
        WriteInterval = 60
    WriteInterval = round_interval(WriteInterval, 60)
    FileWriteSchedule = np.arange(0, 60, WriteInterval)
    return FileWriteSchedule

def NewFileCheck(writeFile, config, NewFileSchedule, current_time):
    """
    Runs every logger iteration to check if conditions are met for new file creation.
    If the conditions are met, returns the new file name.
    Writes a header to the new file if a header is specified in config
    Args:
        writeFile (str): path to current writeFile
        config (dict): instrument configuration dictionary
        NewFileSchedule (dict): dictionary containing information on the new file creation schedule
    Returns:
        writeFile (str) if conditions are not met for new file creation
        If conditions are met for new file creation, returns newFileName (str): path to new file.
        Writes header to new file if directed by config. 
    """
    def newFileReturn(writeFile, config, current_time):
        """
        Creates new file if it hasn't already been created. Returns new file name.
        Args:
            writeFile (str): path to current writeFile
            config (dict): instrument configuration dictionary           
        Returns
            writeFile (str) if new file has already been created
            If new file has not been created, newFileName (str): path to new file.
            Writes header to new file if directed by config.
        """
        newFileName = create_writeFile_name(config, current_time)
        if writeFile != newFileName:
            if config["Header String"] != None:
                HeaderStringToDat(config["Header String"], newFileName)
            #print(f'Writing to new file: {newFileName}\n')
            return newFileName
        else:
            return writeFile

    if NewFileSchedule['type'] == 'minute':
        if current_time.minute in NewFileSchedule['value'] and current_time.second < 5:
            return newFileReturn(writeFile, config, current_time)
        else:
            return writeFile
    elif NewFileSchedule['type'] == 'hour':
        if current_time.hour in NewFileSchedule['value'] and current_time.minute == 0 and current_time.second < 5:
            return newFileReturn(writeFile, config, current_time)
        else:
            return writeFile
    elif current_time.hour == 0 and current_time.minute == 0 and current_time.second < 5:
        return newFileReturn(writeFile, config, current_time)
    else:
        return writeFile

def RowsListToDat(rows_list, writeFile, config):
    """
    Writes a list of row strings to a data file
    Args:
        rows_list (list): list of data strings to write
        writeFile (str): path to write data to
    Returns
        writes lines to datafile
    """
    if len(rows_list) > 0:
        with open (writeFile, 'a') as f:
            if config['Header String'] == None:
                for row in rows_list:
                    f.write(row + '\n')
            else:
                for row in rows_list:
                    f.write('\n' + row)
    return

def round_current_time(current_time):
    """
    Repeat timestamps with streaming data may be alleviated through rounding
    Args:
        current_time (datetime.datetime): datetime object from datetime.datetime.now()
    Returns:
        current_time (datetime.datetime): datetime object rounded to nearest second
    """
    S = round(current_time.second + current_time.microsecond/1000000)
    if S < 60:
        Y = current_time.year
        m = current_time.month
        d = current_time.day
        H = current_time.hour
        M = current_time.minute
        return datetime.datetime(Y, m, d, H, M, S)
    else:
        current_time = current_time + datetime.timedelta(seconds = 1)
        Y = current_time.year
        m = current_time.month
        d = current_time.day
        H = current_time.hour
        M = current_time.minute
        S = current_time.second
        return datetime.datetime(Y, m, d, H, M, S)

def get_timestamp(current_time):
    """
    Uses clock to make a timestamp
    Args:
        current_time (datetime.datetime): datetime object representing current time
    Returns:
        string containing timestamp
    """
    return datetime.datetime.strftime(current_time, "%Y-%m-%d %H:%M:%S")

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
        print(f'Running {config.get("Startup Purge")} second startup purge.')
        it = 0
        while it < config['Startup Purge']:
            if not config['Stream']:
                serial_object.write(config['Connection Information']['Command'].encode('ascii'))
            it += 1
            time.sleep(1)
            serial_object.read(serial_object.in_waiting)
        print('Startup purge complete.')
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
    while len(data) > config['Connection Information']['Length Max']:
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
        if config['Connection Information'].get('Handle Garbled'):
            data_string += data.decode('ascii', 'ignore')
        else:
            data_string += data.decode('ascii')
    return data_string

def EndOfString_serial_stream_read(serial_object, config, data_string):
    """
    Reads serial buffer until end of line character indicated by config.
    Stream version appends to data obtained in read_serial_stream until data string is complete.
    Args:
        serial_object (serial.Serial): serial connection object
        config (dict): instrument configuration dictionary
        data_string (str): complete or partial data string read during read_serial_stream
    Returns:
       data_string (str): decoded instrument data line 
    """
    EOS = config['Connection Information']['End of String']
    while data_string.find(EOS) < 0:
        time.sleep(0.05)
        data = serial_object.read(serial_object.in_waiting)
        data_string += data.decode('ascii')
    return data_string

def read_serial_data(serial_object, command, config):
    """
    Sends serial command to instrument and reads response.
    Args:
        serial_object (serial object): serial object for instrument to communicate with
        command (bytes): command to send instrument to elicit data response
        config (dict): instrument configuration dictionary
    Returns:
        data_string (str): string of data sent by instrument
    """
    if config['Instrument Name'] == '42C':
        data_string = read42C_output(serial_object, command)
    else:
        serial_object.write(command)
        if config['Connection Information'].get('End of String') != None:
            data_string = EndOfString_serial_read(serial_object, config)
        elif config['Connection Information'].get('Command Wait Time') != None:
            time.sleep(config['Connection Information']['Command Wait Time'])
            data_string = serial_object.read(serial_object.in_waiting).decode('ascii')
        else:
            data_string = serial_object.read(serial_object.in_waiting).decode('ascii')
    return data_string

def read42C_output(serial_object, command, sleep_interval = .2):
    """
    Writes command to 42C and reads intrument response
    Args:
        serial_object (Serial object): 42C serial connection object
        command (bytestring): data pull command generated from create_serial_command(config)
        sleep interval (float): number of seconds to wait to read instrument response after sending command
    Returns:
        data_string (str): 42C response to command
    """
    while serial_object.in_waiting > 0:
        serial_object.read(serial_object.in_waiting)
    serial_object.write(command)
    time.sleep(sleep_interval)
    InstrumentBuff_len = serial_object.in_waiting
    InstrumentBuff = serial_object.read(InstrumentBuff_len)
    CR_index = InstrumentBuff.find(b'\r')
    if InstrumentBuff.find(b'\n') > 0:
        NL_index = InstrumentBuff.find(b'\n')
        byte_line_1 = InstrumentBuff[0:NL_index]
        byte_line_2 = InstrumentBuff[NL_index+1:CR_index]
        byte_string = byte_line_1 + byte_line_2
    else:
        byte_string = InstrumentBuff[0:CR_index]
    try:
        data_string = byte_string.decode('ascii')
        return data_string
    except UnicodeDecodeError:
        return read42C_output(serial_object, command)

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
            data_string = s.recv(1024).decode('ascii')
        return data_string

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

def read_ModbusIEEE(modbusTCP_object, start_register, LoSigFirst = True):
    """
    Adapted from https://stackoverflow.com/questions/59883083/convert-two-raw-values-to-32-bit-ieee-floating-point-number
    Reads modbus data encoded with IEEE 754 (Institute of Electrical and Electronics Engineers Standard for Floating Point Arithmetic).
    Reads 32 bits from two 16 bit registers and converts data to a floating point number.
    Args:
        modbusTCP_object (ModbusClient): modbus TCP/IP communication object
        start_register (int): register address to begin reading from
        LoSigFirst (bool): boolean indicating if less significant (lower order) register is first in the pair of registers
            True: low significance register first
            False: high significance register first
    Returns:
        value (float): floating point number encoded by data in registers
        None if a decoding error occurs
    """
    if modbusTCP_object.open():
        raw_data = modbusTCP_object.read_holding_registers(start_register, 2)
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
                )[0],3)
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
    for metric in config['Float Register Dictionary']:
        if write_metric_name:
            metric_name = metric + ','
        else:
            metric_name = ''
        address = config['Float Register Dictionary'][metric] - config['Connection Information']['Register Address Offset']
        value = None
        n_try = 1
        while value == None:
            if n_try > 5:
                break
            value = read_ModbusIEEE(modbusTCP_object, address, LoSigFirst)
            n_try += 1
        if first_loop:
            data_string += f'{metric_name}{value}'
            first_loop = False
        else:
            data_string += f',{metric_name}{value}'
    for metric in config['Unsigned 16 Bit Register Dictionary']:
        if write_metric_name:
            metric_name = metric + ','
        else:
            metric_name = ''
        address = config['Unsigned 16 Bit Register Dictionary'][metric] - config['Connection Information']['Register Address Offset']
        value = None
        n_try = 1
        while value == None:
            if n_try > 5:
                break
            if modbusTCP_object.open():
                value = modbusTCP_object.read_holding_registers(address, 1)[0]
            else:
                value = None
                time.sleep(0.01)
            n_try += 1
        if data_string == '':
            data_string += f'{metric_name}{value}'
        else:
            data_string += f',{metric_name}{value}'
    for metric in config['Unsigned 32 Bit Register Dictionary']:
        if write_metric_name:
            metric_name = metric + ','
        else:
            metric_name = ''
        address = config['Unsigned 32 Bit Register Dictionary'][metric] - config['Connection Information']['Register Address Offset']
        value = None
        n_try = 1
        while value == None:
            if n_try > 5:
                break
            if modbusTCP_object.open():
                data = modbusTCP_object.read_holding_registers(address, 2)
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

def create_serial_stream_dic(config):
    """
    Uses sentence list in config file to create a data dictionary for use in read_serial_stream.
    Creates a dictionary with value None for each sentence key.
    Args:
        config (dict): instrument configuration dictionary
    Returns:
        data_dic (dict): dictionary with value None for each sentence key
    """
    data_dic = {}
    if len(config['Sentence List']) > 0:
        for sentence in config['Sentence List']:
            data_dic[sentence] = None
    else:
        data_dic = None
    return data_dic

def read_serial_stream(serial_object, config, data_dic, new_string = b'', try_n = 0):
    """
    Reads streamed serial data
    If ouput is broken into keyed sentences separated by end of line delimiters,
        Reads serial stream until all desired data sentences have been completely read and stored in a dictionary.
    If output does not have keyed sentences, reads serial data until end of line.
    Args:
        serial_object (serial.Serial): instrument serial connection object
        config (dict): instrument configuration dictionary
        data_dic (dict): dictionary containing data sentences keyed by sentence keys
            At recursion depth 0, provided by create_serial_stream_dic
        new_string (bytes): byte string to add incoming data to
            Empty at recursion depth 0
            Modified at each recursion level based on data read and data stored in data_dic
    Returns
        If keyed sentence type:
            data_dic (dict): dictionary of completed data sentences keyed by sentence key
        If conventional type:
            EndOfString_serial_stream_read function 
    """
    sentence_delimiter = config.get('Sentence Delimiter')
    buff = serial_object.in_waiting
    data = serial_object.read(buff)
    if buff > config['Connection Information']['Buffer Size Max']:
        return None
    new_string += data
    try:
        read_string = new_string.decode('ascii')
        if data_dic != None:
            for key in data_dic:
                if key in read_string:
                    key_index = read_string.find(key)
                    segment = read_string[key_index:]
                    CR_index = segment.find(sentence_delimiter)
                    if CR_index > 0:
                        sentence = segment[:CR_index]
                        data_dic[key] = sentence
                        end_sentence_index = key_index + CR_index + len(sentence_delimiter)
                        read_string = read_string[0:key_index] + read_string[end_sentence_index:]
                        new_string = read_string.encode('ascii')
        else:
            if len(read_string) == 0:
                return None
            else:
                return EndOfString_serial_stream_read(serial_object, config, read_string)
    except UnicodeDecodeError:
        pass
    for key in data_dic:
        if data_dic[key] == None:
            time.sleep(.1)
            if try_n < 10:
                try_n += 1
                return read_serial_stream(serial_object, config, data_dic, new_string, try_n)
            else:
                return None
    return data_dic

def parse_serial_stream_dic(data_dic, config):
    """
    Parses data_dic produced by read_serial_stream. Produces consolidated data string.
    Args:
        data_dic (dict): data dictionary generated by read_data_stream
        config (dict): instrument configuration file dictionary
    Returns:
        data_string (str): consolidated string of data sentences separated by delimiter specified in config
    """
    data_string = ''
    first_loop = True
    for key in data_dic:
        if first_loop:
            data_string += data_dic[key]
            first_loop = False
        else:
            data_string += config['Delimiter'] + data_dic[key]
    return data_string

def _1_sec_stream_time_check(current_time, last_log_time):
    """
    Differences in streaming clock and computer clock can lead to repeat and skipped seconds
    with 1 second logging.
    This function handles these cases and changes current_time value when the occur.
    Args:
        current_time (datetime.datetime): current time rounded to nearest second
        last_log_time (datetime.datetime): last time logging occured
    Returns:
        current_time (datetime.datetime): current time rounded to nearest second (corrected if warranted)
        last_log_time (datetime.datetime): last time logging occured (set to current_time)
    """ 
    if (current_time - last_log_time).seconds == 0:
        print(f'\tStream TS case 1 occured at {current_time} with last log time of {last_log_time}.')
        current_time = last_log_time + datetime.timedelta(seconds = 1)
    elif (current_time - last_log_time).seconds == 2:
        print(f'\tStream TS case 2 occured at {current_time} with last log time of {last_log_time}.')
        current_time = last_log_time + datetime.timedelta(seconds = 1)
    last_log_time = current_time
    return current_time, last_log_time

def clean_string(data_string, config):
    """
    Data strings may contain carriage return or newline characters. This function removes those characters (if they aren't at the first index)
    Args:
        data_string (str): string of data to be cleaned
        multiline (bool): boolean indicating if data_string contains multiple lines
        MinStringLength (int): for multiline strings
            this is the minimum number of characters that the string must contain in order for it to be accepted as complete
        sentence_delimiter (str): for multiline strings
            this is the sequence of characters that delimit lines within the string
    Returns:
        data_string (str): cleaned string of data
    """
    multiline = config.get('Multiline')
    sentence_delimiter = config.get('Sentence Delimiter')
    if data_string != None:
        if multiline:
            new_string = ""
            first_loop = True
            while data_string.find(sentence_delimiter) >= 0:
                CR_index = data_string.find(sentence_delimiter)
                if first_loop:
                    new_string += data_string[:CR_index]
                    first_loop = False
                else:
                    new_string += config['Delimiter'] + data_string[:CR_index]
                data_string = data_string[CR_index+len(sentence_delimiter):]
            return new_string
        else:
            CR_index = data_string.find('\r')
            if CR_index > 0:
                data_string = data_string[:CR_index]
            NL_index = data_string.find('\n')
            if NL_index > 0:
                data_string = data_string[:NL_index]
            return data_string
    else:
        return None

def logger(config, logger_state_file):
    """
    Loop to run the datalogger
    Args:
        config (dict): dictionary of configuration information for instrument being logged
    Returns:
        Reads and logs data from instrument at read interval
        Writes rows of data to writeFile at write interval
        Creates new datafiles at new file interval
    """

    #List of communication types that will be directed to serial_init function
    serial_init_list = [
            'Serial',
            ]

    #List of communication types that will be directed to modbus_init function
    modbus_list = [
            'Modbus Serial',
            'Modbus TCP/IP'
            ]

    #Initialize the first writeFile
    current_time = datetime.datetime.now()
    writeFile = create_writeFile_name(config, current_time)
    if config["Header String"] != None:
        if not path.exists(writeFile):
            HeaderStringToDat(config["Header String"], writeFile)

    #Establish new file schedule and file writing schedule
    NewFileSchedule = determine_new_file_schedule(config['New File Interval'])
    FileWriteSchedule = determine_FileWriteSchedule(config['Write Interval'])

    #Initialize communication with instrument
    comm_type = config['Communication Type']
    if comm_type in serial_init_list:
        serial_object = serial_init(config)
        command = create_serial_command(config)
    elif comm_type in modbus_list:
        modbus_object = modbus_init(config)
    else:
        pass
    
    #Set up variables for loop
    j = 0
    loop = True
    first_loop = True
    rows_list = []

    #Run loop
    while loop:
        #time.sleep configured to sync with system clock for logging
        time.sleep(config['Read Interval'] - time.time() % config['Read Interval'])
        current_time = datetime.datetime.now()
        if first_loop:
            check_logger_state_time = current_time
            first_loop = False
        if (current_time - check_logger_state_time).seconds >= 60:
            check_logger_state_time = current_time
            with open(logger_state_file, 'r') as f:
                i = 0
                for line in f:
                    if i == 0:
                        line = line
                    else:
                        pass
            if "Quit" in line:
                print("Logging Terminated")
                break
        timestamp = get_timestamp(current_time)
        writeFile = NewFileCheck(writeFile, config, NewFileSchedule, current_time)
        if comm_type == 'Serial':
            data_string = read_serial_data(serial_object, command, config) 
            data_string = clean_string(data_string, config)
        elif comm_type == 'Modbus Serial':
            data_string = read_ModbusSerial_registers(modbus_object, config)
            data_string = clean_string(data_string, config)
        elif comm_type == 'Modbus TCP/IP':
            data_string = read_ModbusTCP_registers(modbus_object, config)
        elif comm_type == 'TCP/IP':
            data_string = read_TCPIP_data(config)
            data_string = clean_string(data_string, config)
        if data_string != None:
            row_string = config['Instrument Name'] + config['Delimiter'] + timestamp + config['Delimiter'] + data_string
            rows_list += [row_string]
        if current_time.second in FileWriteSchedule or current_time.second == 59:
            try:
                RowsListToDat(rows_list, writeFile, config)
                rows_list = []
            except PermissionError:
                pass
        if j == 0:
            print(f'{config["Instrument Name"]} connection Established. Writing to {writeFile}.')
            j += 1

def stream_logger(config, logger_state_file):
    """
    Loop to run the datalogger
    Args:
        config (dict): dictionary of configuration information for instrument being logged
    Returns:
        Reads and logs data from instrument at read interval
        Writes rows of data to writeFile at write interval
        Creates new datafiles at new file interval
    """

    #List of communication types that will be directed to serial_init function
    serial_init_list = [
            'Serial',
            ]

    #List of communication types that will be directed to modbus_init function
    modbus_list = [
            'Modbus Serial',
            'Modbus TCP/IP'
            ]

    #Initialize the first writeFile
    current_time = datetime.datetime.now()
    writeFile = create_writeFile_name(config, current_time)
    if config["Header String"] != None:
        if not path.exists(writeFile):
            HeaderStringToDat(config["Header String"], writeFile)

    #Establish new file schedule and file writing schedule
    NewFileSchedule = determine_new_file_schedule(config['New File Interval'])
    FileWriteSchedule = determine_FileWriteSchedule(config['Write Interval'])

    #Initialize communication with instrument
    comm_type = config['Communication Type']
    if comm_type in serial_init_list:
        serial_object = serial_init(config)
        command = create_serial_command(config)
    elif comm_type in modbus_list:
        modbus_object = modbus_init(config)
    elif comm_type == 'TCP/IP':
        socket_object = TCPIP_stream_init(config)
    else:
        pass
    
    #Set up variables for loop
    j = 0
    loop = True
    first_loop = True
    first_log = True
    rows_list = []

    #Run loop
    while loop:
        time.sleep(config['Read Interval'])
        current_time = round_current_time(datetime.datetime.now())
        if first_loop:
            check_logger_state_time = current_time
            first_loop =False
        if (current_time - check_logger_state_time).seconds >= 60:
            check_logger_state_time = current_time
            with open(logger_state_file, 'r') as f:
                i = 0
                for line in f:
                    if i == 0:
                        line = line
                    else:
                        pass
            if "Quit" in line:
                loop = False
                print("Logging Terminated")
        if comm_type == 'Serial':
            data_dic = create_serial_stream_dic(config)
            data = read_serial_stream(serial_object, config, data_dic) 
            if type(data) == dict:
                data_string = parse_serial_stream_dic(data, config)
            else:
                data_string = clean_string(data, config)
        elif comm_type == 'TCP/IP':
            data = socket_object.recv(1024)
            if len(data) > config['Connection Information']['Length Max']:
                continue
            else:
                data_string = clean_string(data.decode('ascii'), config)
        if data_string != None:
            if first_log:
                last_log_time = current_time - datetime.timedelta(seconds=1)
                print(f'First log occured at {current_time} with last_log_time set to {last_log_time}.')
                first_log = False
            if config['Stream Log Interval'] == 1:
                current_time, last_log_time = _1_sec_stream_time_check(current_time, last_log_time)
            timestamp = get_timestamp(current_time)
            row_string = config['Instrument Name'] + config['Delimiter'] + timestamp + config['Delimiter'] + data_string
            rows_list += [row_string]
        writeFile = NewFileCheck(writeFile, config, NewFileSchedule, current_time)
        if current_time.second in FileWriteSchedule or current_time.second == 59:
            try:
                RowsListToDat(rows_list, writeFile, config)
                rows_list = []
            except PermissionError:
                pass
        if j == 0:
            print(f'{config["Instrument Name"]} connection Established. Writing to {writeFile}.')
            j += 1

def main():
    """
    Main function to run program.
    Takes in command line arguments and calls functions
    """

    import argparse

    #Parse command line arguments
    parser = argparse.ArgumentParser(description='Data Writing Settings')
    parser.add_argument('-I', '--instrument_name', type=str, help='Name of instrument to log', metavar='', required=True)
    args = parser.parse_args()

    #Establish instrument variable
    instrument = args.instrument_name
    
    #Generate dictionary of configuration file paths
    config_file_dic = process_instrument_list()

    #Specify a directory for log files
    log_dir = "C:\\Python\\daq\\logs\\"
    
    #Specify a logger state file
    #This file stores user directives to continue running or to quit
    logger_state_file = 'C:\\Python\\daq\\logger_state\\logger_state.txt'

    #If configuration file is available, generate instrument configuration dictionary
    #If instrument is enabled, initiate logger or stream_logger according to instrument configuration
    if instrument in config_file_dic:
        config = read_daq_config(config_file_dic[instrument])
        if not path.exists(config['Output Directory']):
              mkdir(config['Output Directory'])  
        log_file = log_dir + instrument + '.txt'
        error_log_file = log_dir + instrument + '_error.txt'
        sys.stdout = open(log_file, 'w')
        sys.stderr = open(error_log_file, 'w')
        if config['Enabled']:
            if config['Stream']:
                stream_logger(config, logger_state_file)
            else:
                logger(config, logger_state_file)
        else:
            print(f'{instrument} disabled.')
    else:
        log_file = log_dir + 'other_logs.txt'
        sys.stdout = open(log_file, 'w')
        print(f'{instrument} is an unsupported instrument name.')

if __name__ == '__main__':
    main()
