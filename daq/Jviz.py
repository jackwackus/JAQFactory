"""
Author: Jack Connor 
Date Created: 3/22/2021
Last Modified: 8/23/2023
"""

import os
import sys
import time
import datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator, NullFormatter)

def read_daq_config(read_file = 'C:\\JAQFactory\\daq\\config\\G2401.txt'):
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

def create_metric_viz_list(user_command, Jviz_config):
    """
    Creates a list of metrics to visualize based on user input.
    Does not allow visualization of more than 3 metrics at a time.
    Args:
        user_command (str): string containing first instrument name
        Jviz_config (dict): Jviz configuration dictionary indicating which data columns to read for configured instruments
    Returns:
        metric_viz_list (list): list of metrics to visualize
            contains tuples formatted: (instrument, parameter)
    """
    metric_viz_list = []
    i = 1
    while i < 4:
        if user_command in Jviz_config:
            instrument = user_command
            parameters_dic = Jviz_config[instrument]
            print(f'\nChoose a {instrument} parameter to visualize on plot {i}.' \
                    '\n\nAvailable parameters include:')
            for parameter in parameters_dic:
                print(parameter)
            print()
            instrument_parameter = input()
            if instrument_parameter in parameters_dic:
                metric_viz_list += [(instrument, instrument_parameter)]
                i += 1
            elif instrument_parameter == 'Quit':
                sys.exit()
            else:
                print('\nInvalid parameter. Try again.\n')
                continue
        elif user_command == '':
            return metric_viz_list
        elif user_command == 'Quit':
            sys.exit()
        else:
            print('\nInvalid instrument name. Try again.')
            time.sleep(1)
        if i < 4:
            os.system('cls')
            print(f'Choose an instrument to visualize on plot {i}.' \
                    '\n\nAvailable instruments include:')
            for instrument in Jviz_config:
                if instrument != 'Plot Frequency':
                    print(instrument)
            print('\nYou may press enter if you are done adding plots.\n')
            user_command = input()
    return metric_viz_list

def create_instrument_configs(metric_viz_list, config_path = "C:\\Python\\daq\\config\\"):
    """
    Creates dictionary containing instrument configuration dictionaries for all instruments to visualize.
    Args:
        metric_viz_list (list): list of metrics to visualize, created by create_metric_viz_list
        config_path (str): configuration file directory
    Returns:
        instrument_configs (dict): dictionary of instrument configuration dictionaries keyed by instrument
    """
    instrument_configs = {}
    for instrument in metric_viz_list:
        config_file_path = f'{config_path}{instrument[0]}.txt'
        instrument_configs[instrument[0]] = read_daq_config(config_file_path)
    return instrument_configs

def pull_last_data_line(config, recursion_depth = 0):
    """
    Searches instrument output directory for most recent file and pulls last line from that file.
    Args:
        config (dict): instrument configuration dictionary
        recursion_depth (int): number of times function has been called recursively
    Returns:
        last_line (str): last recorded dataline for instrument
    """
    data_dir = config['Output Directory']
    list_of_files = os.listdir(data_dir)
    i = 0
    for f in list_of_files:
        list_of_files[i] = data_dir + '\\' + f
        i += 1
    try:
        latest_file = max(list_of_files, key=os.path.getctime)
    except FileNotFoundError:
        #print('no file')
        recursion_depth += 1
        if recursion_depth < 977:
            time.sleep(0.5)
            return pull_last_data_line(config, recursion_depth)
        else:
            return None
    if latest_file[-4:] == ".dat":
        try:
            with open(latest_file, 'r') as f:
                for line in f:
                    pass
                last_line = line
        except:
            return None
    else:
        #print('no file')
        recursion_depth += 1
        if recursion_depth < 977:
            time.sleep(0.5)
            return pull_last_data_line(config, recursion_depth)
        else:
            return None
    return last_line

