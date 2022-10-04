import difflib
import os
import json
import re
from tqdm import tqdm
from json import JSONDecodeError
from urllib import request

import pandas as pd
import unicodedata

from util import entry_to_string, query_yes_no
from exceptions import *

dutch_postal_code_regex = re.compile("^[1-9]\d{3} ?(?!SA|SD|SS)[A-Z]{2}$")


def get_api_key():
    # Check that the credentials file exists
    if not os.path.exists("input/credentials.json"):
        raise InvalidApiKeyException("No Google Maps API key given (input/credentials.json)")

    with open("input/credentials.json") as file:
        # Attempt to parse the json
        try:
            data = json.load(file)
        except JSONDecodeError:
            raise InvalidApiKeyException("No (valid) JSON object in credentials.json")

        # Check that the json is an object
        if not isinstance(data, dict):
            raise InvalidApiKeyException("No JSON object in credentials.json")

        # Check that the key exists
        if "google_maps_api_key" in data:
            api_key = data["google_maps_api_key"]
        else:
            raise InvalidApiKeyException("Missing json key 'google_maps_api_key' in credentials.json")

        # Check that the key is a possible string
        if not isinstance(api_key, str):
            raise InvalidApiKeyException("Json value for key 'google_maps_api_key' is not a string")
        elif api_key == "INSERT_MAPS_API_KEY":
            raise InvalidApiKeyException("Please update the API key in credentials.json. "
                                         "A valid API key is stored on the shared Thabloid committee drive")

        # Check that the api key is valid
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address=a&key={api_key}"
        if eval(request.urlopen(url).read())["status"] == "REQUEST_DENIED":
            raise InvalidApiKeyException("The API key in credentials.json was invalid")

    return api_key


def request_from_google_api(api_key, arguments):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{arguments}&key={api_key}"
    response = request.urlopen(url)
    try:
        response = eval(response.read().decode("utf-8"))
    except NameError:
        return None

    if not response["status"] == "OK":
        return None
    return response


def request_postal_code_and_city(api_key, entry, include_city=False):
    # Parse arguments
    arguments = f"address={entry['address'].replace(' ', '+')}"
    if include_city:
        arguments = arguments + f"+{entry['city'].replace(' ', '+')}"

    # Send the request
    response = request_from_google_api(api_key, arguments)

    try:
        # Fetch the postal code and city from the result
        address_components = list(filter(lambda x: "address_components" in x,
                                         response["results"]))[0]["address_components"]
        # Get postcode dict
        postal_code_dict = list(filter(lambda x: "postal_code" in x["types"], address_components))[0]
        # Attempt to parse city dict
        try:
            city_dict = list(filter(lambda x: "locality" in x["types"], address_components))[0]
        except IndexError:
            # If the city dict could not be parsed, just return the postal code
            return postal_code_dict["long_name"].upper().replace(" ", ""), None
        # Return the result
        return postal_code_dict["long_name"].upper(), city_dict["long_name"]
    except IndexError:
        return None, None
    except TypeError:
        return None, None


def fix_dutch_postal_code(api_key, entry):
    # Get a response from the address and city
    postal_code, city = request_postal_code_and_city(api_key, entry, True)

    # If no response was received, try it again, but without the city
    if not postal_code:
        postal_code, city = request_postal_code_and_city(api_key, entry, False)

    # If all fails, raise an exception
    if not postal_code:
        raise InvalidAddressException("No postal code could be found for the provided address")

    # Correct city back if it was None
    if not city:
        city = entry["city"]

    if (postal_code.lower().replace(" ", "") == entry["postal_code"].lower().replace(" ", "")
        and city.lower().replace(" ", "") == entry["city"].lower().replace(" ", "")) \
            or query_yes_no("\n---------------------------------------------------\n"
                            "The Google Maps API checked the following entry:\n"
                            f"{entry_to_string(entry)}\n"
                            f"And proposed the following changes:\n"
                            f"  Postal code:   {postal_code}\n"
                            f"  City:          {city}\n"
                            "Do you want to change the original entry to this proposition?", "yes"):
        entry["postal_code"] = postal_code
        entry["city"] = city
        entry["country"] = "Netherlands"
    else:
        raise InvalidAddressException("The postal code found for the provided address was decided to be incorrect")


