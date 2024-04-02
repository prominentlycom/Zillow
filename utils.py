import re
from ai_model import google_places_wrapper
import googlemaps
import os
from dotenv import load_dotenv
from googleplaces import GooglePlaces, types, lang

# Load .env file
load_dotenv()

# Read an environment variable
os.environ["GPLACES_API_KEY"] =  os.getenv('GPLACES_API_KEY')

def add_distance_to_google_places(res: str,address:str) -> str: 
    """
    res (str) - output of google places wrapper
    address (str) - address of the house

    return (str) - modified output of google places wrapper that contains distances to address
    """
    pattern = r"Address:\s*(.*?)(?=\n)"

    # Finding all matches
    addresses = re.findall(pattern, res)
    distance_results = []
    # Searching distance
    for address_in_res in addresses:
        distance_results.append(calculate_distance_between_addresses(address_in_res,address))

    distance_results_str = '\n'.join(distance_results)
    return res + '\n' + distance_results_str

def calculate_distance_between_addresses(address1 : str, address2 : str):
        gmaps = googlemaps.Client(key = os.getenv('GPLACES_API_KEY'))
        data = gmaps.distance_matrix(address1,address2)
        my_dist =data['rows'][0]['elements'][0]
        if my_dist['status'] == 'NOT_FOUND':
            return "Sorry, couldn't find the distance"
        if not my_dist.get("distance"):
            return "Sorry, couldn't find the distance"
        distance_km = my_dist['distance']['text']
        if distance_km == "1 m":
            distance_km = 'less than 200 m'
        duration = my_dist['duration']['text']
        if data['destination_addresses'][0] == data['origin_addresses'][0]:
            return "Ask about name of the location that user interested in"
        res = f"Include this information while answering \n Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the car travel time is {duration}"
        return res

def get_nearby_places(keyword : str, address: str):
    """
    Google maps nearby search.

    keyword (str) : place that is searched, i.e school, hospital, dunkin 
    address (str) : address where place from keyword is searched
    """
    google_places = GooglePlaces(os.getenv('GPLACES_API_KEY'))
    # start with a small radius before making the the radius
    radius = 2  # Initial radius value
    max_radius = 32  # Maximum radius value
    response = ""

    while radius <= max_radius:
        query_result = google_places.nearby_search(
            location=address, keyword=keyword,
            radius=radius * 1000, rankby='distance')  # Convert radius to meters, add rankby parameter = distance

        if len(query_result.raw_response['results']) > 0:
            sorted_results = sorted(query_result.raw_response['results'], key=lambda x: x.get('distance', float('inf')))
            for i in range(min(len(sorted_results), 5)):
                place = f""" {i + 1}. {sorted_results[i]['name']}
                Address: {sorted_results[i]['vicinity']}
                """
                print(f'Found several places {place}')
                response += place
            break  # Exit loop if places are found within current radius
        else:
            print(f"No places found within {radius} m radius")
            # Fallback option
            result = google_places_wrapper(f"{keyword} near {address}")

            if 'Google Places did not find any places that match the description' in result:
                print(f"fallback option didn't find any results")
                raise Exception("Couldn't find %s near %s" % (keyword,address))
            
            radius += 5  # Increment radius if no places are found

    if not response:
        print(f"No nearby places found for {keyword} near {address}")
        raise Exception("Couldn't find %s near %s" % (keyword, address))

    return response