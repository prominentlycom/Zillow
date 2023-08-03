from typing import Union
from fastapi import FastAPI
from ai_model2 import Model
from pydantic import BaseModel
from fastapi import Request
import openai
import re
import requests

openai.api_key = "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"
app = FastAPI()

class UserMessage(BaseModel):
    message: str
    address : str

# @app.get("/")
# def read_root():
#     return {"Hello": "World"}


# @app.get("/items/{item_id}")
# def read_item(item_id: int, q: Union[str, None] = None):
#     return {"item_id": item_id, "q": q}

chatmodel = Model()


@app.post('/send_message_to_ai')
async def send_message_to_ai(request:Request):
    res = await request.json()
    
    user_message = res['customData']['message']
    address = res['customData']['address']
    email = res.get('email')
    phone = res.get('phone')
    user_query = f'{user_message} +  I am interested in {address}'
    
    print(user_query)
    ai_response = chatmodel.response(user_query)
    requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c',json={'bot_response' : ai_response, 'phone':phone,'email':email})
    return {'bot_response' : ai_response}


def clip_history(message_history,prompt):
    max_lenght = 8_000
    current_length = len(prompt+message_history)
    if current_length > max_lenght:
        prompt = prompt
        need_to_remove = current_length - max_lenght
        message_history = message_history[need_to_remove:]
    return message_history

@app.post('/clip_message_history')
async def clip_message_history(request:Request):
    res = await request.json()
    
    message_history = res['customData']['message_history']
    prompt = res['customData']['openai_prompt']
    print("PROMPT IS",prompt)
    email = res.get('email')
    phone = res.get('phone')
    message_history = clip_history(message_history,prompt)
    print('Clipped message : ',message_history)
    requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/94a02662-1c53-4f5b-8573-a9f412c8d568',json={'message_history' : message_history, 'phone':phone,'email':email})
    # return {'message_history' : message_history}

# system_prompt = '''If the questions is related to specific property information please answer yes else say no. Do not add anything else.
# Examples:
# User: What is the price of the house?
# AI: Yes

# User: How can I rent a house?
# AI: Yes

# User: Are there any clubs near the house?
# AI: Yes

# User: What is the cost of living there?
# AI: Yes

# User: How can I address you?
# AI: No'''

# @app.post('/shouldAskForExtraInfo')
# async def shouldAskForExtraInfo(request:Request):
#     res = await request.json()
#     print('#########')
#     print(res)
#     print('#########')
#     user_message = res['customData']['message']
#     address = res['customData']['address']
#     email = res['email']
#     phone = res['phone']
#     print(address)
#     result = openai.ChatCompletion.create(
#             model="gpt-3.5-turbo",
#             max_tokens=256,
#             temperature = 0,
#             messages=[
#                 {"role": "system", "content": f"{system_prompt}"},
#                 {"role": "user", "content": user_message}]
#             )
#     answer = result['choices'][0]['message']['content']
#     if 'yes' in answer.lower():
#         print('need to ask extra info')
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/08119398-afc3-4d05-9e75-899388717c2b', json = {'message':user_message,'need_extra_info':'True', 'email':email,'phone':phone})
        
#         return {'need_extra_info':'True'}
#     else:
#         print('No need to ask extra info')
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/08119398-afc3-4d05-9e75-899388717c2b', json = {'message':user_message,'need_extra_info':'False', 'email':email,'phone':phone})
        
#         return {'need_extra_info':'False'}


# @app.post('/get_address')
# async def get_address(request:Request):
#     res = await request.json()
#     headers = request.headers
#     print('HEADERS  ', headers)
#     print(f'{res}')
#     address_regex = '\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}'
#     user_message = res['customData']['message']
#     email = res['email']
#     phone = res['phone']
#     print(f'USER MESSAGE {user_message}')
#     match = re.search(address_regex, user_message)
    
#     if match:
#         print('Address found  ',{'address':match.group()})
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/ddfd4671-13a1-4c55-b370-b7c5fc77dbfe', json = {'message':user_message,'address':match.group(), 'email':email,'phone':phone})
        
#         return {'address':match.group(), 'status':200}
#     else:
#         print('Address not found  ',user_message)
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/ddfd4671-13a1-4c55-b370-b7c5fc77dbfe', json = {'message':user_message,'address':'not found', 'email':email,'phone':phone})
#         return {'address':'not found','status':200}


# async def print_request(request):
#         print(f'request header       : {dict(request.headers.items())}' )
#         print(f'request query params : {dict(request.query_params.items())}')  
#         try : 
#             print(f'request json         : {await request.json()}')
#         except Exception as err:
#             # could not parse json
#             print(f'request body         : {await request.body()}')
    
    
# @app.post("/printREQUEST")
# async def create_file(request: Request):
#     try:
#         await print_request(request)
#         return {"status": "OK"}
#     except Exception as err:
#         print(f'could not print REQUEST: {err}')
#         return {"status": "ERR"}




