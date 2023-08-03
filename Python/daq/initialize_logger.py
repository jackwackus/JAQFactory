"""
Author: Jack Connor 
Date Created: 2/19/2021
Last Modified: 1/26/2023
"""

import os
import sys
import time
import pandas as pd

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

def create_EnableState_df(config_file_dic):
    """
    Reads all instrument config files in config_file_dic and saves enable state to a dataframe
    Args:
        config_file_dic (dict): dictionary of instrument configuration files created from process_instrument_list()
    Returns:
        EnableState_df (pandas DataFrame): dataframe of instruments and respective enable states
    """

    EnableState_dic = {'Instrument Name': [], 'Enable State': []}
    for instrument in config_file_dic:
        instrument_name_error_statement = '\n'.join([
            f'No Configuration file exists for {instrument}.',
            f'A configuration file is required for logging.',
            f'Skipping {instrument}.\n'
            ])
        configuration_file_error_statement = '\n'.join([
            f'An error occurred processing {instrument} configuration file.',
            f'{instrument} configuration file must be fixed for {instrument} to log.',
            f'You can try to enable {instrument} after fixing the configuration file.\n'
            ])
        try:
            config = read_daq_config(config_file_dic[instrument])
            if instrument == config['Instrument Name']:
                EnableState_dic['Instrument Name'] += [instrument]
                if config['Enabled']:
                    EnableState_dic['Enable State'] += ['Enabled']
                else:
                    EnableState_dic['Enable State'] += ['Disabled']
            else:
                print(instrument_name_error_statement)
                continue
        except FileNotFoundError:
            print(instrument_name_error_statement)
            continue
        except:
            print(configuration_file_error_statement)
            EnableState_dic['Instrument Name'] += [instrument]
            EnableState_dic['Enable State'] == ['Configuration Error']
    EnableState_df = pd.DataFrame(EnableState_dic)
    return EnableState_df

def process_valid_command(enable_command, instrument_name, config_file_dic):
    """
    If a valid enable or disable command is recieved, reads corresponding instrument config file,
    copies config file, and rewrites file with new enable state line.
    Prints messages to console. Takes new input() value.
    Args:
        enable_command (str): enable state value selected by user
        instrument_name (str): instrument name
        config_file_dic (dict): dictionary of instrument configuration files
    Returns:
        user_command (str): next user input to be processed
        Writes new instrument enable state to corresponding configuration file
        Prints status messages
    """
    config_filename = config_file_dic[instrument_name]
    print_string_dic = {'True': 'enabled', 'False': 'disabled'}
    with open(config_filename, 'r') as f:
        data = []
        for line in f:
            if "Enabled" in line:
                line = 'Enabled=' + enable_command + '\n'
            data += [line]
    with open(config_filename, 'w') as f:
        for line in data:
            f.write(line)
    os.system('cls')
    print_string = '\n'.join([
        'JAQFactory Initializer',
        f'\nYou have succesfully {print_string_dic[enable_command]} {instrument_name}.',
        '\nCurrent enable state configuration:'
        ])

    print(print_string)
    EnableState_df = create_EnableState_df(config_file_dic)
    print(EnableState_df)

    print_string = '\n'.join([
        '\nWould you like to enable or disable another instrument?',
        '\nIf no, press enter.',
        'If you would like to enable an instrument, enter "enable Instrument Name".',
        'If you would like to disable an instrument, enter "disable Instrument Name".',
        'After enabling or disabling an instrument, you will be prompted with the option to enable or disable another instrument.\n'
        ])

    print(print_string)
    user_command = input()

    return user_command

def user_command_loop(user_command, config_file_dic):
    """
    Loop to process user commands
    Args:
        user_command (str): user commmand input() value
        config_file_dic (dict): dictionary of instrument configuration file paths
    Returns:
        Command processing return values
        Breaks if command is just the Enter button
    """
    if user_command != "":
        loop = True
        while loop:
            if 'enable' in user_command:
                instrument_name = user_command[7:]
                if instrument_name in config_file_dic:
                    user_command = process_valid_command('True', instrument_name, config_file_dic) 
                else:
                    print('Invalid Instrument Name or command format. Try again\n')
                    user_command = input()
            elif 'disable' in user_command:
                instrument_name = user_command[8:]
                if instrument_name in config_file_dic:
                    user_command = process_valid_command('False', instrument_name, config_file_dic) 
                else:
                    print('Invalid Instrument Name or command format. Try again\n')
                    user_command = input()
            elif user_command == "":
                break
            else:
                print('Invalid Command. Try again\n')
                user_command = input()
    else:
        pass

def main():
    """
    Main function to run program.
    Takes in command line arguments and calls functions
    """

    #Specify an error log file
    error_log_file = "C:\\Python\\daq\\logs\\_initialize_logger_error.txt"
    sys.stderr = open(error_log_file, 'w')

    #Create dictionary with configuration file locations for all configured instruments
    config_file_dic = process_instrument_list() 

    #Make a program start-up statement
    print_string = '\n'.join([
        'JAQFactory Initializer',
        '\nWelcome to JAQFactory Initializer!',
        '\nReview which instruments are enabled and disabled.\n'
        ])
    
    #Clear console and print start-up information
    os.system('cls')
    print(print_string)
    EnableState_df = create_EnableState_df(config_file_dic)
    print(EnableState_df)

    #Print user input messages
    print_string = '\n'.join([
        '\nWould you like to enable or disable an instrument?',
        '\nIf no, press enter.',
        'If you would like to enable an instrument, enter "enable Instrument Name".',
        'If you would like to disable an instrument, enter "disable Instrument Name".',
        'After enabling or disabling an instrument, you will be prompted with the option to enable or disable another instrument.\n'
        ])
    print(print_string)
    
    #Wait for and process user input
    user_command = input()
    user_command_loop(user_command, config_file_dic)

    #Print messages for terminating program
    print_string = '\n'.join([
        'JAQFactory Initializer',
        '\nInstruments will be enabled as followed:'
        ])
    os.system('cls')
    print(print_string)
    EnableState_df = create_EnableState_df(config_file_dic)
    print(EnableState_df)
    print_string = '\n'.join([
        '\nOpening JAQFactory Manager'
        ])
    print(print_string)
    time.sleep(3)

if __name__ == '__main__':
    main()
