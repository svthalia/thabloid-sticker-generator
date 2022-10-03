import pandas as pd
import os
import util
from checker import check_entries
from pdf import generate_pdf

authors = ['Lars Jeurissen']
version = '1.0'

program_art = '''  _______ _           _     _       _     _      
 |__   __| |         | |   | |     (_)   | |     
    | |  | |__   __ _| |__ | | ___  _  __| |     
    | |  | '_ \\ / _` | '_ \\| |/ _ \\| |/ _` |     
    | |  | | | | (_| | |_) | | (_) | | (_| |     
   _|_|_ |_| |_|\\__,_|_.__/|_|\\___/|_|\\__,_|     
  / ____| | (_)    | |                           
 | (___ | |_ _  ___| | _____ _ __                
  \\___ \\| __| |/ __| |/ / _ \\ '__|               
  ____) | |_| | (__|   <  __/ |                  
 |_____/ \\__|_|\\___|_|\\_\\___|_|    _             
  / ____|                         | |            
 | |  __  ___ _ __   ___ _ __ __ _| |_ ___  _ __ 
 | | |_ |/ _ \\ '_ \\ / _ \\ '__/ _` | __/ _ \\| '__|
 | |__| |  __/ | | |  __/ | | (_| | || (_) | |   
  \\_____|\\___|_| |_|\\___|_|  \\__,_|\\__\\___/|_|

Running Thabloid Sticker Generator v{} by {}
-------------------------------------------------------------------------------'''


def read_input(input_dir):
    input("Put all address files (.csv) that you want to process in the 'input' folder. Press enter when done.")
    csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_dir)))
    while len(csvs) <= 0:
        input("No .csv files detected. Press enter when you have added them.")
        csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_dir)))

    print("Parsing {} input files..".format(len(csvs)))
    column_names = ['first_name', 'last_name', 'address', 'address_2', 'postal_code', 'city', 'country']

    erroneous_lines = []
    input_data = pd.concat([pd.read_csv(os.path.join(input_dir, csv), header=0, names=column_names,
                                        engine='python', on_bad_lines=lambda ln: erroneous_lines.append(",".join(ln)),
                                        keep_default_na=False) for csv in csvs]).drop_duplicates()
    if len(erroneous_lines) > 0:
        print("----------")
        print("Encountered {} erroneous line(s) in the input csv file(s):".format(len(erroneous_lines)))
        print(*erroneous_lines, sep="\n")
        print("----------")
        exit_program = '.'
        while exit_program != '' and exit_program != 'y' and exit_program != 'n':
            exit_program = input("We will continue with the remaining entries if you don't exit. "
                                 "Do you want to exit? (Y/n)").lower()
        if exit_program != 'n':
            exit(0)

    print("Read {} data entries".format(len(input_data)))
    return input_data


if __name__ == "__main__":
    print(program_art.format(version, ", ".join(authors)))

    input_dir = 'input'
    output_dir = 'output'
    if not os.path.exists(input_dir):
        os.mkdir(input_dir)
    if os.path.exists(output_dir):
        while len(os.listdir(output_dir)) != 0:
            input("The 'output' directory is not empty, please delete its contents. Press enter when done.")
    else:
        os.mkdir(output_dir)

    entries = read_input(input_dir)
    check_entries_input = input("Entries can be checked and corrected using the Google Maps API. "
                                "Do you want to do this? (Y/n)").lower()
    while len(check_entries_input) != 0 and check_entries_input != 'y' and check_entries_input != 'n':
        check_entries_input = input("Do you want to check entries using the Google Maps API? (Y/n)")

    if len(check_entries_input) == 0 or check_entries_input == 'y':
        entries = check_entries(entries)

    generate_pdf(entries, os.path.join(output_dir, "sticker_sheet.pdf"))
