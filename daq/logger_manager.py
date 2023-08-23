"""
Author: Jack Connor 
Date Created: 2/19/2021
Last Modified: 1/26/2023
"""

import os
import sys
import time

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

def create_enabled_instrument_list(config_file_dic):
    """
    Reads all instrument config files in config_file_dic and saves enabled instruments to a list
    Args:
        config_file_dic (dict): dictionary of instrument configuration files created from process_instrument_list()
    Returns:
        enabled_instrument_list (list): list of enabled instruments
    """
    enabled_instrument_list = []
    for instrument in config_file_dic:
        config = read_daq_config(config_file_dic[instrument])
        if config['Enabled']:
            enabled_instrument_list += [instrument]
    return enabled_instrument_list

def print_data_line(config):
    """
    Searches instrument output directory for most recent file and prints last line from that file
    Args:
        config (dict): instrument configuration dictionary
    Returns:
        Prints most recent dataline to console
    """
    data_dir = config['Output Directory']
    list_of_files = os.listdir(data_dir)
    i = 0
    for f in list_of_files:
        list_of_files[i] = data_dir + '\\' + f
        i += 1
    latest_file = max(list_of_files, key=os.path.getctime)
    if latest_file[-4:] == ".dat":
        try:
            with open(latest_file, 'r') as f:
                for line in f:
                    pass
                last_line = line
        except:
            last_line = "Last lined pulled by parser. Try again."
    else:
        last_line = "Last lined pulled by parser. Try again."
    print_string = '\n'.join([
        'JAQFactory Manager',
        f'\nLast Recorded Dataline for {config["Instrument Name"]}:\n',
        ])
    print(print_string)
    if config["Header String"] != None:
        print(config["Header String"])
    print(last_line),

def write_logger_state(state = 'Run'):
    """
    Writes logger state 'Run' or 'Quit' to logger state file.
    Args:
        state (str): logger state to write ('Run' or 'Quit')
    Returns:
        Writes state to logger state file.
        If state is 'Quit', runs one minute countdown with quit messages
    """
    logger_state_file = 'C:\\Python\\daq\\logger_state\\logger_state.txt'
    with open(logger_state_file, 'w') as f:
        f.write(state)
    if state == 'Quit':
        count_down_list = list(range(1,61))
        for element in count_down_list:
            os.system('cls')
            print_string = '\n'.join([
                'JAQFactory Manager',
                '\nLogger quit initiated.',
                f'All loggers will shutdown in {count_down_list[-element]} seconds.\n'
                ])
            print(print_string)
            time.sleep(1)
        print_string = '\n'.join([
            'JAQFactory Manager',
            '\nAll loggers have shut down. Logging Terminated.',
            '\nTo reinitialize logging, use JAQFactory Initializer on the Desktop.'
            ])
        os.system('cls')
        print(print_string)
        time.sleep(3)

def main():
    """
    Main function to run program.
    Loops waiting for user commands.
    Processes user commands. Breaks loop if command is 'Quit'.
    """

    #Specify an error log file
    error_log_file = "C:\\Python\\daq\\logs\\_logger_manager_error.txt"
    sys.stderr = open(error_log_file, 'w')

    os.system('cls')

    #Create a list of enabled instruments
    config_file_dic = process_instrument_list() 
    enabled_instrument_list = create_enabled_instrument_list(config_file_dic) 

    #Intitialize manager and print start-up messages
    print_string_list_1 = [
            'JAQFactory Manager',
            '\nWelcome to JAQFactory Manager!',
            '\nNOTE: Stopping JAQFactory Manager will not stop loggers. Loggers can be stopped with the "Quit" command,',
            'or by ending background Python processes in Task Manager. If you close JAQFactory Manager, you can reopen',
        'it from the Desktop.',
            '\nTo view an instrument\'s last recorded dataline, enter the instrument name. Valid instrument names include:']
    print_string_list_2 = [
            '\nTo end all logging processes, type "Quit"\n'
            ]
    welcome_string_list = print_string_list_1 + enabled_instrument_list + print_string_list_2
    write_logger_state()
    print('\n'.join(welcome_string_list))

    #Wait for and process user input
    user_command = input()
    while user_command != 'Quit':
        if user_command in config_file_dic:
            os.system('cls')
            config = read_daq_config(config_file_dic[user_command])
            print_data_line(config)
            print('\n'.join(welcome_string_list[2:]))
            user_command = input()
        else:
            print('Invalid Command\n')
            user_command = input()
    
    #Shut down loggers
    write_logger_state('Quit')

if __name__ == '__main__':
    main()
