import difflib
import os
import json
import re
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError

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


def request_entry_with_google_api(api_key, entry, include_city=False):
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
        country_short = None
        country_long = None

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
                country_short = component["short_name"]
                country_long = component["long_name"]

        return {"street_name": street_name, "street_number": street_number, "street_extra": street_extra,
                "postal_code": postal_code, "city": city, "country_short": country_short, "country_long": country_long}
    except IndexError:
        return None
    except TypeError:
        return None


def suggest_address_with_google_api(api_key, entry, in_nl=True):
    result = entry.to_dict()
    # Get a response from the address and city
    address = request_entry_with_google_api(api_key, entry, True)
    if in_nl:
        # If no response was received, or the response country was invalid, or no full address was provided,
        # try without city
        if not address or not address['country_short'] == 'NL' or not address['street_name'] \
                or not address['street_number'] or not address['postal_code'] or not address['city']:
            address = request_entry_with_google_api(api_key, entry, False)
    elif not address:
        address = request_entry_with_google_api(api_key, entry, False)

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
    if not in_nl and address["country_long"]:
        result["country"] = address["country_long"]
    return result


# def handle_foreign_postal_code(api_key, entry):
#     # If the country is not 'Netherlands', it is a postal code from another country
#     if not entry["country"] == "Netherlands":
#         return True
#     # Otherwise, query the user
#     if query_yes_no("\n---------------------------------------------------\n"
#                     "In the following entry:\n"
#                     f"{entry_to_string(entry)}\n"
#                     f"Is {entry['postal_code']} actually a postal code from another country?"):
#         # Send request
#         arguments = f"address={entry['address'].replace(' ', '+')}+{entry['city'].replace(' ', '+')}"
#         response = request_from_google_api(api_key, arguments)
#         try:
#             # Fetch the address components from the result
#             address_components = list(filter(lambda x: "address_components" in x,
#                                              response["results"]))[0]["address_components"]
#             # Get country
#             country = list(filter(lambda x: "country" in x["types"], address_components))[0]["long_name"]
#             # Check with the user if the country is correct
#             if query_yes_no(f"Is {country} the correct country for this entry?", "yes"):
#                 entry["country"] = country
#                 return True
#             else:
#                 raise InvalidAddressException("No correct country could be found")
#         except IndexError:
#             return None, None
#     # Return that it was not a postal code from another country
#     return False


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
        # As the Geodata API is sometimes unstable, we try to send the request a number of times
        response = None
        attempts = 3
        for i in range(0, attempts - 1):
            try:
                response = request.urlopen(url, timeout=5)
                break
            except RemoteDisconnected:
                if i == attempts - 1:
                    return None
            except TimeoutError:
                if i == attempts - 1:
                    return None
            except URLError:
                if i == attempts - 1:
                    return None
        return json.loads(response.read().decode("utf-8"))['response']
    except HTTPError:
        return None


