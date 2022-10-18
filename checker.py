import difflib
import os
import json
import re
from urllib.error import HTTPError

from tqdm import tqdm
from json import JSONDecodeError
from urllib import request

import unicodedata

from util import entry_to_string, query_yes_no, format_dutch_address
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
        if json.loads(request.urlopen(url).read())["status"] == "REQUEST_DENIED":
            raise InvalidApiKeyException("The API key in credentials.json was invalid")

    return api_key


def request_from_google_api(api_key, arguments):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{arguments}&key={api_key}"
    response = request.urlopen(url)
    try:
        response = json.loads(response.read().decode("utf-8"))
    except NameError:
        return None

    if not response["status"] == "OK":
        return None
    return response


def request_dutch_entry_from_google_api(api_key, entry, include_city=False):
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

        street_name = None
        street_number = None
        street_extra = None
        postal_code = None
        city = None
        country = None

        for component in address_components:
            types = component["types"]

            if "route" in types:
                street_name = component["long_name"]
            if "street_number" in types:
                street_number = component["long_name"]
            if "subpremise" in types:
                street_extra = component["long_name"]
            if "postal_code" in types:
                postal_code = component["long_name"]
            if "locality" in types:
                city = component["long_name"]
            if "country" in types:
                country = component["short_name"]

        return {"street_name": street_name, "street_number": street_number, "street_extra": street_extra,
                "postal_code": postal_code, "city": city, "country": country}
    except IndexError:
        return None
    except TypeError:
        return None


def suggest_address_change_with_google_api(api_key, entry):
    result = entry.to_dict()
    # Get a response from the address and city
    address = request_dutch_entry_from_google_api(api_key, entry, True)

    # If no response was received, try it again, but without the city
    if not address or not address['country'] == 'NL':
        address = request_dutch_entry_from_google_api(api_key, entry, False)

    # If all fails, raise an exception
    if not address:
        return None

    result["address"] = f"{address['street_name']} {address['street_number']}"
    if address['street_extra']:
        result["address"] = f"{result['address']}, {address['street_extra']}"
    if address["postal_code"]:
        result["postal_code"] = address["postal_code"]
    if address["city"]:
        result["city"] = address["city"]
    return result


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
        None
        # TODO: fix_dutch_postal_code(api_key, entry)


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
        None
        # TODO: fix_dutch_postal_code(api_key, entry)


def query_dutch_georegister(street, house_number, postal_code, city, house_number_extra=None):
    query_params = [f"fl=woonplaatsnaam,postcode,straatnaam,huis_nlt"]
    if street:
        query_params.append(f"fq=straatnaam:{street}")
    if house_number:
        query_params.append(f"fq=huisnummer:{house_number}")
    if postal_code:
        query_params.append(f"fq=postcode:{postal_code}")
    if city:
        query_params.append(f"fq=woonplaatsnaam:{city}")
    # For adding the house number extra to the query parameter
    if house_number_extra:
        query_params.append(f"q={house_number_extra}")
    formatted = '&'.join(query_params)

    url = f"https://geodata.nationaalgeoregister.nl/locatieserver/v3/free?{formatted}".replace(' ', '+')
    # print(f"Geodata URL: {url}")
    try:
        return json.loads(request.urlopen(url).read().decode("utf-8"))['response']
    except HTTPError:
        return None


#
# def suggest_address_change_with_geocode_api(entry, ignore_argument):
#     street, house_number, house_number_extra = format_dutch_address(entry["address"])
#     if not house_number:
#         return
#     postal_code = format_dutch_postal_code(entry["postal_code"])
#
#     if ignore_argument == "street_name":
#         response = query_dutch_georegister(street, house_number, postal_code, entry['city'], house_number_extra)
#     elif ignore_argument == "city":
#         response = query_dutch_georegister(street, house_number, postal_code, None, house_number_extra)


