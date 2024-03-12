import re
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

    #radius in meters ~ 30 miles
    query_result = google_places.nearby_search(
            location=address, keyword=keyword,
            radius=48280.3)


    # if len(query_result.raw_response['results']) == 0:
    #     return "Didn't find an"
    response = ""
    for i in range(len(query_result.raw_response['results'])):
        response += f""" {i+1}. {query_result.raw_response['results'][i]['name']}
Address : {query_result.raw_response['results'][i]['vicinity']}

"""
    return response