def parse_data_line(line, delimiter, data_index):
    """
    Parses dataline to obtain timestamp and data value specified by Jviz configuration file.
    Args:
        line (str): last recorded dataline for instrument
        delimiter (str): delimiter used to parse line, from config
        data_index (int): index of desired data parameter, from Jviz_config
    Returns:
        time (str): string containing time from timestamp in line
        data_value (str): value pulled from data_index in line
    """
    data_list = []
    delimiter_index = line.find(delimiter)
    while delimiter_index  >= 0:
        data_list += [line[:delimiter_index]]
        line = line[delimiter_index+1:]
        delimiter_index = line.find(delimiter)
    data_list += [line]
    if delimiter == ' ':
        time = data_list[2]
    else:
        time = data_list[1][data_list[1].find(' ')+1:]
    data_value = round(float(data_list[data_index]),2)
    return time, data_value

def run_viz(metric_viz_list, Jviz_config):
    """
    Runs visualization function and prints corresponding console messages.
    Args:
        metric_viz_list (list): list of metrics to visualize, created by create_metric_viz_list
        Jviz_config (dict): Jviz configuration dictionary indicating which data columns to read for configured instruments
    Returns:
        prints messages and runs visualize
    """
    plotting_message_string = '\n'.join([
        'Jviz',
        f'\nDashboard will open when data is available. Selected Plots:'
        ])
    os.system('cls')
    print('Input the number of minutes you would like to be plotted.\n')
    n_seconds = None
    while n_seconds == None:
        try:
            n_seconds = int(float(input())*60)
        except:
            print('\nInvalid input. Try again.\n')
            continue
    os.system('cls')
    print(plotting_message_string)
    for instrument in metric_viz_list:
        metric = instrument[0] + ' ' + instrument[1]
        print(metric)
    print()
    visualize(metric_viz_list, Jviz_config, n_seconds)

