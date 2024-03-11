import re
from ai_model import find_distance

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
        distance_results.append(find_distance(addresses=address_in_res+'|'+address))

    distance_results_str = '\n'.join(distance_results)
    return res + '\n' + distance_results_str
    