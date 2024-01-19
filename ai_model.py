import json
import time

import aiohttp
import openai
from googlemaps.exceptions import ApiError
from pydantic import BaseModel, Field
import requests
import re
import os
from typing import Optional
from dotenv import load_dotenv
import googlemaps
from langchain.agents import initialize_agent, Tool
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.memory import ConversationBufferMemory
from langchain.tools import GooglePlacesTool
from langchain.utilities.google_places_api import GooglePlacesAPIWrapper
from datetime import datetime


# Load .env file
load_dotenv()

# Read an environment variable
os.environ["GPLACES_API_KEY"] = os.getenv("GPLACES_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

functions = [
    {
        "name": "search_params",
        "description": "Please show the location and other parameters",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "interested location, should be only the city name and state code"
                },
                "bedsMin": {
                    "type": "number",
                    "description": "Minimum requirement number of bedrooms"
                },
                "bedsMax": {
                    "type": "number",
                    "description": "Maximum requirement of bedrooms, not more than this value"
                },
                "bathsMin": {
                    "type": "number",
                    "description": "Minimum requirement number of bathrooms"
                },
                "bathsMax": {
                    "type": "number",
                    "description": "Preferred number of bathrooms"
                },
                "minPrice": {
                    "type": "number",
                    "description": "Minimum preferred house price, current price - 10%"
                },
                "sqftMax": {
                    "type": "number",
                    "description": "Maximum preferred Square Feet value."
                },
                "buildYearMax": {
                    "type": "number",
                    "description": "Maximum preferred Year Built value"
                },
                "maxPrice": {
                    "type": "number",
                    "description": "Preferred house price, not more than this value"
                },
                "sqftMin": {
                    "type": "number",
                    "description": "Minimum preferred Square Feet value."
                },
                "buildYearMin": {
                    "type": "number",
                    "description": "Minimum preferred Year Built value"
                },
                "home_type": {
                    "type": "string",
                    "enum": ["Houses", "Townhomes", "Apartments", "Condos", "Multi-family"],
                    "description": "Preferred home type. Can be 'Houses', 'Townhomes' for townhouse, 'Apartments', 'Condos', 'Multi-family'"
                },
                "keywords": {
                    "type": "string",
                    "description": "Keywords for filter properties. Only include key words, ignoring other parts of the sentence."
                },
            }
        }
    },
]




def get_agent_listings(agent_id: str):
    """Tool that get all active listings of provided agent"""
    all_listings = []
    page_number = 1
    while True:

        querystring = {"zuid": agent_id, "page": str(page_number)}
        print(querystring)
        url = "https://zillow-com1.p.rapidapi.com/agentActiveListings"
        headers = {
            "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
            "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers, params=querystring)
        time.sleep(1.5)
        lis = response.json().get("listings")
        if lis:
            all_listings.extend(lis)
        if len(lis) < 10:
            break
        else:
            page_number += 1
    print("all_listings: ", len(all_listings))
    photos = {}
    if all_listings:
        for element in all_listings:
            photos[element["address"]["line1"] + ", " + element["address"]["line2"]] = element["primary_photo_url"]
    return {"res": all_listings, "photos": photos}


def convert_timestamp_to_date(timestamp):
    # Convert milliseconds to seconds by dividing by 1000
    timestamp_seconds = timestamp / 1000

    # Create a datetime object from the timestamp
    datetime_obj = datetime.fromtimestamp(timestamp_seconds)

    # Format the datetime object as a string and return it
    formatted_date = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_date


def find_zpid(
    location: Optional[str] = None,
) -> dict|str:
    """Tool that uses Zillow api to find zpid given adress of the house. Use case find zpid when need to use get_house_property tool. Valid params include "location":"location"."""

    base_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"

    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
    }

    querystring = {"page": "1"}
    print("LOCATION: ", location)
    if location is not None:
        querystring["location"] = location

    print(f'Search with {querystring}')
    time.sleep(1.5)
    result = requests.get(base_url, params=querystring, headers=headers)
    # print("FIND_ZPID_RESULT: ", result.json())
    try:
        if isinstance(result.json(), list):
            return result.json()[0]["zpid"]
        return result.json()["zpid"]
    except:
        return "Sorry, could you please give full address"


