from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatAnthropic
from langchain.chat_models import ChatOpenAI
from langchain import LLMChain

from langchain.agents import ZeroShotAgent, Tool, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain import OpenAI, LLMChain
from langchain.utilities import GoogleSearchAPIWrapper
from human_tool import HumanInputRun
from pydantic import BaseModel, Field
import requests
from typing import Optional
import openai


def find_zpid(
    location: Optional[str] = None, 
) -> dict:
    """Tool that uses Zillow api to find zpid given adress of the house. Use case find zpid when need to use get_house_property tool. Valid params include "location":"location"."""

    base_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    
    headers = {
	"X-RapidAPI-Key": "40953cc5afmsh9d09a374a48d7f2p115b37jsnca69ccb7de17",
	"X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    querystring = {"page":"1"}
    
    if location is not None:
        querystring['location'] = location
        

    # print(f'Search with {querystring}')
    result = requests.get(base_url, params=querystring, headers=headers)
    print(f'ZPID = {result.json()}')
    try :
        if isinstance(result.json(),list):
            return result.json()[0]["zpid"]
        return result.json()["zpid"]
    except :
        print('EXCEPTION')
        return "Sorry, could you please give full address"

def post_process_house_property(house_property):
    house_property.pop('nearbyHomes')
    house_property.pop('listed_by')
    house_property.pop('priceHistory')
    house_property.pop('resoFacts')
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
    post_processed = post_process_house_property(result.json())
    return post_processed

def get_quesion(x: Optional[str] = None):
    return x


class Model():
    def __init__(self):
        self.max_length = 16_000
        
        class SearchInput(BaseModel):
            query: str = Field(description="should be an address in similar to this format 18070 Langlois Rd SPACE 212, Desert Hot Springs, CA 92241")

        class AdditionalInfo(BaseModel):
            query: str = Field(description="should be a question regarding information that needed to answer on person question")
            
        search_tool = Tool(
            name="SEARCH INFO ABOUT HOUSE USING IT'S ADDRESS",
            func=get_house_property,
            description="useful when need to search for infor about house located in specific address",
            args_schema = SearchInput
        )

        ask_for_addition_info_tool = Tool(
            name="Ask for additional information",
            func=get_quesion,
            description="useful when need to ask for additional info",
            args_schema = AdditionalInfo
        )
        
        tools = [search_tool]
        
        prefix = """You are a real estate agent, have a conversation with a human, answering the following questions or ask for additional information as best you can, be polite and nice. Do not mention address in each response, if you need some additional info ask a person about it . You have access to the following tools:"""
        suffix = """Begin!"

        {chat_history}
        Question: {input}
        {agent_scratchpad}"""

        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=["input", "chat_history", "agent_scratchpad"],
        )
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        llm = OpenAI(temperature=0,openai_api_key="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")
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        agent = ZeroShotAgent(llm_chain=llm_chain, tools=tools, allowed_tools=["SEARCH INFO ABOUT HOUSE USING IT'S ADDRESS"], verbose=True, max_iterations=5,
    early_stopping_method="generate")
        # agent_kwargs = {
        #     "extra_prompt_messages": [ConversationBufferMemory(memory_key="memory", return_messages=True)],
        # }
        # self.agent_chain = initialize_agent(
        #     tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True, agent_kwargs=agent_kwargs
        #     )

        self.agent_chain = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True, memory=self.memory, handle_parsing_errors=True, max_iterations=3,allowed_tools=["SEARCH INFO ABOUT HOUSE USING IT'S ADDRESS"],
        early_stopping_method="generate"
        )
    def response(self,user_input):
        self.clip_context()
        return self.agent_chain.run(user_input)
        
    def get_content_length(self):
        total_length = 0
        for message in self.memory.chat_memory.messages:
            total_length += len(message.content)
        return total_length
    
    def clip_context(self):
        while self.get_content_length() > self.max_length:
            print("Removed two messages")
            self.memory.chat_memory.messages.pop(0)
            self.memory.chat_memory.messages.pop(0)
        