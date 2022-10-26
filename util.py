"""
File with utility functions
"""

import re

dutch_address_regex = re.compile(r"^(\d*[\wäöüß\d '/\\.\-]+)[,\s]+(\d+)[\s,]*([\wäöüß\d\-/]*)$")


def query_yes_no(question: str, default: str = None) -> bool:
    """
    Ask a yes/no question to the user and return their answer.

    Parameters
    ----------
    question: str
        The question that is presented to the user
    default: str
        Default response value (i.e. the value that is used when the user presses the 'enter' key)
        Can be 'yes', 'ye', 'y', 'no', 'n' and None

    Raises
    ------
    ValueError
        If an invalid default value is given

    Returns
    -------
    bool:
        True if the user response was 'yes', False if the user response was 'no'
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError(f"invalid default answer: '{default}'")

    while True:
        print(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        if choice in valid:
            return valid[choice]
        print("Please respond with 'yes' or 'no' (or 'y' or 'n')")


def entry_to_string(entry: dict) -> str:
    """
    Converts an entry to a multi-line human-readable string

    Parameters
    ----------
    entry: dict
        The entry, represented as a dictionary

    Returns
    -------
    str:
        A nicely formatted string representing this entry
    """
    string = f"  Name:          {entry['first_name']} {entry['last_name']}\n" \
             f"  Address:       {entry['address']}\n"
    if len(entry['address_2']) > 0:
        string += f"                 {entry['address_2']}\n"
    string += f"  Postal code:   {entry['postal_code']}\n" \
              f"  City:          {entry['city']}"
    if entry['country'] != 'Netherlands':
        string += f"\n  Country:       {entry['country']}"
    return string


def format_dutch_address(address: str) -> (str, str, str):
    """
    Formats a Dutch address into a street name, house number, and house number extra part,
    using a regular expression.

    Parameters
    ----------
    address: str
        The address, represented as a string

    Returns
    -------
    str, str, str:
        A tuple containing the address, house number and house number extra
    None, None, None
        If the pattern could not be matched
    """
    pattern = dutch_address_regex.search(address.strip())
    if pattern:
        return pattern.group(1), pattern.group(2), pattern.group(3)
    return None, None, None


def format_dutch_postal_code(postal_code: str) -> str:
    """
    Formats a Dutch postal code to upper-case and with a space between the letters and digits.

    Parameters
    ----------
    postal_code: str
        The Dutch postal code

    Returns
    -------
    str:
        The formatted Dutch postal code
    """
    postal_code = postal_code.upper()
    if len(postal_code) == 6:
        return f"{postal_code[0:4]} {postal_code[4:6]}"
    return postal_code
