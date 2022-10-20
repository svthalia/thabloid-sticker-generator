import pandas as pd
import os
import unicodedata
from util import query_yes_no
from checker import correct_entries
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


def read_input(input_directory):
    input("Put all address files (.csv) that you want to process in the 'input' folder. Press enter when done.")
    csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_directory)))
    while len(csvs) <= 0:
        input("No .csv files detected. Press enter when you have added them.")
        csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_directory)))

    print(f"Parsing {len(csvs)} input file(s)..")
    column_names = ['first_name', 'last_name', 'address', 'address_2', 'postal_code', 'city', 'country']

    erroneous_lines = []
    input_data = pd.concat([pd.read_csv(os.path.join(input_directory, csv), header=0, names=column_names,
                                        engine='python', on_bad_lines=lambda ln: erroneous_lines.append(",".join(ln)),
                                        keep_default_na=False) for csv in csvs]).drop_duplicates()
    input_data.reset_index(drop=True, inplace=True)
    if len(erroneous_lines) > 0:
        print("----------")
        print(f"Encountered {len(erroneous_lines)} erroneous line(s) in the input csv file(s):")
        print(*erroneous_lines, sep="\n")
        print("----------")

        if query_yes_no("We will continue with the remaining entries if you don't exit. Do you want to exit?", "yes"):
            exit(0)

    print(f"Read {len(input_data)} data entries")
    return input_data


def format_entries(input_entries):
    for i, entry in input_entries.iterrows():
        # Convert german s to double s
        entry['address'] = entry['address'].replace(u'\xdf', 'ss')
        entry['address_2'] = entry['address_2'].replace(u'\xdf', 'ss')
        entry['city'] = entry['city'].replace(u'\xdf', 'ss')
        # Format to ascii
        entry['address'] = unicodedata.normalize('NFKD', entry['address']).encode('ascii', 'ignore').decode("ascii")
        entry['address_2'] = unicodedata.normalize('NFKD', entry['address_2']).encode('ascii', 'ignore').decode("ascii")
        entry['city'] = unicodedata.normalize('NFKD', entry['city']).encode('ascii', 'ignore').decode("ascii")
        entry['postal_code'] = entry['postal_code'].upper()


def post_process_entries(input_entries):
    # Do post-processing that PostNL requests
    # see https://www.postnl.nl/versturen/brief-of-kaart-versturen/hoe-verstuur-ik-een-brief-of-kaart/brief-adresseren/
    for i, entry in input_entries.iterrows():
        if entry["country"] == "Netherlands" and len(entry["postal_code"]) == 6:
            entry["postal_code"] = f"{entry['postal_code'][:4]} {entry['postal_code'][4:]}"
        entry["city"] = entry["city"].upper()
        entry["country"] = entry["country"].upper()
        # Format german s
        entry['address'] = entry['address'].replace(u'\xdf', 'ss')
        entry['address_2'] = entry['address_2'].replace(u'\xdf', 'ss')
        entry['city'] = entry['city'].replace(u'\xdf', 'ss')


if __name__ == "__main__":
    # Print introduction
    print(program_art.format(version, ", ".join(authors)))

    # Validate input and output directories
    input_dir = 'input'
    output_dir = 'output'
    if not os.path.exists(input_dir):
        os.mkdir(input_dir)
    while os.path.exists(output_dir) and os.listdir(output_dir):
        input("The 'output' directory is not empty, please delete its contents. Press enter when done.")
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # Read the input from the input directory
    entries = read_input(input_dir)

    # Do some basic entry formatting
    format_entries(entries)

    # Optional: Check entries in the Google Maps API
    if query_yes_no("Entries can be checked and corrected using various APIs. Do you want to do this?", "yes"):
        no_invalid, no_changed = correct_entries(entries, output_dir)
        print(f"Number of invalid addresses: {no_invalid}")
        print(f"Number of changed addresses: {no_changed}")

    # Apply postprocessing to the entries
    post_process_entries(entries)

    # Generate the output PDF
    generate_pdf(entries, os.path.join(output_dir, "sticker_sheet.pdf"))

    print("Generation complete! Thank you for using the amazing Thabloid Sticker Generator, see you in a few months!")
