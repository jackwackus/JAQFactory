"""
Author: Jack Connor
Date Created: 9/13/2021
Last Modified: 1/26/2023
"""

import os
import time
from logger import process_instrument_list

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

    os.system('cls')
    if instrument in config_file_dic:
        print(f'Initializing logger restart for {instrument}.')
        time.sleep(1)
        print(f'{instrument} logger restart initialized.')
        time.sleep(2)
    else:
        print("\nUnsupported instrument name. The following instruments are supported and must be typed as displayed:\n")
        for instrument in config_file_dic:
            print(instrument)
        time.sleep(2)

if __name__ == '__main__':
    main()
