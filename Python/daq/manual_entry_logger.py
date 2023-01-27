import serial
import time
import datetime
import msvcrt
import os
import pandas as pd
from os import path

def get_date_string():
    Y = str(datetime.datetime.now().year)
    m =str(datetime.datetime.now().month)
    d =str(datetime.datetime.now().day)

    if datetime.datetime.now().month < 10:
        _m = "0"
    else:
        _m = ""

    if datetime.datetime.now().day < 10:
        _d = "0"
    else:
        _d = ""
    date_string = Y + _m + m + _d + d
    return date_string

def get_timestamp(current_time):
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

def logger(writeFile):
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
    import argparse

    parser = argparse.ArgumentParser(description='COM and Data Writing Settings')
    parser.add_argument('-d', '--write_dir', type=str, help='Directory to save datafile', default='C:\\Python\\daq\\data\\Manual Logger')
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