def visualize(metric_viz_list, Jviz_config, time_window_size):
    """
    Sets up visualization plots and animates them with realtime data.
    Args:
        metric_viz_list (list): list of metrics to visualize, created by create_metric_viz_list
        Jviz_config (dict): Jviz configuration dictionary indicating which data columns to read for configured instruments
    Returns:
        displays animated visualization plots
    """

    #Establish working directory
    working_dir = os.getcwd()

    #Obtain instrument configurations
    instrument_configs = create_instrument_configs(metric_viz_list, config_path = working_dir + '\\config\\')

    #Establish number of plots variable
    n_plots = len(metric_viz_list)

    #Create plot_dict to store plotting variables
    #Initialize figures and add subplots, stored as values in plot_dict
    fig = plt.figure()
    i = 1
    plot_dict = {}
    for instrument in metric_viz_list:
        metric = instrument[0] + ' ' + instrument[1]
        plot_dict[metric] = {'x': [], 'y': [], 'Plot': fig.add_subplot(n_plots, 1, i)}
        i += 1

    #Plot first values before animation starts
    def plot_first_frame(plot_dict, instrument_configs):
        """
        Sets up intitial frame of plots for animation
        Args:
            plot_dict (dict): dictionary containing instrument subplots
            instrument_configs (dict): dictionary of instrument configuration dictionaries
        Returns:
            plot_dict (dict): dictionary containing instrument subplots

        """
        #Establish an instrument number to be updated for each instrument in Instrument Plotting Loop
        n_inst = 1

        #Establish color list for plotting each instrument
        color_list = ['r', 'y', 'g']

        #Instrument Plotting Loop
        #Loop through each metric, update plot with most recent data values
        for element in metric_viz_list:
            instrument = element[0]
            parameter = element[1]
            metric = instrument + ' ' + parameter
            #Pull most recent instrument data, attempt to parse
            #If error, update time and copy previous data value
            config = instrument_configs[instrument]
            print(f'Waiting for first {instrument} {parameter} data point.')
            data_line = pull_last_data_line(config)
            try:
                x, y = parse_data_line(data_line, config['Delimiter'], Jviz_config[instrument][parameter])
                print(f'First {instrument} {parameter} data point found.')
            except:
                print(f'No {instrument} {parameter} data found. Initializing plots with exception.')
                x = '00:00:00'
                y = 0

            #Set plot window length based on plotting frequency and user input
            plot_window = int(time_window_size/Jviz_config['Plot Frequency'])
            major_TickInterval = int(plot_window)/10

            #Update x and y lists with most recent data, limit list lengths to 60
            plot_dict[metric]['x'].append(x)
            plot_dict[metric]['y'].append(y)
            plot_dict[metric]['x'] = plot_dict[metric]['x'][-plot_window:]
            plot_dict[metric]['y'] = plot_dict[metric]['y'][-plot_window:]

            #Update plot
            plot_dict[metric]['Plot'].clear()
            plot_dict[metric]['Plot'].plot(
                    plot_dict[metric]['x'],
                    plot_dict[metric]['y'],
                    linestyle = '-',
                    marker = '.',
                    color=color_list[n_inst-1])

            #Reset plot formatting
            plot_dict[metric]['Plot'].ticklabel_format(axis='y', style='plain', useOffset=False)
            plot_dict[metric]['Plot'].set_ylabel(metric)
            if n_inst < n_plots:
                plot_dict[metric]['Plot'].xaxis.set_major_locator(MultipleLocator(major_TickInterval))
                plot_dict[metric]['Plot'].xaxis.set_major_formatter(NullFormatter())
                plot_dict[metric]['Plot'].xaxis.set_minor_locator(MultipleLocator(1))
                if n_inst == 1:
                    plot_dict[metric]['Plot'].set_title('Dashboard')
            else:
                plot_dict[metric]['Plot'].xaxis.set_major_locator(MultipleLocator(major_TickInterval))
                plot_dict[metric]['Plot'].tick_params(axis='x', labelrotation=45)
                plot_dict[metric]['Plot'].xaxis.set_minor_locator(MultipleLocator(1))
                if n_plots == 1:
                    plot_dict[metric]['Plot'].set_title('Dashboard')

            #Step n_inst
            n_inst += 1
        print('\nDashboard now open.\nExit dashboard to change plots or quit program.')
        return plot_dict

    plot_dict = plot_first_frame(plot_dict, instrument_configs)

    #Set plot update interval. This should be the data frequency of the slowest instrument.
    plot_update_interval = Jviz_config['Plot Frequency']*1000

    #FuncAnimate works better with init function
    def init():
        return

    #Define a function to animate plots
    def animate(i, plot_dict, instrument_configs):
        """
        Every iteration, pulls and plots most recent instrument data values for each instrument.
        Will be looped by matplotlib.animation.FuncAnimation to animate data visualization plots.
        Args:
            i (int): animation frame number initialized and used by matplotlib.animation.FuncAnimation
            plot_dict (dict): dictionary containing instrument subplots
            instrument_configs (dict): dictionary of instrument configuration dictionaries
        Returns:
            updates plots with most recent data in realtime
        """
       
        #Establish an instrument number to be updated for each instrument in Instrument Plotting Loop
        n_inst = 1

        #Establish color list for plotting each instrument
        color_list = ['r', 'y', 'g']

        #Instrument Plotting Loop
        #Loop through each metric, update plot with most recent data values
        for element in metric_viz_list:
            instrument = element[0]
            parameter = element[1]
            metric = instrument + ' ' + parameter
            #Pull most recent instrument data, attempt to parse
            #If error, update time and copy previous data value
            config = instrument_configs[instrument]
            data_line = pull_last_data_line(config)
            try:
                x, y = parse_data_line(data_line, config['Delimiter'], Jviz_config[instrument][parameter])
            except:
                last_dt = datetime.datetime.strptime(plot_dict[metric]['x'][-1], '%H:%M:%S')
                new_dt = last_dt + datetime.timedelta(seconds = 1)
                x = new_dt.strftime('%H:%M:%S')
                y = plot_dict[metric]['y'][-1]

            #Set plot window length based on plotting frequency and user input
            plot_window = int(time_window_size/Jviz_config['Plot Frequency'])
            major_TickInterval = int(plot_window)/10

            #Update x and y lists with most recent data, limit list lengths to 60
            plot_dict[metric]['x'].append(x)
            plot_dict[metric]['y'].append(y)
            plot_dict[metric]['x'] = plot_dict[metric]['x'][-plot_window:]
            plot_dict[metric]['y'] = plot_dict[metric]['y'][-plot_window:]

            #Update plot
            plot_dict[metric]['Plot'].clear()
            plot_dict[metric]['Plot'].plot(
                    plot_dict[metric]['x'],
                    plot_dict[metric]['y'],
                    linestyle = '-',
                    marker = '.',
                    color=color_list[n_inst-1])

            #Reset plot formatting
            plot_dict[metric]['Plot'].ticklabel_format(axis='y', style='plain', useOffset=False)
            plot_dict[metric]['Plot'].set_ylabel(metric)
            if n_inst < n_plots:
                plot_dict[metric]['Plot'].xaxis.set_major_locator(MultipleLocator(major_TickInterval))
                plot_dict[metric]['Plot'].xaxis.set_major_formatter(NullFormatter())
                plot_dict[metric]['Plot'].xaxis.set_minor_locator(MultipleLocator(1))
                if n_inst == 1:
                    plot_dict[metric]['Plot'].set_title('Dashboard')
            else:
                plot_dict[metric]['Plot'].xaxis.set_major_locator(MultipleLocator(major_TickInterval))
                plot_dict[metric]['Plot'].tick_params(axis='x', labelrotation=45)
                plot_dict[metric]['Plot'].xaxis.set_minor_locator(MultipleLocator(1))
                if n_plots == 1:
                    plot_dict[metric]['Plot'].set_title('Dashboard')

            #Step n_inst
            n_inst += 1

    #Run matplotlib function that iterates through animate function at specified time interval
    ani = animation.FuncAnimation(fig, animate, init_func = init, fargs=(plot_dict, instrument_configs), interval=plot_update_interval, cache_frame_data=False)

    #Display figure
    plt.show()

