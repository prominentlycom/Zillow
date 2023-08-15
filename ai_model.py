
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
os.environ["GPLACES_API_KEY"] =  os.getenv('GPLACES_API_KEY')


def convert_timestamp_to_date(timestamp):
    # Convert milliseconds to seconds by dividing by 1000
    timestamp_seconds = timestamp / 1000
    
    # Create a datetime object from the timestamp
    datetime_obj = datetime.fromtimestamp(timestamp_seconds)
    
    # Format the datetime object as a string and return it
    formatted_date = datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_date


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
    """Remove some information from zillow listing to fit into LLM's context """
    house_property.pop('nearbyHomes')
    house_property.pop('listed_by')
    house_property.pop('priceHistory')
    house_property.pop('resoFacts')
    house_property.pop('attributionInfo')
    house_property.pop('taxHistory')  
    return house_property

def __get_info_about_home_from_zillow(location:str):
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
        

    result = requests.get(base_url, params=querystring, headers=headers)
    return result

def get_house_property(
    location: Optional[str] = None, 
) -> dict:
    """Tool that uses Zillow api to get house properties given adress of the house.Use case answer on questions related to the house. Valid params include "location":"location"."""
    result = __get_info_about_home_from_zillow(location)
    post_processed = post_process_house_property(result.json())
    return post_processed


def find_distance(addresses:str) -> str:
    '''Find distance tool, useful when need to find distance between two exact addresses'''
    splitted_addresses = addresses.split('|')
    gmaps = googlemaps.Client(key = os.getenv('GPLACES_API_KEY'))
    
    if len(splitted_addresses) == 2:
        address1, address2 =  splitted_addresses[0],splitted_addresses[1]
        address_regex = '\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}'
        match = re.search(address_regex, address2)
        if not match:
            address2 = GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=1)).run(f'{address2} near {address1}').split('Address:')[1].split('\n')[0]
        data = gmaps.distance_matrix(address1,address2)
        my_dist =data['rows'][0]['elements'][0]
        if my_dist['status'] == 'NOT_FOUND':
            return "Sorry, couldn't find the distance"
        
        distance_km = my_dist['distance']['text']
        if distance_km == "1 m":
            distance_km = 'less than 200 m'
        duration = my_dist['duration']['text']
        return f"Include this information while answering \n Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the duration is {duration}"
    elif len(splitted_addresses) > 2:
        answer = ''
        address1 = splitted_addresses[0]
        for i in range(1,len(splitted_addresses)):
            address2 = splitted_addresses[i]
            data = gmaps.distance_matrix(address1,address2)
            my_dist =data['rows'][0]['elements'][0]
            if my_dist['status'] == 'NOT_FOUND':
                return "Sorry, couldn't find the distance"
            
            distance_km = my_dist['distance']['text']
            if distance_km == "1 m":
                distance_km = 'less than 200 m'
            duration = my_dist['duration']['text']
            answer += f"Distance from {data['destination_addresses'][0]} to {data['origin_addresses'][0]} is {distance_km} and the duration is {duration}\n"
        return f"Include this information while answering \n{answer}"
    
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
    result = __get_info_about_home_from_zillow(location)
    post_processed = result.json()['nearbyHomes']
    return post_processed

def remove_data_about_dates_before_date(data:list[dict], date:datetime = datetime(2014, 1, 1)) -> list[dict]:
    filtered_data = [d for d in data if datetime.strptime((d['time']), '%Y-%m-%d %H:%M:%S') >= date]
    return filtered_data

