import re

dutch_address_regex = re.compile("^(\d*[\wäöüß\d '/\\.\-]+)[,\s]+(\d+)[\s,]*([\wäöüß\d\-/]*)$")


def query_yes_no(question: str, default: str = None) -> bool:
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        print(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n')")


def entry_to_string(entry: dict) -> str:
    string = f"  Name:          {entry['first_name']} {entry['last_name']}\n" \
             f"  Address:       {entry['address']}\n"
    if len(entry['address_2']) > 0:
        string += f"                 {entry['address_2']}\n"
    string += f"  Postal code:   {entry['postal_code']}\n" \
              f"  City:          {entry['city']}\n"
    if entry['country'] != 'Netherlands':
        string += f"  Country:       {entry['country']}"
    return string


def format_dutch_address(address: str) -> (str, str, str):
    pattern = dutch_address_regex.search(address.strip())
    if pattern:
        return pattern.group(1), pattern.group(2), pattern.group(3)
    return None, None, None


def format_dutch_postal_code(postal_code: str) -> str:
    postal_code = postal_code.upper()
    if len(postal_code) == 6:
        return f"{postal_code[0:4]} {postal_code[4:6]}"
    return postal_code
