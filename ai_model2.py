from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatAnthropic
from langchain.chat_models import ChatOpenAI
from langchain import LLMChain
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.agents import ZeroShotAgent, Tool, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain import OpenAI, LLMChain
from langchain.utilities import GoogleSearchAPIWrapper
from human_tool import HumanInputRun
from pydantic import BaseModel, Field
import requests
from typing import Optional
import openai
from langchain.tools import GooglePlacesTool
import os
import pickle

os.environ["GPLACES_API_KEY"] = "AIzaSyAuj7gPxOpEWM6V6ckw0aErmR5FKS1-poI"


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
from langchain.memory.chat_message_histories import FileChatMessageHistory
from langchain.utilities.google_places_api import GooglePlacesAPIWrapper

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
            description="useful when need to search for info about house located in specific address",
            args_schema = SearchInput
        )

        ask_for_addition_info_tool = Tool(
            name="Ask for additional information",
            func=get_quesion,
            description="useful when need to ask for additional info",
            args_schema = AdditionalInfo
        )
        
        tools = [search_tool,GooglePlacesTool(api_wrapper=GooglePlacesAPIWrapper(top_k_results=5))]
        
        prefix = """Have a conversation with a client, answer on questions like human real estate agent. Do not mention house address in each response. Ask clarifying questions to help client. Try not to sound repetative and don't output answers like facts. You have access to the following tools:"""
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
        # self.chat_history_memory = FileChatMessageHistory("chat_history.txt")
        # initial_memory = self.chat_history_memory.messages
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        llm = OpenAI(temperature=0.5,openai_api_key="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",max_tokens=512)
        self.llm = llm
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        agent = ZeroShotAgent(llm_chain=llm_chain, tools=tools, allowed_tools=["SEARCH INFO ABOUT HOUSE USING IT'S ADDRESS",'google_places'], verbose=True, max_iterations=5,
    early_stopping_method="generate")
        # agent_kwargs = {
        #     "extra_prompt_messages": [ConversationBufferMemory(memory_key="memory", return_messages=True)],
        # }
        # self.agent_chain = initialize_agent(
        #     tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, ver bose=True, agent_kwargs=agent_kwargs
        #     )
        self.agent_chain = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True, memory=self.memory, handle_parsing_errors=True, max_iterations=3,allowed_tools=["SEARCH INFO ABOUT HOUSE USING IT'S ADDRESS",'google_places'],
        early_stopping_method="generate"
        )
        
    def response(self,user_input):
        self.clip_context()
        ai_response = self.agent_chain.run(user_input)
        # self.chat_history_memory.add_user_message(user_input)
        # self.chat_history_memory.add_ai_message(ai_response)
        print(self.memory.chat_memory.messages)
        self.memory.chat_memory.messages.pop(0)
        self.memory.chat_memory.messages.pop(0)
        return self.refine_ai_response(user_input,ai_response)

    def refine_ai_response(self,user_input,rough_ai_response):
        llm = ChatOpenAI(temperature=0.5,openai_api_key="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")
        messages = [
            SystemMessage(
                content=f"""You are real estate agent, have a convercation with client, please answer on this client's message. Use information below to proceed 
        {rough_ai_response}"""
            ),
            HumanMessage(
                content=f"""Client message: {user_input}
        AI: """
            ),
        ]
        refined_response = llm(messages).content
        
        return refined_response

    def save_last_memory_into_pickle(self):
        pickled_str = pickle.dumps(self.memory)

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
            # self.chat_history_memory.clear()
        