def get_tax_informatiom(location:str) -> dict:
    """Tool that uses Zillow api to search for house price, taxHistory and price history the house. Use case answer on questions related to the house price, tax. Valid params include "location":"location". """
    result = __get_info_about_home_from_zillow(location)
    post_processed = result.json()['taxHistory']


    #remove data, when the date was before this
    comparison_date = datetime(2014, 1, 1)
    #post process time to readable format
    for i in range(len(post_processed)):
        if 'time' in post_processed[i].keys():
            post_processed[i]['time'] = convert_timestamp_to_date(post_processed[i]['time'])

    post_processed = remove_data_about_dates_before_date(post_processed)
          
    priceHistory = result.json()['priceHistory']
    #remove useless data
    for i in range(len(priceHistory)):
        if 'attributeSource' in priceHistory[i].keys():
            priceHistory[i].pop('attributeSource')
        if 'time' in priceHistory[i].keys():
            priceHistory[i]['time'] = convert_timestamp_to_date(priceHistory[i]['time'])
    priceHistory = remove_data_about_dates_before_date(priceHistory)
            
    post_processed.append(priceHistory)
    
    post_processed.append({'current_price':f"{result.json()['price']} {result.json()['currency']}"})
    post_processed.append({'propertyTaxRate':result.json()['propertyTaxRate']})
    return post_processed
    