def main():
    """
    Main function to run program.
    """

    os.system('cls')

    #Establish working directory
    working_dir = os.getcwd()

    #Establish important data objects
    config_file_dic = process_instrument_list(working_dir + '\\config\\')
    Jviz_config = read_daq_config(read_file = working_dir + '\\config\\Jviz.txt') 
    configured_instrument_list = []
    for element in Jviz_config:
        if element != 'Plot Frequency':
            configured_instrument_list += [element]

    #Print start-up message to console
    print_string_list_1 = [
            'Jviz',
            '\nWelcome to Jviz!',
            'You may visualize up to 3 data streams simultaneously.',
            'Enter an instrument name for the first plot.',
            '\nConfigured instruments include:']
    welcome_string_list = print_string_list_1 + configured_instrument_list + ['\nType Quit to exit program.\n']
    print('\n'.join(welcome_string_list))

    #Generate compatible metric_viz_list
    metric_viz_list = []
    while len(metric_viz_list) == 0:
        user_command = input()
        if user_command == 'Quit':
            break
        elif user_command not in configured_instrument_list:
            print('\nInvalid command. Try again\n')
            continue
        metric_viz_list = create_metric_viz_list(user_command, Jviz_config)

    #Run loop that allows user to switch between plots until entering quit command
    while user_command != 'Quit':
        run_viz(metric_viz_list, Jviz_config) 
        os.system('cls')
        print('\n'.join(welcome_string_list))
        metric_viz_list = None
        while metric_viz_list == None:
            user_command = input()
            if user_command == 'Quit':
                break
            elif user_command not in configured_instrument_list:
                print('\nInvalid command. Try again\n')
                continue
            metric_viz_list = create_metric_viz_list(user_command, Jviz_config)

if __name__ == '__main__':
    main()
