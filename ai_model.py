import requests
from typing import Optional, Type
from langchain.tools.base import StructuredTool
from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatAnthropic
from langchain.chat_models import ChatOpenAI

def find_zpid(
    location: Optional[str] = None, 
) -> dict:
    """Tool that uses Zillow api to find zpid given adress of the house. Use case find zpid when someone is interested in house. Valid params include "location":"location"."""

    base_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    
    headers = {
	"X-RapidAPI-Key": "cad9458103mshe64bf73cf4954ebp1be8eajsn95afe237a166",
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    querystring = {"page":"1"}
    
    if location is not None:
        querystring['location'] = location
        

    print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)
    return result.json()



def post_process_house_property(house_property):
    house_property.pop('nearbyHomes')
    house_property.pop('listed_by')
    house_property.pop('priceHistory')
    house_property.pop('resoFacts')
    return house_property

def get_house_property(
    zpid: Optional[int] = None, 
) -> dict:
    """Tool that uses Zillow api to get information about house or it's neighborhood given zpid of the house.Use case answer on questions related to the house or it's neighborhood. Valid params include "zpid":"zpid"."""

    base_url = "https://zillow-com1.p.rapidapi.com/property"
    
    headers = {
	"X-RapidAPI-Key": "cad9458103mshe64bf73cf4954ebp1be8eajsn95afe237a166",
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    
    if zpid is not None:
        querystring = {"zpid":f"{zpid}"}
    else:
        raise Exception("Didn't get zpid")
        

    result = requests.get(base_url, params=querystring, headers=headers)
    post_processed = post_process_house_property(result.json())
    return post_processed


class Model():
    def __init__(self):
        self.max_length = 16_000
        find_zpid_tool = StructuredTool.from_function(find_zpid)
        get_house_property_tool = StructuredTool.from_function(get_house_property)
        tools = [find_zpid_tool, get_house_property_tool] # Add any tools here
        llm = ChatOpenAI(temperature=0,openai_api_key="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") 
        chat_history = MessagesPlaceholder(variable_name="chat_history")
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        self.agent_chain = initialize_agent(
            tools, 
            llm, 
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION, 
            verbose=True, 
            memory=memory, 
            agent_kwargs = {
                "memory_prompts": [chat_history],
                "input_variables": ["input", "agent_scratchpad", "chat_history"]
            }
        )


    def response(self,user_input):
        response = self.agent_chain.run(user_input)
        return response