class Model():
    def __init__(self):
        self.max_length = 16_000
        
        class SearchInput(BaseModel):
            query: str = Field(description="should be an address in similar to this format 18070 Langlois Rd SPACE 212, Desert Hot Springs, CA 92241")

        get_house_details_tool = Tool(
            name="Get House Details Tool",
            func=get_house_property,
            description="useful when need to search for info about house, but not about places near it.  The input to this tool should be an address of the house",
            args_schema = SearchInput
        )

        find_distance_tool = Tool(
            name="Find distance tool",
            func=find_distance,
            description="useful when need to find distance between two addresses or how close two addresses are. You may use google_places tool to find address. The input to this tool should be a | separated list of addresses of length two, representing the two addresses you want to find distance between. For example, `13545 Cielo Azul Way, Desert Hot Springs, CA 92240|12105 Palm Dr, Desert Hot Springs, CA 92240` would be the input if you wanted to find distance between 13545 Cielo Azul Way, Desert Hot Springs, CA 92240 and 12105 Palm Dr, Desert Hot Springs, CA 92240.",
        )

        find_nearby_homes = Tool(
            name = "Find nearby homes",
            func = get_info_about_nearby_homes,
            description = "useful when need to search for info about other houses that are listed and located in specific address, but not about places near it.  The input to this tool should be an address of the house"
        )

        get_tax_or_price_info = Tool(
            name = "Get tax or price info",
            func = get_tax_informatiom,
            description = "useful when need to search about tax or price history, reductions info about house.  The input to this tool should be an address of the house"
        )
        
        google_places = Tool(
            name = 'google_places',
            func = google_places_wrapper,
            description = """A wrapper around Google Places. 
        Useful for when you need to find address of some place near property
        discover addressed from ambiguous text or validate address.
        Input should be a search query."""
        )
        

        
        tools = [get_house_details_tool, google_places, find_distance_tool,find_nearby_homes,get_tax_or_price_info]

        self.memory = ConversationBufferMemory(memory_key="chat_history")
        llm = ChatOpenAI(temperature=0.0,openai_api_key="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",max_tokens=512,model="gpt-3.5-turbo-16k")

        def _handle_error(error) -> str:
            _,though = str(error).split("Could not parse LLM output:")
            return though

        self.agent_chain = initialize_agent(tools,llm,memory=self.memory,agent="chat-zero-shot-react-description",
                                            verbose=True,early_stopping_method="generate",max_iterations=4, handle_parsing_errors=_handle_error,
                                            agent_kwargs={
        'system_message_prefix':"Answer to the question as best and comprehensively as possible, give a complete answer to the question. Inlude all important information in your Final Answer. You have access to the following tools:",
    })  
        # self.agent_chain.agent.llm_chain.prompt.messages[0].prompt.template = self.agent_chain.agent.llm_chain.prompt.messages[0].prompt.template.replace('Thought: I now know the final answer','Thought:  I have gathered detailed information to answer the question')
        print("Prompt ", self.agent_chain.agent.llm_chain.prompt.messages)

    def split_messages(self,text):
        """Function to split chat history and return them as two separete lists. Last user message is skipped."""
        user_messages, ai_messages = [],[]
        for single_sample in text.split('You:'):
            if single_sample.strip() != '':
                #skip user message
                if len(single_sample.split("AI:")) == 2:
                    user_message, ai_message = single_sample.split("AI:")
                    user_message = user_message.strip()
                    ai_message = ai_message.strip()
                    user_messages.append(user_message)
                    ai_messages.append(ai_message)


        return user_messages, ai_messages

    def add_memory(self,user_messages, ai_messages):
        """Add memory into LLM agent"""
        # system_prompt = "Please answer as a pirate, add 'Arr' in your messages"
        # self.memory.add_
        messages = zip(user_messages,ai_messages)
        history_length = len(list(messages))
        i = 0
        previous_human_messages = []
        previous_ai_messages = []
        for user_message,ai_message in zip(user_messages,ai_messages): 
            #Add only two last messages from AI and USER
            if i >= history_length-2:
                self.memory.chat_memory.add_user_message(user_message)
                self.memory.chat_memory.add_ai_message(ai_message)
                previous_human_messages.append(user_message)
                previous_ai_messages.append(ai_message)
            i+=1
        return previous_human_messages, previous_ai_messages
        
    def response(self,user_input,message_history):
        """Repsond on user's message"""
        user_messages, ai_messages = self.split_messages(message_history)
        previous_human_messages, previous_ai_messages = self.add_memory(user_messages, ai_messages)
        #remove first AI and user message if it doesn't fit into memory
        self.clip_context()
        print("User question: ",user_input)
        ai_response = self.agent_chain.run(user_input)
        print('Langchain answer ', ai_response)
        return self.enhance_ai_response(user_input,ai_response,previous_human_messages, previous_ai_messages)

    def enhance_ai_response(self,user_input,rough_ai_response,previous_human_messages, previous_ai_messages):
        """Additional ChatGPT request to enhance AI response"""
        llm = ChatOpenAI(temperature=0.0,max_tokens=600,model="gpt-3.5-turbo")
        messages = [
                    SystemMessage(
                        content=f"""You are friendly, helpful and supportive real estate agent named Rick, please answer concisely on last client's message.
Follow this rules while answering:
- Sound like real human
- Do not sound repetative or too much like a servant.
- Do not mention address in the response, instead use words like "The house", "property", etc. Do not mention the address.
- Also do not answer with templates like 'The distance is [distance]'.
- If the user message is something like "I am interested in [address]" just ask what could you help him with.
- Do not include information with clipped data
- Do not mention any tools that were used to get information
Below is the information that you might need to answer the question, use it only when it is related to the user question, you may modify it, but keep the meaning:
{rough_ai_response}

Examples :
User: How far is the beach?
AI: The beach is 200 km away from the house. Do you help with something else?

User: What is the price of the house?
AI: Current price of this house is 100 as mentione on Zillow. Let me know if there's anything else I can assist you with regarding this property.


"""
                    )
                ]
        # for human_message, ai_message in zip(previous_human_messages, previous_ai_messages):
        #     messages.append(HumanMessage(content=human_message))
        #     messages.append(AIMessage(content=ai_message))

        messages.append(HumanMessage(content=user_input))
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


    def get_summary_of_conversation(self,conversation):
        llm = ChatOpenAI(temperature=0.0,model="gpt-3.5-turbo-16k")
        prefix = """Here is client communication with ai, please give question on which AI was not able to answer, usually when AI is unable to answer it usually has "I am sorry", "I apologize" etc. in response."""
        sufix = """As output please provide only questions on which AI didn't give repsonse during conversation. Do not provide questions that were answered in other messages.
Provide output in format
User question on which AI didn't answer: 
1. question
2. question
"""
        conversation = conversation[:self.max_tokens]
        prompt = f'{prefix} \n {conversation} \n {sufix}'
        messages =[
            HumanMessage(content = prompt)
        ]
        summary = llm(messages).content
        return summary