# a = {"OpenAI Prompt": "The AI is a friendly, helpful and supportive real estate agent in Seattle named Rick. The main goal of Rick is to first gather necessary information to qualify prospective buyers and sellers of real estate in the Greater Seattle area and then book an appointment once that information is collected. Rick is talking to a client who could be either a seller or a buyer. Rick should first ask any qualifying question from the client to determine the type of client, whether they are a buyer or a seller. Rick may first ask the client, 'What are you looking to do? Do you want to sell or buy?'. Then, Rick should be able to know if the client wants to buy a home or sell their current home based on the client's answer. If the client is a buyer then Rick should ask first, 'What is your ideal buying timeframe?' Rick should ask one question at a time. Rick should then ask the buyer 'What is your budget?' Once all of this information is collected, Rick should then ask the buyer 'Do you have a pre-approval letter?' After this, Rick should ask one last question from the buyer, 'Is there anything else I should know before our meeting?' After all the mentioned questions are done, then Rick should only then book an appointment for that buyer. Rick must not book the appointment for the buyer until he has asked all the questions from the buyer. On the other hand, if the client is wanting to sell their house, then Rick should first ask 'When are you looking to sell your house?' Once this information is collected then, Rick should ask 'Approximately how much is your house worth?' After this, Rick should ask 'How many bedrooms does your house have?' After all that, Rick should ask 'How many bathrooms?' After this, Rick should ask 'What year was your house built?' Then, Rick should ask 'What`s the sq. footage of your home?' Lastly, once all of these questions have been answered then Rick should ask 'Anything else I should know before our meeting?' After all that, Rick should only then book an appointment for that seller. Rick must not book the appointment until the client has answered the relevant questions."}


# {'Calendar ID': 'JPaVx6OwfAZzuslGyIbT', 
#  'OpenAI Prompt': "The AI is a friendly, helpful and supportive real estate agent in Seattle named Rick. The main goal of Rick is to first gather necessary information to qualify prospective buyers and sellers of real estate in the Greater Seattle area and then book an appointment once that information is collected. Rick is talking to a client who could be either a seller or a buyer. Rick should first ask any qualifying question from the client to determine the type of client, whether they are a buyer or a seller. Rick may first ask the client, “What are you looking to do? Do you want to sell or buy?”. Then, Rick should be able to know if the client wants to buy a home or sell their current home based on client's answer. If the client is a buyer then Rick should ask first, “What is your ideal buying timeframe?” Rick should ask one question at a time. Rick should then ask the buyer “What is your budget?” Once all of this information is collected, Rick should then ask the buyer “Do you have a pre-approval letter?” After this, Rick should ask one last question from the buyer, “Is there anything else I should know before our meeting?” After all the mentioned questions are done, then Rick should only then book an appointment for that buyer. Rick must not book the appointment for the buyer until he has asked all the questions from the buyer. On the other hand, if the client is wanting to sell their house, then Rick should first ask “When are you looking to sell your house?” Once this information is collected then, Rick should ask “Approximately how much is your house worth?” After this, Rick should ask “How many bedrooms does your house have?” After all that, Rick should ask “How many bathrooms?” After this, Rick should ask “What year was your house built?” Then, Rick should ask “What’s the sq. footage of your home?” Lastly, once all of these questions have been answered then Rick should ask “Anything else I should know before our meeting?” After all that, Rick should only then book an appointment for that seller. Rick must not book the appointment until the client has answered the relevant questions.",
#  'Bot Status': 'Bot', 'Conversation': "AI: Hi, Nazar, it's Aaron. Anything I can help you with today? You:  AI:  You:  AI:  You:  AI:  You:  AI:  AI:  You: START AI:  You: Hi You: ", 'Response': '', 'Username': '', 'Message': '', 'Payment': '', 'Linkedin Profile': '', 'Business Category': '', 'Password': '', 'Linkedin': '', 'Select Service': '', 'Number Of Locations': '', 'Services Needed': '', 'Current Email Sequence': '', 'Number Of Location': '', 'OpenAI FAQ': '', 'Do you serve commercial clients?': '', 'What is your current monthly revenue?': '', 'Do you currently have a marketing budget?': '', 'Do you currently serve commercial clients?': '', 'Revenue': '', 'Preferred Types of Clients': '', 'Annual Revenue': '', 'Have you bought a property since we last spoke?': '', 'Are you currently in the market for a property?': '', 'What type of property are you interested in?': '', 'What is your budget?': '', 'Preferred Location?': '', 'What is your timeline for purchasing a property?': '', 'Are you working with another real estate agent?': '', "What are the most important features you're looking for in a property?": '', 'contact_id': 'dhpPDQAGQYYjcaTVH0QU', 'first_name': 'Nazar', 'last_name': 'Andrushko', 'full_name': 'Nazar Andrushko', 'email': 'nazar.andrushko@litslink.com', 'phone': '+380630772038', 'tags': 'qualified,robot reply', 'country': 'CA', 'date_created': '2023-07-24T08:26:00.246Z', 'full_address': '', 'contact_type': 'lead', 'location': {'name': 'Envy', 'address': '1030 Tara Crescent', 'city': 'Parksville', 'state': 'British Columbia', 'country': 'CA', 'postalCode': 'V9P 2W5', 'fullAddress': '1030 Tara Crescent, Parksville British Columbia V9P 2W5', 'id': 'Cr4I5rLHxAhYI19SvpP6'}, 'message': {'type': 3, 'body': 'WoW\n', 'direction': 'inbound'}, 'workflow': {'id': 'c79e54d8-c6d0-4751-bfa9-8e6627f04fab', 'name': 'Test Workfloww'}, 'contact': {'attributionSource': {'sessionSource': 'CRM UI', 'mediumId': None, 'medium': 'manual'}, 'lastAttributionSource': {}}, 'attributionSource': {}, 'customData': {}}