def handle_foreign_postal_code(api_key, entry):
    # If the country is not 'Netherlands', it is a postal code from another country
    if not entry["country"] == "Netherlands":
        return True
    # Otherwise, query the user
    if query_yes_no("\n---------------------------------------------------\n"
                    "In the following entry:\n"
                    f"{entry_to_string(entry)}\n"
                    f"Is {entry['postal_code']} actually a postal code from another country?"):
        # Send request
        arguments = f"address={entry['address'].replace(' ', '+')}+{entry['city'].replace(' ', '+')}"
        response = request_from_google_api(api_key, arguments)
        try:
            # Fetch the address components from the result
            address_components = list(filter(lambda x: "address_components" in x,
                                             response["results"]))[0]["address_components"]
            # Get country
            country = list(filter(lambda x: "country" in x["types"], address_components))[0]["long_name"]
            # Check with the user if the country is correct
            if query_yes_no(f"Is {country} the correct country for this entry?", "yes"):
                entry["country"] = country
                return True
            else:
                raise InvalidAddressException("No correct country could be found")
        except IndexError:
            return None, None
    # Return that it was not a postal code from another country
    return False


def get_number(address):
    try:
        return address[re.search("\d", address).span()[0]:]
    except AttributeError:
        return None


def check_address(api_key, entry, correct_addresses):
    # Get the house number of the address
    house_number = get_number(entry['address'])
    closest_street = ""
    closest_ratio = 0
    # Loop through all options for correct addresses
    for correct_address in correct_addresses:
        # Convert to ascii
        street = unicodedata.normalize('NFKD', correct_address['straat']).encode('ascii', 'ignore').decode("ascii")

        # If the street name that was found is a part of the already known address, check if they are equal.
        # If they are not, set the address equal to the street with the house number
        if street.lower() in entry['address'].lower():
            if not street.lower() == entry['address'].lower():
                entry['address'] = street + (" " + house_number if house_number else "")
            return

        # Caculate the similarity ratio between the collected street and the address, store the lowest ratio
        similarity_ratio = difflib.SequenceMatcher(None, street.lower(), entry['address'].lower()).ratio()
        if similarity_ratio > closest_ratio:
            closest_street = street
            closest_ratio = similarity_ratio

    # Append the house number to the street
    street = closest_street + (" " + house_number if house_number else "")
    # If the closest ratio was high enough, we alter the entry and are done
    if closest_ratio > 0.75:
        entry['address'] = street
        return
    # Otherwise, we ask the user if the addresses are similar enough.
    # If they are not similar enough, we use the google maps API to alter the entry
    if query_yes_no("\n---------------------------------------------------\n"
                    "The Postal Code API checked the following entry:\n"
                    f"{entry_to_string(entry)}\n"
                    f"And proposed the following modification:\n"
                    f"  Address:       {street}\n"
                    "Are these the same addresses?"):
        entry["address"] = street
    else:
        fix_dutch_postal_code(api_key, entry)


def validate_address_with_postal_code(api_key, entry):
    # Retrieve addresses from the postal code api
    try:
        url = f"http://postcode-api.nl/adres/{entry['postal_code'].replace(' ', '')}"
        correct_addresses = json.load(request.urlopen(url))
    except JSONDecodeError:
        correct_addresses = []
    # If there was at least one valid address, check the addresses. Otherwise, raise an exception
    if len(correct_addresses) != 0:
        check_address(api_key, entry, correct_addresses)
    else:
        fix_dutch_postal_code(api_key, entry)


def check_entries(entries):
    api_key = get_api_key()

    for i, entry in tqdm(entries.iterrows()):
        try:
            # Check that the address is not empty and not removed
            if entry["address"] == "" or "<removed>" in entry["address"]:
                raise InvalidAddressException("Missing data for 'address' field")

            if entry["postal_code"] == "":
                # Fix empty postal codes
                fix_dutch_postal_code(api_key, entry)
            elif not dutch_postal_code_regex.match(entry["postal_code"]):
                if entry["country"] == "Netherlands":
                    try:
                        fix_dutch_postal_code(api_key, entry)
                    except InvalidAddressException:
                        if not handle_foreign_postal_code(api_key, entry):
                            raise InvalidAddressException("No postal code could be found for the provided address")
                elif not handle_foreign_postal_code(api_key, entry):
                    # If it was not a foreign postal code, attempt to fix it as a Dutch postal code
                    fix_dutch_postal_code(api_key, entry)
            else:
                # For correct Dutch postal codes, check that their associated address matches
                validate_address_with_postal_code(api_key, entry)
        except InvalidAddressException as err:
            if not query_yes_no(f"\n---------------------------------------------------\n"
                                f"The following entry was found to be invalid:\n"
                                f"{entry_to_string(entry)}\n"
                                f"Reason: {err.message}\n"
                                f"Do you want to add this address anyway?", "no"):
                # Drop invalid results
                entries.drop(i, inplace=True)
    # Reset the indices for the dataset
    entries.reset_index(drop=True, inplace=True)

# https://geodata.nationaalgeoregister.nl/locatieserver/v3/free?fq=straatnaam:...&fq=woonplaatsnaam:...&fq=huisnummer:...&fl=woonplaatsnaam,postcode,straatnaam,huisnummer