def verify_dutch_address(entry, ignore_argument=""):
    street, house_number, house_number_extra = format_dutch_address(entry["address"])
    if not house_number:
        return False
    postal_code = entry["postal_code"].upper().replace(" ", "")

    if ignore_argument == "straatnaam":
        response = query_dutch_georegister(None, house_number, postal_code, entry['city'], house_number_extra)
    elif ignore_argument == "woonplaatsnaam":
        response = query_dutch_georegister(street, house_number, postal_code, None, house_number_extra)
    elif ignore_argument == "postcode":
        response = query_dutch_georegister(street, house_number, None, entry['city'], house_number_extra)
        if int(response['numFound']) == 0:
            response = query_dutch_georegister(street, house_number, None, entry['city'], None)
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
        result_index = 0
        if ignore_argument == "postcode":
            # For the postal code, if there are over 10 responses, we ignore the results
            if int(response['numFound']) > 10:
                return False
            # Otherwise, if there is more than one response, we check if we have a match
            if not int(response['numFound']) == 1:
                # Else, check if there is exactly one that has matching data
                result_index = -1
                for i in range(0, int(response['numFound'])):
                    if street in response['docs'][i]['straatnaam'] \
                            and response['docs'][i]['huis_nlt'].startswith(house_number) \
                            and response['docs'][i]['woonplaatsnaam'] == entry['city']:
                        # If the resulting index was already set, we have multiple matching entries. This is incorrect
                        if not result_index == -1:
                            return False
                        result_index = i
                # If no entry was found, return
                if result_index == -1:
                    return False
        else:
            # For the street name and city name, check if the ignored elements are the same for all responses
            expected = response['docs'][0][ignore_argument]
            for i in range(1, response['numFound']):
                if not response['docs'][i][ignore_argument] == expected:
                    return False
        # If they are, set that value and return
        response_address = response['docs'][result_index]
        if ignore_argument == "straatnaam":
            entry['address'] = entry['address'].replace(street, response_address['straatnaam'])
        elif ignore_argument == "woonplaatsnaam":
            entry['city'] = response_address['woonplaatsnaam']
        elif ignore_argument == "postcode":
            entry['address'] = entry['address'].replace(street, response_address['straatnaam'])
            entry['postal_code'] = response_address['postcode']
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
                address_suggestion = suggest_address_with_google_api(api_key, entry)
                if address_suggestion:
                    # Check if the newly suggested address is correct
                    if verify_dutch_address(address_suggestion):
                        # Change the entry to the suggestion
                        entry['address'] = address_suggestion['address']
                        entry['postal_code'] = address_suggestion['postal_code']
                        entry['city'] = address_suggestion['city']
                        changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                                'GOOGLE_SUGGESTION_DUTCH'))
                        continue
                    # TODO: Google maps vond wel een adres, maar de database vindt hem niet valid?
                    # TODO: Zie hierna, zelfde case maar met meer info?

                # TODO: Attempt to fix the address by ignoring the street name and using the postal code
                # TODO: Doe dit met de geocode api.
                # TODO: Also: als er meerde entries zijn check dan of adres overal hetzelfde is dan is het goed
                if verify_dutch_address(entry, ignore_argument="straatnaam"):
                    changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                            'GEODATA_SUGGESTION_CHANGE_STREET_NAME'))
                    continue

                # TODO: Als dit ook niet werkt: misschien was de woonplaatsnaam fout?
                # TODO: Geocode api query zonder woonplaatsnaam. Als er 1 resultaat is, verander dan
                if verify_dutch_address(entry, ignore_argument="woonplaatsnaam"):
                    changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                            'GEODATA_SUGGESTION_CHANGE_CITY'))
                    continue

                if verify_dutch_address(entry, ignore_argument="postcode"):
                    changed_entries.append((entry_to_string(original_entry_dict), entry_to_string(entry.to_dict()),
                                            'GEODATA_SUGGESTION_CHANGE_POSTAL_CODE'))
                    continue
            else:
                # Verify the international address with the Google Maps API
                address_suggestion = suggest_address_with_google_api(api_key, entry, False)
                if address_suggestion:
                    # Check if the suggestion changed something. If so, add it to the changed entries
                    if not entry['address'].lower() == address_suggestion['address'].lower().replace(u'\xdf', 'ss') \
                            or not entry['postal_code'].lower() == address_suggestion['postal_code'].lower() \
                            or not entry['city'].lower() == address_suggestion['city'].lower().replace(u'\xdf', 'ss') \
                            or not entry['country'].lower() == address_suggestion['country'].lower():
                        changed_entries.append((entry_to_string(original_entry_dict),
                                                entry_to_string(address_suggestion),
                                                'GOOGLE_SUGGESTION_NON_DUTCH'))
                    # Change the entry to the suggestion
                    entry['address'] = address_suggestion['address']
                    entry['postal_code'] = address_suggestion['postal_code']
                    entry['city'] = address_suggestion['city']
                    entry['country'] = address_suggestion['country']
                    continue

            # TODO: Request user? anders verwijderen
            print(f'\n{entry_to_string(entry)}')

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
