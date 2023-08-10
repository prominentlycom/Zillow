
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

# Load .env file
load_dotenv()

# Read an environment variable
os.environ["GPLACES_API_KEY"] =  os.getenv('GPLACES_API_KEY')




def find_zpid(
    location: Optional[str] = None, 
) -> dict:
    """Tool that uses Zillow api to find zpid given adress of the house. Use case find zpid when need to use get_house_property tool. Valid params include "location":"location"."""

    base_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    
    headers = {
	"X-RapidAPI-Key": os.getenv('X-RapidAPI-Key'),
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    querystring = {"page":"1"}
    
    if location is not None:
        querystring['location'] = location
        

    # print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)
    try :
        if isinstance(result.json(),list):
            return result.json()[0]["zpid"]
        return result.json()["zpid"]
    except :
        return "Sorry, could you please give full address"

def post_process_house_property(house_property):
    # house_property.pop('nearbyHomes')
    house_property.pop('listed_by')
    house_property.pop('priceHistory')
    house_property.pop('resoFacts')
    house_property.pop('taxHistory') 
    # house_property.pop('mlsDisclaimer')
    
    print(house_property)
    return house_property

def get_house_property(
    location: Optional[str] = None, 
) -> dict:
    """Tool that uses Zillow api to get house properties given adress of the house.Use case answer on questions related to the house. Valid params include "location":"location"."""

    zpid = find_zpid(location)
    if zpid == "Sorry, could you please give full address":
        return zpid
    
    base_url = "https://zillow-com1.p.rapidapi.com/property"
    
    headers = {
	"X-RapidAPI-Key": os.getenv('X-RapidAPI-Key'),
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    if zpid is not None:
        querystring = {"zpid":f"{zpid}"}
    else:
        raise Exception("Didn't get zpid")
        

    # print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)
    # print(result.json())
    post_processed = post_process_house_property(result.json())
    return post_processed

def get_quesion(x: Optional[str] = None):
    return x


def find_distance(addresses:str) -> str:
    '''Find distance tool, useful when need to find distance between two exact addresses'''
    print("FIND DISTANCE FUNCTION")
    address1, address2 = addresses.split('|')
    print(address1,address2)
    address_regex = '\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}'
    match = re.search(address_regex, address2)
    if not match:
        address2 = GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=1)).run(f'{address2} near {address1}').split('Address:')[1].split('\n')[0]
    print('distance between', address2, address1)
    gmaps = googlemaps.Client(key='AIzaSyAuj7gPxOpEWM6V6ckw0aErmR5FKS1-poI')
    data = gmaps.distance_matrix(address1,address2)
    my_dist =data['rows'][0]['elements'][0]
    if my_dist['status'] == 'NOT_FOUND':
        return "Sorry, couldn't find the distance"
    
    distance_km = my_dist['distance']['text']
    duration = my_dist['duration']['text']
    return f"Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the duration is {duration}"

def google_places_wrapper(query:str) -> str:
    """ A wrapper around Google Places. 
        Useful for when you need to find address of some place near property
        discover addressed from ambiguous text or validate address.
        Input should be a search query."""
    places_tool = GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=5))
    res = places_tool.run(query)
    print(f"Google places result : {res}")
    return res

