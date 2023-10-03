import asyncio
import datetime

import aiohttp
import requests
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from ai_model import Model


# Load .env file
load_dotenv()

# Read an environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["GPLACES_API_KEY"] = os.getenv("GPLACES_API_KEY")

app = FastAPI()

current_request_task = None


@app.post("/send_message_to_ai")
async def send_message_to_ai(request: Request):
    chatmodel = Model()

    global current_request_task
    if current_request_task and not current_request_task.done():
        current_request_task.cancel()

    try:
        res = await request.json()
        print("RESULT_JSON: ", res)
        user_message = res["customData"]["message"]
        if "[" in user_message:
            user_message = user_message.split("[")
        address = res["customData"]["address"]
        message_history = res["customData"]["message_history"]
        email = res.get("email")
        phone = res.get("phone")

        user_query = f"{user_message} +  I am interested in {address}"

        current_request_task = asyncio.create_task(
            chatmodel.response(user_query, message_history)
        )

        ai_response = await current_request_task

        print("BOT_RESPONSE:", ai_response)

        async with aiohttp.ClientSession() as session:
            webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3iegjjp/"
            payload = {"bot_response": ai_response, "phone": phone, "email": email}
            async with session.post(webhook_url, json=payload, ssl=False) as response:
                pass

        return {"bot_response": ai_response}

    except asyncio.CancelledError:
        pass

    finally:
        current_request_task = None


@app.post("/get_summary")
async def get_summary(request: Request):
    chatmodel = Model()
    res = await request.json()

    email = res.get("email")
    phone = res.get("phone")
    message_history = res["customData"]["message_history"]
    summary = chatmodel.get_summary_of_conversation(message_history)
    # summary = f"{summary}"
    print(summary)
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c"
        payload = {"summary": summary, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"summary": summary}


LOG_FILE = "logfile.txt"


@app.post("/test_webhook")
async def test_webhook(request: Request):
    try:
        res = await request.json()
        location = res["location"]
        print("WEBHOOK_RES", res)
        message = res["customData"]["message"]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_message = (
            f"{timestamp} - Location: {location} - Message History: {message}\n"
        )

        with open(LOG_FILE, "a") as file:
            file.write(log_message)

        print(timestamp, location, message)

        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# @app.post("/summary_counter")
# async def summary_counter(request: Request):
#     res = await request.json()
#     counter = res.get("summary_check")
#     counter += 1
#     res["summary_check"] = counter


# async with aiohttp.ClientSession() as session:
#     webhook_url = 'https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c'
#     payload = {'bot_response': ai_response, 'phone': phone, 'email': email}
#     async with session.post(webhook_url, json=payload, ssl=False) as response:
#         pass

## Send to GHL's GPT
# def clip_history(message_history,prompt):
#     max_lenght = 8_000
#     current_length = len(prompt+message_history)
#     if current_length > max_lenght:
#         prompt = prompt
#         need_to_remove = current_length - max_lenght
#         message_history = message_history[need_to_remove:]
#     return message_history

# @app.post('/clip_message_history')
# async def clip_message_history(request:Request):
#     res = await request.json()

#     message_history = res['customData']['message_history']
#     prompt = res['customData']['openai_prompt']
#     print("PROMPT IS",prompt)
#     email = res.get('email')
#     phone = res.get('phone')
#     message_history = clip_history(message_history,prompt)
#     print('Clipped message : ',message_history)
#     requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/94a02662-1c53-4f5b-8573-a9f412c8d568',json={'prompt':prompt,'message_history' : message_history, 'phone':phone,'email':email})
# return {'message_history' : message_history}

## was used with custom webhook
# basic_prompt = '''If the question is related to specific property information or utilities near that property, please answer yes, otherwise say no. Do not add anything else.

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
# AI: No

# User: What is the price of [some address]?
# AI: Yes

# User: I'm interested in 13151 Cuando Way, Desert Hot Springs, CA 92240
# AI: No

# User: I'm interested in [address]
# AI: No

# User: How far away is it?
# AI: Yes

# Use examples to proceed with this:
# User: '''

# @app.post('/shouldAskForExtraInfo')
# async def shouldAskForExtraInfo(request:Request):
#     res = await request.json()
#     print('#########')
#     print(res)
#     print('#########')
#     user_message = res['customData']['message']

#     prompt = basic_prompt + user_message + "\n AI:"
#     address = res['customData']['address']
#     email = res.get('email')
#     phone = res.get('phone')
#     print(address)
#     result = openai.ChatCompletion.create(
#             model="gpt-3.5-turbo",
#             max_tokens=256,
#             temperature = 0,
#             messages=[
#                 {"role": "user", "content": prompt}]
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

## was used with custom webhook
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