def post_process_house_property(house_property):
    """Remove some information from zillow listing to fit into LLM's context"""
    print("HOUSE_PROPERTY_VARIABLE: ", house_property)
    house_property.pop("nearbyHomes")
    house_property.pop("listed_by")
    house_property.pop("brokerageName")
    house_property.pop("contact_recipients")
    house_property.pop("priceHistory")
    house_property.pop("resoFacts")
    house_property.pop("attributionInfo")
    house_property.pop("taxHistory")
    return house_property


def __get_info_about_home_from_zillow(location: str):
    zpid = find_zpid(location)
    if zpid == "Sorry, could you please give full address":
        return zpid

    base_url = "https://zillow-com1.p.rapidapi.com/property"

    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
    }

    if zpid is not None:
        querystring = {"zpid": f"{zpid}"}
    else:
        raise Exception("Didn't get zpid")
    time.sleep(1.2)
    result = requests.get(base_url, params=querystring, headers=headers)
    print("RESULT_HOME: ", result.json())
    return result


def get_house_property(
    location: Optional[str] = None,
) -> dict|str:
    """Tool that uses Zillow api to get house properties given adress of the house.Use case answer on questions related to the house. Valid params include "location":"location"."""
    result = __get_info_about_home_from_zillow(location)
    if isinstance(result, str):
        return result
    post_processed = post_process_house_property(result.json())
    return post_processed


def find_distance(addresses: str) -> str:
    """Find distance tool, useful when need to find distance between two exact addresses"""
    print("Adresses: ", addresses)
    splitted_addresses = addresses.split("|")
    gmaps = googlemaps.Client(key=os.getenv("GPLACES_API_KEY"))

    if len(splitted_addresses) == 2:
        address1, address2 = splitted_addresses[0], splitted_addresses[1]
        address_regex = "\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}"
        match = re.search(address_regex, address2)
        if not match:
            print("NOT_MATCH")
            try:
                address2 = (
                    GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=1))
                    .run(f"{address2} near {address1}")
                    .split("Address:")[1]
                    .split("\n")[0]
                )
            except IndexError:
                return "Sorry, couldn't find the distance"
        print("ADDRESS2: ", address2)
        data = gmaps.distance_matrix(address1, address2)
        my_dist = data["rows"][0]["elements"][0]
        if my_dist["status"] == "NOT_FOUND":
            return "Sorry, couldn't find the distance"

        distance_km = my_dist["distance"]["text"]
        if distance_km == "1 m":
            distance_km = "less than 200 m"
        duration = my_dist["duration"]["text"]
        if data['destination_addresses'][0] == data['origin_addresses'][0]:
            print("NOTHING WAS FOUND")
            return "Ask about name of the location that user interested in"
        res = f"Include this information while answering \n Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the duration is {duration}"
        print("THE FINAL OPTION", res)
        return res

    elif len(splitted_addresses) > 2:
        answer = ""
        address1 = splitted_addresses[0]
        try:
            for i in range(1, len(splitted_addresses)):
                address2 = splitted_addresses[i]
                data = gmaps.distance_matrix(address1, address2)
                my_dist = data["rows"][0]["elements"][0]
                if my_dist["status"] == "NOT_FOUND":
                    return "Sorry, couldn't find the distance"

                distance_km = my_dist["distance"]["text"]
                if distance_km == "1 m":
                    distance_km = "less than 200 m"
                duration = my_dist["duration"]["text"]
                answer += f"Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the duration is {duration}\n"
        except ApiError:
            return "Sorry, couldn't find the distance"
        res = f"Include this information while answering \n{answer}"
        return res