def get_info_about_nearby_homes(location:str) -> str:
    """Tool that uses Zillow api to search for nearby properties given adress of the house. Use case answer on questions related to the properties nearby. Valid params include "location":"location"."""
    zpid = find_zpid(location)
    if zpid == "Sorry, could you please give full address":
        return zpid
    
    base_url = "https://zillow-com1.p.rapidapi.com/property"
    
    headers = {
	"X-RapidAPI-Key": "40953cc5afmsh9d09a374a48d7f2p115b37jsnca69ccb7de17",
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    if zpid is not None:
        querystring = {"zpid":f"{zpid}"}
    else:
        raise Exception("Didn't get zpid")
        

    # print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)
    # print(result.json())
    post_processed = result.json()['nearbyHomes']
    return post_processed

class Model():
    def __init__(self):
        self.max_length = 16_000
        
        class SearchInput(BaseModel):
            query: str = Field(description="should be an address in similar to this format 18070 Langlois Rd SPACE 212, Desert Hot Springs, CA 92241")

        class AdditionalInfo(BaseModel):
            add: str = Field(description="should be a question regarding information that needed to answer on person question")
            
        search_tool = Tool(
            name="Search Tool",
            func=get_house_property,
            description="useful when need to search for info about house, but not about places near it.  The input to this tool should be an address of the house",
            args_schema = SearchInput
        )

        # find_distance_tool = StructuredTool.from_function(find_distance)
        find_distance_tool = Tool(
            name="Find distance tool",
            func=find_distance,
            description="useful when need to find distance between two addresses. You may use google_places tool to find address. The input to this tool should be a | separated list of addresses of length two, representing the two addresses you want to find distance between. For example, `13545 Cielo Azul Way, Desert Hot Springs, CA 92240|12105 Palm Dr, Desert Hot Springs, CA 92240` would be the input if you wanted to find distance between 13545 Cielo Azul Way, Desert Hot Springs, CA 92240 and 12105 Palm Dr, Desert Hot Springs, CA 92240.",
            # args_schema = AdditionalInfo
        )

        find_nearby_homes = Tool(
            name = "Find nearby homes",
            func = get_info_about_nearby_homes,
            description = "useful when need to search for info about other houses that are listed and located in specific address, but not about places near it.  The input to this tool should be an address of the house"
        )

        google_places = Tool(
            name = 'google_places',
            func = google_places_wrapper,
            description = """A wrapper around Google Places. 
        Useful for when you need to find address of some place near property
        discover addressed from ambiguous text or validate address.
        Input should be a search query."""
        )
        

        
        tools = [search_tool, google_places, find_distance_tool,find_nearby_homes]

        self.memory = ConversationBufferMemory(memory_key="chat_history")
        llm = ChatOpenAI(temperature=0.0,openai_api_key="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",max_tokens=512,model="gpt-3.5-turbo-16k")

        def _handle_error(error) -> str:
            _,though = str(error).split("Could not parse LLM output:")
            return though

        self.agent_chain = initialize_agent(tools,llm,memory=self.memory,agent="chat-zero-shot-react-description", verbose=True,early_stopping_method="generate",max_iterations=5, handle_parsing_errors=_handle_error)

    def split_messages(self,text):
        user_messages, ai_messages = [],[]
        for single_sample in text.split('You:'):
            if single_sample.strip() != '':
                if len(single_sample.split("AI:")) == 2:
                    user_message, ai_message = single_sample.split("AI:")
                    user_message = user_message.strip()
                    ai_message = ai_message.strip()
                    user_messages.append(user_message)
                    ai_messages.append(ai_message)


        return user_messages, ai_messages

    def add_memory(self,user_messages, ai_messages):
        messages = zip(user_messages,ai_messages)
        history_length = len(list(messages))
        i = 0
        previous_human_messages = []
        previous_ai_messages = []
        for user_message,ai_message in zip(user_messages,ai_messages): 
            if i >= history_length-2:
                self.memory.chat_memory.add_user_message(user_message)
                self.memory.chat_memory.add_ai_message(ai_message)
                previous_human_messages.append(user_message)
                previous_ai_messages.append(ai_message)
            i+=1
        return previous_human_messages, previous_ai_messages
        
    def response(self,user_input,message_history):
        user_messages, ai_messages = self.split_messages(message_history)
        previous_human_messages, previous_ai_messages = self.add_memory(user_messages, ai_messages)
        self.clip_context()
        ai_response = self.agent_chain.run(user_input)
        return self.refine_ai_response(user_input,ai_response,previous_human_messages, previous_ai_messages)

    def refine_ai_response(self,user_input,rough_ai_response,previous_human_messages, previous_ai_messages):
        llm = ChatOpenAI(temperature=0.0,openai_api_key="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",max_tokens=1200)
        messages = [
                    SystemMessage(
                        content=f"""The AI is a friendly, helpful and supportive real estate agent named Rick, have a conversation with client, please answer on this client's message.  Don't provide general information If the user message is something like "I am interested in [address]". Do not sound repetative or too much like a servant.
                Below is the information that you might need to answer the question, use it only when it is related to the user message:
                {rough_ai_response}"""
                    )
                ]
        for human_message, ai_message in zip(previous_human_messages, previous_ai_messages):
            messages.append(HumanMessage(content=human_message))
            messages.append(AIMessage(content=ai_message))
        messages.append(HumanMessage(content=user_input))
        refined_response = llm(messages).content
        
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
        