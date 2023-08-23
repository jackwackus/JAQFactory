"""
Author: Jack Connor 
Date Created: 2/8/2023
"""

import time
import sys
import datetime
from os import path, mkdir
from logger import *

def create_command_dict(config):
    """
    Uses the config dictionary to create a command dictionary containing the primary and secondary commands, in bytes
    Args:
        config (dict): dictionary of configuration information for instrument being logged
    Returns:
        command_dict (dict): dictionary containing primary and secondary commands
    """
    command_dict = {
            'Primary Command': config['Connection Information']['Primary Command'].encode('ascii'),
            'Secondary Command': config['Connection Information']['Secondary Command'].encode('ascii')
            }
    return command_dict

def command_check(command_dict, CommandSwitchSchedule, current_time, last_command_switch_time):
    """
    Runs every logger iteration to check if conditions are met to run command_2.
    If the conditions are met, returns command_2 as the command.
    Args:
        command_dict (dict): dictionary containing the primary and secondary commands
        CommandSwitchSchedule (dict): dictionary containing information on the command switching schedule
        current_time (datetime.datetime): current time
        last_command_switch_time (datetime.datetime): time of last command switch to secondary command
    Returns:
        If conditions are not met for command switching
            command_1 (bytes): primary command
            last_command_switch_time (datetime.datetime): time of last command switch to secondary command
        If conditions are met for command_switching,
            command_2 (bytes): secondary command
            command_switch_time (datetime.datetime): time that command was switched to secondary command
    """
    def command_switch(command_dict, current_time, last_command_switch_time):
        """
        Switches command if it hasn't already been switched..
        Args:
            command_dict (dict): dictionary containing the primary and secondary commands           
            current_time (datetime.datetime): current time
            last_command_switch_time (datetime.datetime): time of last command switch to secondary command
        Returns
            If secondary command was recently sent
                command_1 (bytes): primary command
                last_command_switch_time (datetime.datetime): time of last command switch to secondary command
            If secondary command was not recently sent
                command_2 (bytes): secondary command
                command_switch_time (datetime.datetime): current time, representing the time of the switch to the secondary command
        """
        if (current_time - last_command_switch_time).seconds > 10:
            return command_dict['Secondary Command'], current_time
        else:
            return command_dict['Primary Command'], last_command_switch_time

    command_1 = command_dict['Primary Command']
    if CommandSwitchSchedule['type'] == 'minute':
        if current_time.minute in CommandSwitchSchedule['value'] and current_time.second < 5:
            command_2, command_switch_time = command_switch(command_dict, current_time, last_command_switch_time)
            return command_2, command_switch_time
        else:
            return command_1, last_command_switch_time
    elif CommandSwitchSchedule['type'] == 'hour':
        if current_time.hour in CommandSwitchSchedule['value'] and current_time.minute == 0 and current_time.second < 5:
            command_2, command_switch_time = command_switch(command_dict, current_time, last_command_switch_time)
            return command_2, command_switch_time
        else:
            return command_1, last_command_switch_time
    elif current_time.hour == 0 and current_time.minute == 0 and current_time.second < 5:
        command_2, command_switch_time = command_switch(command_dict, current_time, last_command_switch_time)
        return command_2, command_switch_time
    else:
        return command_1, last_command_switch_time

def PTR_zero_controller(config, logger_state_file):
    """
    Loop to run zero controller and data logger
    Args:
        config (dict): dictionary of configuration information for instrument being logged
    Returns:
        Reads and logs data from instrument at read interval
        Writes rows of data to writeFile at write interval
        Creates new datafiles at new file interval
    """

    #Initialize the first writeFile
    current_time = datetime.datetime.now()
    writeFile = create_writeFile_name(config, current_time)
    if config["Header String"] != None:
        if not path.exists(writeFile):
            HeaderStringToDat(config["Header String"], writeFile)

    #Establish new file schedule and file writing schedule
    NewFileSchedule = determine_new_file_schedule(config['New File Interval'])
    FileWriteSchedule = determine_FileWriteSchedule(config['Write Interval'])
    
    #Establish command switching schedule
    #Note the command switching schedule has the same properties as the new file schedule and is created the same way
    CommandSwitchSchedule = determine_new_file_schedule(config['Secondary Command Interval'])

    #Initialize a value for the last command switch time
    last_command_switch_time = current_time

    #Initialize communication with instrument
    serial_object = serial_init(config)
    command_dict = create_command_dict(config)
    
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
        command, last_command_switch_time = command_check(command_dict, CommandSwitchSchedule, current_time, last_command_switch_time)
        data_string = read_serial_data(serial_object, command, config) 
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
            PTR_zero_controller(config, logger_state_file)
        else:
            print(f'{instrument} disabled.')
    else:
        log_file = log_dir + 'other_logs.txt'
        sys.stdout = open(log_file, 'w')
        print(f'{instrument} is an unsupported instrument name.')

if __name__ == '__main__':
    main()
