import requests
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from ai_model import Model


# Load .env file
load_dotenv()

# Read an environment variable
os.environ["OPENAI_API_KEY"] =  os.getenv('OPENAI_API_KEY')
os.environ["GPLACES_API_KEY"] =  os.getenv('GPLACES_API_KEY')

app = FastAPI()

@app.post('/send_message_to_ai')
async def send_message_to_ai(request:Request):
    chatmodel = Model()

    res = await request.json()
    user_message = res['customData']['message']
    if '[' in user_message:
        user_message = user_message.split('[')
    address = res['customData']['address']
    message_history = res['customData']['message_history']
    email = res.get('email')
    phone = res.get('phone')
    
    user_query = f'{user_message} +  I am interested in {address}'
    ai_response = chatmodel.response(user_query,message_history)
    ## make post request on GHL's inbound webhook
    requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c',json={'bot_response' : ai_response, 'phone':phone,'email':email})
    return {'bot_response' : ai_response}


@app.post('/get_summary')
async def get_summary(request:Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get('email')
    phone = res.get('phone')
    message_history = res['customData']['message_history']
    summary = chatmodel.get_summary_of_conversation(message_history)
    summary = f"SUMMARY: {summary}"
    requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c',json={'bot_response' : summary, 'phone':phone,'email':email})
    
