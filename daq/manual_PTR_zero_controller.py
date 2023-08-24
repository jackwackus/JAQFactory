"""
Author: Jack Connor 
Date Created: 2/6/2023
Last Modified: 8/23/2023
"""

import sys
import time
import msvcrt
from os import path, mkdir, system, getcwd
from logger import *
from datetime import datetime, timedelta

def console_NewFileCheck(writeFile, config, NewFileSchedule, current_time, end_timestamp):
    """
    Runs every second to check if conditions are met for new file creation. If the conditions are met, returns the new file name.
    Writes a header to the new file if a header is specified in config
    Args:
        writeFile (str): path to current writeFile
        config (dict): instrument configuration dictionary
        NewFileSchedule (dict): dictionary containing information on the new file creation schedule
        current_time (datetim.datetime): datetime object representing current time
        end_timestamp (str): string representing the time at which zero will end
    Returns:
        writeFile (str) if conditions are not met for new file creation
        If conditions are met for new file creation, returns newFileName (str): path to new file.
        Writes header to new file if directed by config. 
    """
    def newFileReturn(writeFile, config, current_time, end_timestamp):
        """
        Creates new file if it hasn't already been created. Returns new file name.
        Args:
            writeFile (str): path to current writeFile
            config (dict): instrument configuration dictionary           
            current_time (datetim.datetime): datetime object representing current time
            end_timestamp (str): string representing the time at which zero will end
        Returns
            writeFile (str) if new file has already been created
            If new file has not been created, newFileName (str): path to new file.
            Writes header to new file if directed by config.
        """
        newFileName = create_writeFile_name(config, current_time)
        if writeFile != newFileName:
            if config["Header String"] != None:
                HeaderStringToDat(config["Header String"], newFileName)
            print('\n'.join([
                f'Writing to new file: {newFileName}',
                f'Zero will deactivate at {end_timestamp}.',
                'To print the most recent dataline, press p.\n'
                ]))
            return newFileName
        else:
            return writeFile

    if NewFileSchedule['type'] == 'minute':
        if current_time.minute in NewFileSchedule['value'] and current_time.second < 5:
            return newFileReturn(writeFile, config, current_time, end_timestamp)
        else:
            return writeFile
    elif NewFileSchedule['type'] == 'hour':
        if current_time.hour in NewFileSchedule['value'] and current_time.minute == 0 and current_time.second < 5:
            return newFileReturn(writeFile, config, current_time, end_timestamp)
        else:
            return writeFile
    elif current_time.hour == 0 and current_time.minute == 0 and current_time.second < 5:
        return newFileReturn(writeFile, config, current_time, end_timestamp)
    else:
        return writeFile

def manual_PTR_zero_controller(config, serial_object, zero_length, NewFileSchedule, FileWriteSchedule):
    """
    Loop to run the datalogger
    Args:
        config (dict): dictionary of configuration information for instrument being logged
        serial_object (serial.Serial): serial object associated with PTR zero controller
        zero_length (int): time duration in seconds to carry out zero
        NewFileSchedule (dict): dictionary containing information on the new file creation schedule
        FileWriteSchedule (numpy array): list of seconds to write on 
    Returns:
        Sends command to instrument to begin zero
        Reads and logs data from instrument at read interval
        Writes rows of data to writeFile at write interval
        Creates new datafiles at new file interval
    """

    #Establish data for timing the zero
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds = zero_length)

    #Set up variables for loop
    j = 0
    rows_list = []

    #Run loop
    while datetime.now() < end_time:
        #time.sleep configured to sync with system clock for logging
        time.sleep(config['Read Interval'] - time.time() % config['Read Interval'])
        current_time = datetime.now()
        timestamp = get_timestamp(current_time) 
        if j == 0:
            #Reset data for timing the zero
            start_time = current_time
            end_time = start_time + timedelta(seconds = zero_length)
            start_timestamp = timestamp
            end_timestamp = get_timestamp(end_time)

            #Send zero command, record Response
            command = f'{zero_length}\n'.encode('ascii')
            data_string = read_serial_data(serial_object, command, config) 
            data_string = clean_string(data_string, config)
            row_string = config['Instrument Name'] + config['Delimiter'] + start_timestamp + config['Delimiter'] + data_string

            #Initialize writeFile
            writeFile = create_writeFile_name(config, current_time)
            if config["Header String"] != None:
                if not path.exists(writeFile):
                    HeaderStringToDat(config["Header String"], writeFile)

            #Print message with information about the zero
            print_string = '\n'.join([
                'Manual PTR Zero Controller',
                f'\n{zero_length} second zero activated at {start_timestamp}.',
                f'Zero will deactivate at {end_timestamp}.\n'
                ])
            system('cls')
            print(print_string)
        writeFile = console_NewFileCheck(writeFile, config, NewFileSchedule, current_time, end_timestamp)
        command = config['Connection Information']['Primary Command'].encode('ascii')
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
            print_string = '\n'.join([
            f'Writing data to {writeFile}.',
            'To print the most recent dataline, press p.\n'
            ])
            print(print_string)
            j += 1
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'p':
                print(row_string)
                print()

def main():
    """
    Main function to run program.
    Loops waiting for user commands.
    Processes user commands. Breaks loop if command is 'Quit'.
    """

    system('cls')

    #Identify working directory
    working_dir = getcwd

    #Get PTR Zero Config
    config_file_dict = process_instrument_list(working_dir + '//config//')
    config = read_daq_config(config_file_dict['PTR Zero'])


    #Establish new file schedule and file writing schedule
    NewFileSchedule = determine_new_file_schedule(config['New File Interval'])
    FileWriteSchedule = determine_FileWriteSchedule(config['Write Interval'])

    #Initiate serial connection
    try:
        ser = serial_init(config)
    except:
        print_string = '\n'.join([
            'Manual PTR Zero Controller',
            '\nSerial connection unsuccesful.',
            'Troubleshoot serial connection and try again.'
            ])

        system('cls')
        print(print_string)
        time.sleep(3)
        sys.exit()
    
    #Intitialize manager and print start-up messages
    print_string = '\n'.join([
        'Manual PTR Zero Controller',
        '\nZero inactive.',
        'To activate a zero, type the number of minutes for the zero and press enter.',
        'To quit this program, type "Quit" and press enter.'
        ])
    print(print_string)

    #Wait for and process user input
    user_command = input()
    while user_command != 'Quit':
        zero_length = 0
        try:
            zero_length = int(user_command)*60
        except:
            print('Invalid Command. Try again.\n')
            user_command = input()
        if zero_length > 0: 
            #Run Controller
            manual_PTR_zero_controller(config, ser, zero_length, NewFileSchedule, FileWriteSchedule)
            system('cls')
            print(print_string)
            user_command = input()


if __name__ == '__main__':
    main()
