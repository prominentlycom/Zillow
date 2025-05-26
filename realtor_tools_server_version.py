
import os
from openai import OpenAI

client = OpenAI()
from typing import Optional
import requests


functions = [
    {
        "name": "search_params",
        "description": "Please show the location and other parameters",
        "parameters": {
            "type": "object",
            "properties": {
                "state_code": {
                    "type": "string",
                    "description": "Location state code"
                },
                "city": {
                    "type": "string",
                    "description": "Location city"
                },
                "beds": {
                    "type": "number",
                    "description": "Requirement number of bedrooms"
                },
                "baths": {
                    "type": "number",
                    "description": "Requirement number of bathrooms"
                },
                "sold_price": {
                    "type": "number",
                    "description": "Preferred house price"
                },
                "sqft": {
                    "type": "number",
                    "description": "Preferred Square Feet value."
                },
                "year_built": {
                    "type": "number",
                    "description": "Preferred Year Built value"
                }
            }
        }
    },
]


def find_property_id(
    location: Optional[str] = None,
) -> dict:
    """Tool that uses Realtor api to find property_id given address of the house.
    Use case find property_id when need to use get_house_property tool. Valid params include "location":"location"."""

    base_url = "https://realtor-com4.p.rapidapi.com/auto-complete"

    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "realtor-com4.p.rapidapi.com"
    }

    querystring = {"input": location}

    print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)

    try:
        property_id = result.json()["autocomplete"][0]["_id"].split(":")[1]
        return property_id
    except:
        return "Sorry, could you please give full address"


def remove_redundant_house_info(house_property):
    """Remove some information from realtor listing to fit into LLM's context"""
    print("HOUSE_PROPERTY_VARIABLE: ", house_property)
    house_property["data"]["home"].pop("advertisers")
    house_property["data"]["home"].pop("buyers")
    house_property["data"]["home"].pop("consumer_advertisers")
    house_property["data"]["home"].pop("flags")
    house_property["data"]["home"].pop("estimates")
    house_property["data"]["home"].pop("home_tours")
    house_property["data"]["home"].pop("lead_attributes")
    house_property["data"]["home"].pop("property_history")
    house_property["data"]["home"].pop("other_listings")
    house_property["data"]["home"].pop("photos")
    house_property["data"]["home"].pop("products")
    house_property["data"]["home"].pop("source")
    house_property["data"]["home"].pop("tax_history")
    house_property["data"]["home"].pop("matterport")
    house_property["data"]["home"].pop("tags")
    house_property["data"]["home"].pop("primary_photo")
    house_property["data"]["home"].pop("suppression_flags")
    house_property["data"]["home"].pop("href")

    return house_property


def __get_info_about_home_from_realtor(location: str):
    """Retrieve property detail using Realtor.com API"""
    p_id = find_property_id(location)
    if p_id == "Sorry, could you please give full address":
        return p_id

    base_url = "https://realtor-com4.p.rapidapi.com/properties/detail"

    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "realtor-com4.p.rapidapi.com",
    }

    if p_id is not None:
        querystring = {"property_id": p_id}
        print("QUERYSTRING: ", querystring)
    else:
        raise Exception("Didn't get p_id")

    result = requests.get(base_url, params=querystring, headers=headers)
    print("RESULT_HOME: ", result.json())
    return result


def realtor_get_house_details(
    location: Optional[str] = None,
) -> dict:
    """Tool that uses Realtor api to get house properties given adress of the house.
    Use case answer on questions related to the house. Valid params include "location":"location"."""
    result = __get_info_about_home_from_realtor(location)
    if isinstance(result, str):
        return result
    post_processed = remove_redundant_house_info(result.json())
    return post_processed


def get_tax_and_price_information_from_realtor(location: str) -> dict:
    """Tool that uses Realtor api to search for house price, taxHistory and price history the house.
    Use case answer on questions related to the house price, tax. Valid params include "location":"location"."""
    result = __get_info_about_home_from_realtor(location)
    if isinstance(result, str):
        return result
    response = []
    tax_info = result.json()["data"]["home"]["tax_history"][:4]
    response.append({"Tax History": tax_info})
    print("tax info: ", tax_info)
    price_info = result.json()["data"]["home"]["estimates"]["historical_values"][0]["estimates"][:48]
    response.append({"Price History": price_info})
    return response
    # return result.json()


def realtor_search_properties_without_address(user_input: str):
    """Search properties without address tool, useful when need to search properties without specific address"""
    response = client.chat.completions.create(model="gpt-3.5-turbo-0613",
    messages=[
        {
            "role": "system",
            "content": "You are useful assistant"
        },
        {
            "role": "user",
            "content": f"Here is user input: {user_input}. Please return location and other parameters."
        }
    ],
    functions=functions,
    function_call={
        "name": "search_params"
    })
    arguments = response.choices[0].message.function_call.arguments
    arguments = arguments.split("\n")
    params = {}
    for el in arguments:
        el = el.strip()
        el = el.rstrip(",")
        print(el)
        if len(el) > 3:
            key, value = el.split(": ")
            if value.isnumeric():
                value = int(value)
            else:
                value = value.strip('"')
            params[key.strip('"')] = value

    payload = {
        "query": {
            "status": ["for_sale", "ready_to_build"],
        },
        "limit": 42,
        "radius": 100,
        "offset": 0,
        "sort": {
            "direction": "desc",
            "field": "list_date"
        }
    }
    if params.get("state_code"):
        payload["query"]["state_code"] = params["state_code"]
    if params.get("city"):
        payload["query"]["city"] = params["city"]
    if params.get("sold_price"):
        payload["query"]["list_price"] = {"min": params["sold_price"]}
    if params.get("baths"):
        payload["query"]["baths"] = {"min": params["baths"]}
    if params.get("sqft"):
        payload["query"]["sqft"] = {"max": params["sqft"]}
    if params.get("beds"):
        payload["query"]["beds"] = {"max": params["beds"]}

    base_url = "https://realtor-com4.p.rapidapi.com/properties/list"

    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "realtor-com4.p.rapidapi.com"
    }
    response = requests.post(base_url, json=payload, headers=headers)
    result = response.json()
    print("RESULT: ", result)
    result = result["data"]["home_search"]["properties"][:5]
    for item in result:
        item.pop("branding")
        item.pop("lead_attributes")
        item.pop("flags")
        item.pop("photos")
        item.pop("primary_photo")
        item.pop("products")
        item.pop("source")

    return result
