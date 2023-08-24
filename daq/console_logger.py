"""
Author: Jack Connor 
Date Created: 1/26/2021
Last Modified: 1/26/2023
"""

import time
import datetime
import msvcrt
from os import path, mkdir, getcwd
from logger import *

def console_NewFileCheck(writeFile, config, NewFileSchedule, current_time):
    """
    Runs every second to check if conditions are met for new file creation. If the conditions are met, returns the new file name.
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
            print(f'Writing to new file: {newFileName}\n')
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
        current_time = last_log_time + datetime.timedelta(seconds = 1)
    elif (current_time - last_log_time).seconds == 2:
        current_time = last_log_time + datetime.timedelta(seconds = 1)
    last_log_time = current_time
    return current_time, last_log_time

def console_logger(config):
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
            first_loop =False
        timestamp = get_timestamp(current_time)
        writeFile = console_NewFileCheck(writeFile, config, NewFileSchedule, current_time)
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
            print("\nConnection Established. Writing to " + writeFile + '\n\n' + "To print the dataline, press p." + '\n\n' +  "To end logging session, press e." + '\n')
            j += 1
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'p':
                print(row_string)
                print()
            elif key == b'e':
                loop = False
                print("Logging Terminated")

def stream_console_logger(config):
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
                first_log = False
            if config['Stream Log Interval'] == 1:
                current_time, last_log_time = _1_sec_stream_time_check(current_time, last_log_time)
            timestamp = get_timestamp(current_time)
            row_string = config['Instrument Name'] + config['Delimiter'] + timestamp + config['Delimiter'] + data_string
            rows_list += [row_string]
        writeFile = console_NewFileCheck(writeFile, config, NewFileSchedule, current_time)
        if current_time.second in FileWriteSchedule or current_time.second == 59:
            try:
                RowsListToDat(rows_list, writeFile, config)
                rows_list = []
            except PermissionError:
                pass
        if j == 0:
            print("\nConnection Established. Writing to " + writeFile + '\n\n' + "To print the dataline, press p." + '\n\n' +  "To end logging session, press e." + '\n')
            j += 1
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'p':
                print(row_string)
                print()
            elif key == b'e':
                loop = False
                print("Logging Terminated")

def main():
    """
    Main function to run program.
    Takes in command line arguments and calls functions
    """

    import argparse

    #Identify working directory
    working_dir = getcwd

    #Parse command line arguments
    parser = argparse.ArgumentParser(description='Data Writing Settings')
    parser.add_argument('-I', '--instrument_name', type=str, help='Name of instrument to log', metavar='', required=True)
    args = parser.parse_args()
    
    #Establish instrument variable
    instrument = args.instrument_name
    
    #Generate dictionary of configuration file paths
    config_file_dic = process_instrument_list(working_dir + '//config//')

    #If configuration file is available, generate instrument configuration dictionary and initiate console_logger or stream_console_logger accordingly
    if instrument in config_file_dic:
        config = read_daq_config(config_file_dic[instrument])
        if not path.exists(config['Output Directory']):
              mkdir(config['Output Directory'])  
        if config['Stream']:
            stream_console_logger(config)
        else:
            console_logger(config)
    else:
        print("\nUnsupported instrument name. The following instruments are supported and must be typed as displayed:\n")
        for instrument in config_file_dic:
            print(instrument)

if __name__ == '__main__':
    main()