def google_places_wrapper(query: str) -> str:
    """A wrapper around Google Places.
    Useful for when you need to find address of some place near property
    discover addressed from ambiguous text or validate address.
    Input should be a search query."""
    places_tool = GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=3))
    res = places_tool.run(query)
    print(f"Google places result : {res}")
    return res


def get_info_about_similar_homes(location: str, agent_id=None):
    """Tool that uses Zillow api to search for similar properties given address of the house"""
    zpid = find_zpid(location)
    if zpid == "Sorry, could you please give full address":
        return zpid
    time.sleep(1.5)

    url = "https://zillow-com1.p.rapidapi.com/similarProperty"

    querystring = {"zpid": zpid}

    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    time.sleep(1.5)
    response = requests.get(url, headers=headers, params=querystring)
    result = response.json()
    if agent_id:
        res = check_matched_properties(agent_id, result)
        return res
    return result


def check_matched_properties(agent_id, func_result):
    """Check whick objects from agent listings matched search result"""
    listings = get_agent_listings(agent_id)
    zpids_agent = []
    for el in listings:
        zp_id = el.get("zpid")
        if zp_id:
            zpids_agent.append(zp_id)

    matched_homes = []
    for el in func_result:
        zpid = el.get("zpid")
        if zpid and zpid in zpids_agent:
            matched_homes.append(el)
    if matched_homes:
        return matched_homes
    else:
        return "There are no such properties in agent listings"

def get_info_about_nearby_homes(location: str, agent_id=None) -> list|str:
    """Tool that uses Zillow api to search for nearby properties given address of the house.
    Use case answer on questions related to the properties nearby.
    Valid params include "location":"location"."""
    gmaps = googlemaps.Client(key=os.getenv("GPLACES_API_KEY"))

    geocode_result = gmaps.geocode(location)
    coordinates = geocode_result[0]["geometry"]["location"]
    longitude = coordinates["lng"]
    latitude = coordinates["lat"]

    url = "https://zillow-com1.p.rapidapi.com/propertyByCoordinates"
    querystring = {"long": longitude, "lat": latitude, "d": "0.5", "includeSold": "false"}
    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    time.sleep(1.5)
    response = requests.get(url, headers=headers, params=querystring)

    on_market_property = []
    for element in response.json():
        element = element.get("property")
        if element and element["homeStatus"] != "OTHER":
            on_market_property.append(element)
    if len(on_market_property) == 0:
        return "There are no on-market properties nearby"
    if agent_id:
        result = check_matched_properties(agent_id, on_market_property)
        return result
    return on_market_property


def remove_data_about_dates_before_date(
    data: list[dict], date: datetime = datetime(2014, 1, 1)
) -> list[dict]:
    filtered_data = [
        d for d in data if datetime.strptime((d["time"]), "%Y-%m-%d %H:%M:%S") >= date
    ]
    return filtered_data


def get_tax_informatiom(location: str) -> dict:
    """Tool that uses Zillow api to search for house price, taxHistory and price history the house.
    Use case answer on questions related to the house price, tax. Valid params include "location":"location"."""
    result = __get_info_about_home_from_zillow(location)
    if isinstance(result, str):
        return result
    post_processed = result.json()["taxHistory"]

    # remove data, when the date was before this
    comparison_date = datetime(2014, 1, 1)
    # post process time to readable format
    for i in range(len(post_processed)):
        if "time" in post_processed[i].keys():
            post_processed[i]["time"] = convert_timestamp_to_date(
                post_processed[i]["time"]
            )

    post_processed = remove_data_about_dates_before_date(post_processed)

    priceHistory = result.json()["priceHistory"]
    # remove useless data
    for i in range(len(priceHistory)):
        if "attributeSource" in priceHistory[i].keys():
            priceHistory[i].pop("attributeSource")
        if "time" in priceHistory[i].keys():
            priceHistory[i]["time"] = convert_timestamp_to_date(priceHistory[i]["time"])
    priceHistory = remove_data_about_dates_before_date(priceHistory)

    post_processed.append(priceHistory)

    post_processed.append(
        {"current_price": f"{result.json()['price']} {result.json()['currency']}"}
    )
    post_processed.append({"propertyTaxRate": result.json()["propertyTaxRate"]})

    return post_processed


