"""
Author: Jack Connor
Date Created: Unknown
Last Modified: 8/23/2023
"""

import serial
import time
import datetime
import msvcrt
import os
import pandas as pd
from os import path

def get_date_string():
    """
    Generate date string for use in file names.
    Args:
        None
    Returns:
        date_string (str): date string of format %Y%m%d
    """
    current_time = datetime.datetime.now()
    date_string = datetime.datetime.strftime(current_time, "%Y%m%d") 
    return date_string

def get_timestamp(current_time):
    """
    Uses clock to make a timestamp
    Args:
        current_time (datetime.datetime): datetime object representing current time
    Returns:
        string containing timestamp
    """
    return datetime.datetime.strftime(current_time, "%Y-%m-%d %H:%M:%S")

def logger(writeFile):
    """
    Runs loop to process user input and write data when input is provided.
    Args:
        writeFile (str): path to write data when input is provided
    Returns:
        Writes data to writeFile and notifies user of recorded data
    """
    i = 0
    loop = True
    dic = {'Timestamp': ['None'], 'Value': ['None']} 
    print('Press Enter to initiate logger.\n')
    cmd = input()
    while cmd != '':
        print('Press Enter to initiate logger.\n')
        cmd = input()
    time.sleep(1)
    while loop:
        os.system('cls')
        print('Manual Entry Logger\n\n'\
                'Logged Values')
        print(pd.DataFrame(dic).to_string(index = False))
        print('\nType value and press enter to make a log entry. To exit, type "Quit" and press enter.')
        value = input()
        if value == 'Quit':
            break
        elif value.find(',') >= 0:
            value = f'"{value}"'
        ts = get_timestamp(datetime.datetime.now())
        if i == 0:
            dic = {'Timestamp': [], 'Value': []} 
            if not os.path.exists(writeFile):
                rows = ['Timestamp,Value\n',
                        f'{ts},{value}\n']
            else:
                rows = [f'{ts},{value}\n']
            i += 1
        else:
            rows = [f'{ts},{value}\n']
        with open(writeFile, 'a') as f:
            for row in rows:
                f.write(row)
        dic['Timestamp'] += [ts]
        dic['Value'] += [value]

def main():
    """
    Processes command line arguments and calls functions to run the manual data entry program.
    """
    import argparse

    #Identify working directory
    working_dir = os.getcwd()

    parser = argparse.ArgumentParser(description='COM and Data Writing Settings')
    parser.add_argument('-d', '--write_dir', type=str, help='Directory to save datafile', default= working_dir + '\\data\\Manual Logger')
    args = parser.parse_args()

    write_directory = args.write_dir

    datestring = get_date_string()
    file_prefix = write_directory + '\\' + datestring

    os.system('cls')
    print('Manual Entry Logger\n\n'\
            'Welcome to Manual Entry Logger!\n\n'\
            f'The write file name will take the form of {file_prefix}_{{Suffix}}.csv\n'\
            'Enter a file suffix')
    suffix = input()
    writeFile = f'{file_prefix}_{suffix}.csv'
    print("\nCreating new file: " +  writeFile + '\n')

    logger(writeFile)

if __name__ == '__main__':
    main()