def verify_dutch_address(entry, ignore_argument=""):
    street, house_number, house_number_extra = format_dutch_address(entry["address"])
    if not house_number:
        return False
    postal_code = entry["postal_code"].upper().replace(" ", "")

    if ignore_argument == "straatnaam":
        response = query_dutch_georegister(None, house_number, postal_code, entry['city'], house_number_extra)
    elif ignore_argument == "woonplaatsnaam":
        response = query_dutch_georegister(street, house_number, postal_code, None, house_number_extra)
    else:
        response = query_dutch_georegister(street, house_number, postal_code, entry['city'], house_number_extra)

    removed_extra = False
    if not response or response['numFound'] > 25000:
        return False
    elif response['numFound'] == 0:
        # TODO: Als de house number extra niet bestaat hoeft dit dus niet
        response = query_dutch_georegister(street, house_number, postal_code, entry['city'])
        if response['numFound'] == 0:
            return False
        removed_extra = True
    elif response['numFound'] > 1 and ignore_argument:
        # Check if the ignored elements are the same for all responses
        expected = response['docs'][0][ignore_argument]
        for i in range(1, response['numFound']):
            if not response['docs'][i][ignore_argument] == expected:
                return False
        # If they are, set that value and return
        response_address = response['docs'][0]
        if ignore_argument == "straatnaam":
            entry['address'] = entry['address'].replace(street, response_address['straatnaam'])
        elif ignore_argument == "woonplaatsnaam":
            entry['city'] = response_address['woonplaatsnaam']
        return True

    response_address = response['docs'][0]
    if response['numFound'] == 1 and not removed_extra:
        entry['address'] = f"{response_address['straatnaam']} {response_address['huis_nlt']}"
    entry['postal_code'] = response_address['postcode']
    entry['city'] = response_address['woonplaatsnaam']
    return True


def correct_entries(entries, output_dir):
    api_key = get_api_key()

    invalid_entries = []
    changed_entries = []
    entries_to_drop = []

    for i, entry in tqdm(entries.iterrows(), total=len(entries)):
        original_entry_dict = entry.to_dict().copy()
        try:
            if entry["first_name"] == "Rico" and entry["last_name"] == "te Wechel":
                entry["first_name"] = "Grote"
                entry["last_name"] = "Smurf"

            # Check that the address is not empty and not removed
            if entry["address"] == "" or "<removed>" in entry["address"]:
                raise InvalidAddressException("Missing data for 'address' field")

            if entry["country"] == "Netherlands":
                # Verify the Dutch address. If it is a fully correct address, we continue
                if verify_dutch_address(entry):
                    continue

                # Attempt to fix the address with Google Maps
                address_suggestion = suggest_address_change_with_google_api(api_key, entry)
                if address_suggestion:
                    # Check if the newly suggested address is correct
                    if verify_dutch_address(address_suggestion):
                        # TODO: Verander de entry dan nog ff want de suggestion is json lol
                        entry['address'] = address_suggestion['address']
                        entry['postal_code'] = address_suggestion['postal_code']
                        entry['city'] = address_suggestion['city']
                        changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                                'GOOGLE_SUGGESTION'))
                        continue
                    # TODO: Google maps vond wel een adres, maar de database vindt hem niet valid?
                    # TODO: Zie hierna, zelfde case maar met meer info?

                # TODO: Attempt to fix the address by ignoring the street name and using the postal code
                # TODO: Doe dit met de geocode api.
                # TODO: Also: als er meerde entries zijn check dan of adres overal hetzelfde is dan is het goed
                if verify_dutch_address(entry, ignore_argument="straatnaam"):
                    changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                            'GEOCODE_SUGGESTION_CHANGE_STREET_NAME'))
                    continue

                # TODO: Als dit ook niet werkt: misschien was de woonplaatsnaam fout?
                # TODO: Geocode api query zonder woonplaatsnaam. Als er 1 resultaat is, verander dan
                if verify_dutch_address(entry, ignore_argument="woonplaatsnaam"):
                    changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                            'GEOCODE_SUGGESTION_CHANGE_CITY'))
                    continue

                print(entry_to_string(entry))
            else:
                # Do other stuff
                None

        except InvalidAddressException as err:
            if not err.query or not query_yes_no(f"\n---------------------------------------------------\n"
                                                 f"The following entry was found to be invalid:\n"
                                                 f"{entry_to_string(entry)}\n"
                                                 f"Reason: {err.message}\n"
                                                 f"Do you want to add this address anyway?", "no"):
                # Drop invalid results
                entries_to_drop.append(i)
                invalid_entries.append(original_entry_dict)

    # Drop invalid entries and reset the indices
    entries.drop(entries.index[entries_to_drop], inplace=True)
    entries.reset_index(drop=True, inplace=True)

    # Log changes to output files
    with open(os.path.join(output_dir, 'invalid_entries.log'), 'w', encoding='utf8') as file:
        file.write('\n\n'.join(map(entry_to_string, invalid_entries)))

    with open(os.path.join(output_dir, 'changed_entries.log'), 'w', encoding='utf8') as file:
        file.write('\n\n\n'.join(map(lambda changed_entry: f'ORIGINAL:\n{changed_entry[0]}\n'
                                                           f'CHANGED:\n{changed_entry[1]}\n'
                                                           f'REASON: {changed_entry[2]}', changed_entries)))
        # file.write('\n\n\n'.join({f'ORIGINAL:\n{original}\n'
        #                          f'CHANGED:\n{changed}'
        #                          for original, changed in changed_entries.items()}))