def search_properties_without_address(user_input: str):
    """Search properties without address tool, useful when need to search properties without specific address"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
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
        },
    )
    arguments = response["choices"][0]["message"]["function_call"]["arguments"]
    print("INPUT: ", user_input)
    print("ARGUMENTS: ", arguments)

    querystring = json.loads(arguments)
    if querystring.get("minPrice") and not querystring.get("maxPrice"):
        querystring["maxPrice"] = querystring.pop("minPrice")
    if querystring.get("minPrice") == querystring.get("maxPrice"):
        querystring.pop("minPrice")
    if querystring.get("bedsMin") and not querystring.get("bedsMax"):
        querystring["bedsMax"] = querystring.get("bedsMin")
    elif querystring.get("bedsMax") and not querystring.get("bedsMin"):
        querystring["bedsMin"] = querystring.get("bedsMax")

    if querystring.get("bathsMin") and not querystring.get("bathsMax"):
        querystring["bathsMax"] = querystring.get("bathsMin")
    elif querystring.get("bathsMax") and not querystring.get("bathsMin"):
        querystring["bathsMin"] = querystring.get("bathsMax")
    print("QUERYSTRING: ", querystring, type(querystring))
    for key, value in querystring.items():
        querystring[key] = str(value)
    print("arguments_after: ", querystring)

    base_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    # querystring = {"location": "Seattle", "home_type": "Houses", "maxPrice": "700000", "bedsMin": "3"}
    headers = {
        "X-RapidAPI-Key": os.getenv("X-RapidAPI-Key"),
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
    }
    time.sleep(1.5)
    result = requests.get(base_url, params=querystring, headers=headers)
    result = result.json()
    photos = {}
    if "props" not in result:
        res = "There is no result here. Ask user to specify main preferences like location, number of bedrooms, etc."
    else:
        result = result["props"][:10]

        for element in result:
            photos[element["address"]] = element["imgSrc"]

        res = f"This is a search result{result}. Show only base info for each house. Do not show links in response."

    return {"res": res, "photos": photos}


class Model:
    def __init__(self):
        self.max_length = 16_000

        class SearchInput(BaseModel):
            query: str = Field(
                description="should be an address in similar to this format 18070 Langlois Rd SPACE 212, Desert Hot Springs, CA 92241"
            )

        get_house_details_tool = Tool(
            name="Get House Details Tool",
            func=get_house_property,
            description="useful when need to search for info about house, but not about places near it.  The input to this tool should be an address of the house",
            args_schema=SearchInput,
        )

        find_properties_without_address_tool = Tool(
            name="Find properties without address",
            func=search_properties_without_address,
            description="useful when need to find properties and don't have a full address. The input to this tool shoul be user message+address",
        )

        find_distance_tool = Tool(
            name="Find distance tool",
            func=find_distance,
            description="useful when need to find distance between two addresses or how close two addresses are. You may use google_places tool to find address. The input to this tool should be a | separated list of addresses of length two, representing the two addresses you want to find distance between. For example, `13545 Cielo Azul Way, Desert Hot Springs, CA 92240|12105 Palm Dr, Desert Hot Springs, CA 92240` would be the input if you wanted to find distance between 13545 Cielo Azul Way, Desert Hot Springs, CA 92240 and 12105 Palm Dr, Desert Hot Springs, CA 92240.",
        )

        find_nearby_homes = Tool(
            name="Find nearby homes",
            func=get_info_about_nearby_homes,
            description="useful when need to search for info about other houses with status On Sale, that are listed and located in specific address, but not about places near it.  The input to this tool should be an address of the house",
        )

        get_tax_or_price_info = Tool(
            name="Get tax or price info",
            func=get_tax_informatiom,
            description="useful when need to search about tax or price history, reductions info about house.  The input to this tool should be an address of the house",
        )

        google_places = Tool(
            name="google_places",
            func=google_places_wrapper,
            description="""A wrapper around Google Places. 
        Useful for when you need to find address of some place near property
        discover addressed from ambiguous text or validate address.
        Input should be a search query.""",
        )

        tools = [
            get_house_details_tool,
            find_properties_without_address_tool,
            google_places,
            find_distance_tool,
            find_nearby_homes,
            get_tax_or_price_info,
        ]

        self.memory = ConversationBufferMemory(memory_key="chat_history")
        llm = ChatOpenAI(
            temperature=0.0,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=512,
            model="gpt-3.5-turbo-16k",
        )

        def _handle_error(error) -> str:
            _, though = str(error).split("Could not parse LLM output:")
            return though

        self.agent_chain = initialize_agent(
            tools,
            llm,
            memory=self.memory,
            agent="chat-zero-shot-react-description",
            verbose=True,
            early_stopping_method="generate",
            max_iterations=4,
            handle_parsing_errors=_handle_error,
            agent_kwargs={
                "system_message_prefix": "Answer to the question as best and comprehensively as possible, give a complete answer to the question. Inlude all important information in your Final Answer. You have access to the following tools:",
            },
        )
        # self.agent_chain.agent.llm_chain.prompt.messages[0].prompt.template = self.agent_chain.agent.llm_chain.prompt.messages[0].prompt.template.replace('Thought: I now know the final answer','Thought:  I have gathered detailed information to answer the question')
        print("Prompt ", self.agent_chain.agent.llm_chain.prompt.messages)

    def split_messages(self, text, contact_name):
        """Function to split chat history and return them as two separete lists. Last user message is skipped."""
        user_messages, ai_messages = [], []
        print("TEXT_HISTORY: ", text)
        for single_sample in text.split(f"{contact_name}:"):
            if single_sample.strip() != "":
                # skip user message
                if len(single_sample.split("Agent:")) == 2:
                    user_message, ai_message = single_sample.split("Agent:")
                    user_message = user_message.strip()
                    ai_message = ai_message.strip()
                    user_messages.append(user_message)
                    ai_messages.append(ai_message)

        return user_messages, ai_messages

    def add_memory(self, user_messages, ai_messages):
        """Add memory into LLM agent"""
        # system_prompt = "Please answer as a pirate, add 'Arr' in your messages"
        # self.memory.add_
        messages = zip(user_messages, ai_messages)
        history_length = len(list(messages))
        i = 0
        previous_human_messages = []
        previous_ai_messages = []
        for user_message, ai_message in zip(user_messages, ai_messages):
            # Add only two last messages from AI and USER
            if i >= history_length - 2:
                self.memory.chat_memory.add_user_message(user_message)
                self.memory.chat_memory.add_ai_message(ai_message)
                previous_human_messages.append(user_message)
                previous_ai_messages.append(ai_message)
            i += 1
        return previous_human_messages, previous_ai_messages

    async def response(self, user_input, message_history, contact_name):
        """Repsond on user's message"""
        user_messages, ai_messages = self.split_messages(message_history, contact_name)
        previous_human_messages, previous_ai_messages = self.add_memory(
            user_messages, ai_messages
        )
        # remove first AI and user message if it doesn't fit into memory
        self.clip_context()
        print("User question: ", user_input)
        ai_response = self.agent_chain.run(user_input)
        # return ai_response
        return self.enhance_ai_response(
            user_input, ai_response, previous_human_messages, previous_ai_messages
        )

    def history_add(self, message_history, contact_name):
        user_messages, ai_messages = self.split_messages(message_history, contact_name)
        previous_human_messages, previous_ai_messages = self.add_memory(
            user_messages, ai_messages
        )
        self.clip_context()
        messages = []
        print("PREVIOUS_HUMAN: ", previous_human_messages)
        print("USER_MESSAGES: ", user_messages)
        if user_messages and ai_messages:
            for human_message, ai_message in zip(previous_human_messages, previous_ai_messages):
                messages.append(HumanMessage(content=human_message))
                messages.append(AIMessage(content=ai_message))
        return messages

    def enhance_ai_response(
        self,
        user_input,
        rough_ai_response,
        previous_human_messages,
        previous_ai_messages,
    ):
        """Additional ChatGPT request to enhance AI response"""
        print("FINAL ANSWER: ", rough_ai_response)
        llm = ChatOpenAI(temperature=0.7, max_tokens=450, model="gpt-3.5-turbo")
        messages = [
            SystemMessage(
                content=f""" You are a friendly, helpful, and supportive real estate agent named Rick. Provide the information below in enhanced format. You should sound like a real human. Do not mention the address in your response, instead use words like "The house", "property", etc. Do not mention the address. If the user's message is something like "I am interested in (address)" just ask what could you help him with. You must not mention the tools that were used to get information.
                Below is the answer to the user question, use it only when it is related to the user question, you may modify it, but keep the meaning:
                {rough_ai_response} """
            )
        ]
        # for human_message, ai_message in zip(previous_human_messages, previous_ai_messages):
        #     messages.append(HumanMessage(content=human_message))
        #     messages.append(AIMessage(content=ai_message))
        if previous_human_messages:
            messages.append(HumanMessage(content=previous_human_messages[-1]))
        if previous_ai_messages:
            messages.append(AIMessage(content=previous_ai_messages[-1]))
        messages.append(HumanMessage(content=user_input))
        print("MESSAGES: ", messages)
        print("PREVIOUS_USER: ", previous_human_messages)
        print("PREVIOUS_AI: ", previous_ai_messages)
        refined_response = llm(messages).content
        print("enhanced response ", refined_response)
        return refined_response

    def get_content_length(self):
        total_length = 0
        for message in self.memory.chat_memory.messages:
            total_length += len(message.content)
        return total_length

    def clip_context(self):
        while self.get_content_length() > self.max_length:
            self.memory.chat_memory.messages.pop(0)
            self.memory.chat_memory.messages.pop(0)

    def get_summary_of_conversation(self, conversation):
        llm = ChatOpenAI(temperature=0.0, model="gpt-3.5-turbo-16k")
        prefix = """Here is client communication with ai agent named Rick, please give the output using the instructions below.Main rule is DO NOT BE REPETITIVE!"""
        # prefix = """Here is client communication with ai agent named Rick, please give summary of this coversation and provide questions on which AI was not able to answer in this conversation. when AI is unable to answer it usually has "I am sorry", "I apologize", "I don't know" etc. in response. If there are no such questions - please skip this."""
        sufix = """Follow this instructions when provide output, don't mentioned which instructions you use for formatting: INSTRUCTION_1 = simple short summary (2-3 sentences) of the conversation with client's main requirements and very important things which we need to negotiate in person to make a deal, like mortgage, discount and other very important questions. INSTRUCTION_2 = and key questions on which AI didn't give response during conversation (this question usually has "I am sorry", "I don't know", "I apologize" etc. - write ONLY this questions). INSTRUCTIONS_3 = If there is no information about scheduled appointment such as video call or tour and date and time - dont write about this anything, otherwise provide appointment details. Don't be repetitive. Always use client name at the start. If client name wasn't specified then use "Customer" instead.

Provide output in format
[Client's name] was interested in [address] and (if there is an appointment details, please write it using [INSTRUCTIONS_3]). 
Here write short summary using [INSTRUCTION_1].
Write the questions on which AI didn't was nat able to response using [INSTRUCTION_2].
DON'T BE REPETITIVE!
"""
        conversation = conversation[: self.max_length]
        prompt = f"{prefix} \n {conversation} \n {sufix}"
        print("PROMPT: ", prompt)
        messages = [HumanMessage(content=prompt)]
        summary = llm(messages).content
        return summary
