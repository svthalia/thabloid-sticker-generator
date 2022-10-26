"""
Main file, entrypoint for the application.
"""

import sys
import os
import unicodedata
import pandas as pd
from util import query_yes_no
from checker import correct_entries
from pdf import generate_pdf

AUTHORS = ['Lars Jeurissen']
VERSION = '1.0'
PROGRAM_ART = ('  _______ _           _     _       _     _      \n'
               ' |__   __| |         | |   | |     (_)   | |     \n'
               '    | |  | |__   __ _| |__ | | ___  _  __| |     \n'
               '    | |  | \'_ \\ / _` | \'_ \\| |/ _ \\| |/ _` |     \n'
               '    | |  | | | | (_| | |_) | | (_) | | (_| |     \n'
               '   _|_|_ |_| |_|\\__,_|_.__/|_|\\___/|_|\\__,_|     \n'
               '  / ____| | (_)    | |                           \n'
               ' | (___ | |_ _  ___| | _____ _ __                \n'
               '  \\___ \\| __| |/ __| |/ / _ \\ \'__|               \n'
               '  ____) | |_| | (__|   <  __/ |                  \n'
               ' |_____/ \\__|_|\\___|_|\\_\\___|_|    _             \n'
               '  / ____|                         | |            \n'
               ' | |  __  ___ _ __   ___ _ __ __ _| |_ ___  _ __ \n'
               ' | | |_ |/ _ \\ \'_ \\ / _ \\ \'__/ _` | __/ _ \\| \'__|\n'
               ' | |__| |  __/ | | |  __/ | | (_| | || (_) | |   \n'
               '  \\_____|\\___|_| |_|\\___|_|  \\__,_|\\__\\___/|_|\n'
               '\n'
               'Running Thabloid Sticker Generator v{} by {}\n'
               '-------------------------------------------------------------------------------')


def read_input(input_directory: str) -> pd.DataFrame:
    """
    Reads input CSV files from the given input directory and converts them to a DataFrame.
    Invalid lines will be collected. If any invalid lines are encountered, the user will be
    prompted on whether they want to continue.

    Parameters
    ----------
    input_directory: str
        The input directory where the CSV files are stored

    Returns
    -------
    pd.DataFrame:
        A DataFrame containing all correct CSV file entries
    """
    # Read the CSV files
    input("Put all address files (.csv) that you want to process in the 'input' folder. "
          "Press enter when done.")
    csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_directory)))
    while len(csvs) <= 0:
        input("No .csv files detected. Press enter when you have added them.")
        csvs = list(filter(lambda file: file.endswith('.csv'), os.listdir(input_directory)))

    # Parse the CSV files into a pandas dataframe
    print(f"Parsing {len(csvs)} input file(s)..")
    column_names = ['first_name', 'last_name', 'address',
                    'address_2', 'postal_code', 'city', 'country']

    erroneous_lines = []
    input_data = pd.concat([pd.read_csv(os.path.join(input_directory, csv), header=0,
                                        names=column_names, engine='python',
                                        on_bad_lines=lambda l: erroneous_lines.append(','.join(l)),
                                        keep_default_na=False) for csv in csvs]).drop_duplicates()
    # Re-index the dataframe so that we don't have double indices
    input_data.reset_index(drop=True, inplace=True)
    # If there are erroneous lines, prompt the user to ask if they want to continue
    if len(erroneous_lines) > 0:
        print("----------")
        print(f"Encountered {len(erroneous_lines)} erroneous line(s) in the input csv file(s):")
        print(*erroneous_lines, sep="\n")
        print("----------")

        if query_yes_no("We will continue with the remaining entries if you don't exit. "
                        "Do you want to exit?", "yes"):
            sys.exit(0)

    print(f"Read {len(input_data)} data entries")
    return input_data


def format_entries(input_entries: pd.DataFrame):
    """
    Formats input entries in-place so that the rest of the application can use correct data.
    German s'es are converted to two s'es and the data is ascii-encoded

    Parameters
    ----------
    input_entries: pd.DataFrame
        The input entries to be formatted, stored in a dataframe
    """
    for _, entry in input_entries.iterrows():
        # Convert german s to double s
        entry['address'] = entry['address'].replace('\xdf', 'ss')
        entry['address_2'] = entry['address_2'].replace('\xdf', 'ss')
        entry['city'] = entry['city'].replace('\xdf', 'ss')
        # Format to ascii
        entry['address'] = unicodedata.normalize('NFKD', entry['address']).encode('ascii', 'ignore').decode("ascii")
        entry['address_2'] = unicodedata.normalize('NFKD', entry['address_2']).encode('ascii', 'ignore').decode("ascii")
        entry['city'] = unicodedata.normalize('NFKD', entry['city']).encode('ascii', 'ignore').decode("ascii")
        entry['postal_code'] = entry['postal_code'].upper()


def post_process_entries(input_entries: pd.DataFrame):
    """
    Post-processes the entries in-place, so that they are converted to a format that PostNL accepts.
    See: https://www.postnl.nl/versturen/brief-of-kaart-versturen/hoe-verstuur-ik-een-brief-of-kaart/brief-adresseren/

    Parameters
    ----------
    input_entries: pd.DataFrame
        The input entries to be post-processed, stored in a dataframe
    """
    for _, entry in input_entries.iterrows():
        # Format Dutch postal codes
        if entry["country"] == "Netherlands" and len(entry["postal_code"]) == 6:
            entry["postal_code"] = f"{entry['postal_code'][:4]} {entry['postal_code'][4:]}"
        # Uppercase cities and countries
        entry["city"] = entry["city"].upper()
        entry["country"] = entry["country"].upper()
        # Format german s
        entry['address'] = entry['address'].replace('\xdf', 'ss')
        entry['address_2'] = entry['address_2'].replace('\xdf', 'ss')
        entry['city'] = entry['city'].replace('\xdf', 'ss')


if __name__ == "__main__":
    # Print introduction
    print(PROGRAM_ART.format(VERSION, ", ".join(AUTHORS)))

    # Validate input and output directories
    INPUT_DIR = 'input'
    OUTPUT_DIR = 'output'
    if not os.path.exists(INPUT_DIR):
        os.mkdir(INPUT_DIR)
    while os.path.exists(OUTPUT_DIR) and os.listdir(OUTPUT_DIR):
        input("The 'output' directory is not empty, please delete its contents. "
              "Press enter when done.")
    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    # Read the input from the input directory
    entries = read_input(INPUT_DIR)

    # Do some basic entry formatting
    format_entries(entries)

    # Optional: Check entries in the Google Maps API
    if query_yes_no("Entries can be checked and corrected using various APIs. "
                    "Do you want to do this?", "yes"):
        no_invalid, no_changed = correct_entries(entries, OUTPUT_DIR)
        print(f"Number of invalid addresses: {no_invalid}")
        print(f"Number of changed addresses: {no_changed}")

    # Apply postprocessing to the entries
    post_process_entries(entries)

    # Generate the output PDF
    generate_pdf(entries, os.path.join(OUTPUT_DIR, "sticker_sheet.pdf"))

    print("Generation complete! Thank you for using the amazing Thabloid Sticker Generator, "
          "see you in a few months!")
