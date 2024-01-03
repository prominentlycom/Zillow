import asyncio
import datetime

import aiohttp
import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

from ai_model import (Model,
                      get_tax_informatiom,
                      google_places_wrapper,
                      get_info_about_nearby_homes,
                      search_properties_without_address,
                      get_house_property,
                      find_distance,
                      get_info_about_similar_homes, get_agent_listings)
from realtor_tools import (realtor_search_properties_without_address,
                           get_tax_and_price_information_from_realtor,
                           realtor_get_house_details)

# Load .env file
load_dotenv()

# Read an environment variable
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["GPLACES_API_KEY"] = os.getenv("GPLACES_API_KEY")

app = FastAPI()

current_request_task = None

llm = ChatOpenAI(temperature=0.3, max_tokens=650, model="gpt-3.5-turbo-16k")
llm_gpt_4 = ChatOpenAI(temperature=0.3, max_tokens=650, model="gpt-4-1106-preview")


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
        address = res["customData"].get("address", "")
        message_history = res["customData"].get("message_history", "")
        email = res.get("email")
        phone = res.get("phone")
        contact_name = res["customData"]["contact_name"]

        user_query = f"{user_message} +  I am interested in {address}"

        current_request_task = asyncio.create_task(
            chatmodel.response(user_query, message_history, contact_name)
        )

        ai_response = await current_request_task

        print("BOT_RESPONSE:", ai_response)

        # async with aiohttp.ClientSession() as session:
        #     webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        #     payload = {"bot_response": ai_response, "phone": phone, "email": email}
        #     async with session.post(webhook_url, json=payload, ssl=False) as response:
        #         pass

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
    # async with aiohttp.ClientSession() as session:
    #     webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
    #     payload = {"summary": summary, "phone": phone, "email": email}
    #     async with session.post(webhook_url, json=payload, ssl=False) as response:
    #         pass

    return {"summary": summary}


@app.post("/get_tax_or_price_info")
async def get_tax_or_price_info(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    user_message = res["customData"]["message"]
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    res = get_tax_informatiom(address)
    messages.append(SystemMessage(
            content=f"""
            Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and available tax information: "{res}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information." Emphasize utilizing tax details from the last two years unless specified otherwise by the user.

Craft responses that are short, concise, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed.
"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/google_places")
async def google_places(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    user_message = res["customData"]["message"]
    user_query = f"{user_message}, nearby {address}"
    contact_name = res["customData"]["contact_name"]
    city_state = address.split(",")
    print("FIRST_SPLIT_ADDRESS: ", city_state)
    if len(city_state) > 2:
        city_state = city_state[-2:]
    else:
        city_state = city_state[-1]
    result = google_places_wrapper(user_query)
    print("USER_QUERY: ", user_query)
    print("RESULT: ", result)
    message = [SystemMessage(
        content=f"You are helpful assistant. If {result} is the same with full address: {address} - write 'Same address', otherwise write - 'Not same address'")]
    query = llm(message).content
    print("CHECK if address is same: ", query)
    if "Google Places did not find" in result or query == "Same address":
        message = [SystemMessage(content=f"You are helpful assistant. Please extract specific places from this search query:{user_message}. Examples: 1. User: 'I want to know if there is the Angel Stadium nearby?' Assistant: 'Angel Stadium' 2. User: 'Is the house close to any high schools?' Assistant: 'high schools'")]
        query = llm(message).content
        print("PARAPHRASED_QUERY: ", f"{query}, {city_state}")
        result = google_places_wrapper(f"{query}, {city_state}")
    messages = chatmodel.history_add(message_history, contact_name)
    messages.append(SystemMessage(
            content=f"""
            Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information from google about places: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."

Craft responses that are short, concise, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
        )
    )
    result = llm_gpt_4(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/find_similar_homes")
async def find_similar_homes(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    user_message = res["customData"]["message"]
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    agent_id = res["customData"]["agent_id"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_info_about_similar_homes(address, agent_id)
    messages.append(SystemMessage(
        content=f"""
                Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about similar houses: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."

Craft responses that are concise, with links, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
    )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/find_nearby_homes")
async def find_nearby_homes(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    user_message = res["customData"]["message"]
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    agent_id = res["customData"]["agent_id"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_info_about_nearby_homes(address, agent_id)
    messages.append(SystemMessage(
            content=f"""
            Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about homes nearby: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."

Craft responses that are concise, with links, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/find_properties_without_address_tool")
async def find_agent_listings(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    user_message = res["customData"]["message"]
    agent_id = res["customData"].get("agent_id", "")
    preferences = res["customData"].get("preferences", "")
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    if agent_id:
        listings = get_agent_listings(agent_id)
        messages.append(SystemMessage(
                content=f"""This is user message:{user_message} and preferences: {preferences}.
                You have information about real estate agent listings: {listings}
                Use this listings and provide the best suitable property from it according to user message with short info, photo, and link.
                If there are no options in the listings that are suitable according to user message, write 'I will send more later'.
                If you have an option then ask 'do you want something like this?' ant the end"""
            )
        )
        result = llm(messages).content
    else:
        print("ELSE_OPTION")
        result = await find_properties_without_address_tool(request)
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/find_properties_without_address_tool_OLD_VERSION")
async def find_properties_without_address_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    preferences = res["customData"].get("preferences", "")
    message_history = res["customData"].get("message_history", "")
    user_message = res["customData"]["message"]
    user_query = f"{user_message} +  I am interested in {address}, {preferences}"
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = search_properties_without_address(user_query)
    print("USER_QUERY: ", user_query)

    messages.append(SystemMessage(
            content=f"""You have User message:{user_message}, {preferences}.
            This is information  about homes:{result}.
            Use only 3 options with base info (such as address, price, number of bedrooms/bathrooms, living area and) which parameters match the best with User request.
            Always provide the url and property photo to each property that you use.
            Use this information to provide a concise answer on the User message.
            Always ask if the lead needs anything else"""
        )
    )
    result = llm_gpt_4(messages).content

    # async with aiohttp.ClientSession() as session:
    #     webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
    #     payload = {"bot_response": result, "phone": phone, "email": email}
    #     async with session.post(webhook_url, json=payload, ssl=False) as response:
    #         pass

    return result


@app.post("/get_house_details_tool")
async def get_house_details_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    user_message = res["customData"]["message"]
    message_history = res["customData"].get("message_history", "")
    address = res["customData"].get("address", "")
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_house_property(address)

    messages.append(SystemMessage(
            content=f"""
            Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about this property: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."

Craft responses that are short, concise, with links, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""

        )
    )
    result = llm(messages).content
    print("MESSAGES: ", messages)
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/find_distance_tool")
async def find_distance_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    print("FIRST_PRINT_ADDRESS: ", address)
    address = address.strip()
    print("SECOND_PRINT_ADDRESS: ", address)
    user_message = res["customData"]["message"]
    contact_name = res["customData"]["contact_name"]
    place_address = res["customData"].get("place_address", "")
    user_query = f"{user_message}, nearby {address}"
    message_history = res["customData"].get("message_history", "")

    city_state = address.split(",")
    print("FIRST_SPLIT_ADDRESS: ", city_state)
    if len(city_state) > 2:
        city_state = city_state[-2:]
    else:
        city_state = ""
    print("CITY_STATE: ", city_state)
    print("USER_QUERY: ", user_query)
    result_places = google_places_wrapper(user_query)
    message = [SystemMessage(
        content=f"You are helpful assistant. If {result_places} is the same with full address: {address} - write 'Same address', otherwise write - 'Not same address'")]
    query = llm(message).content
    print("CHECK if address is same: ", query)
    if "Google Places did not find" in result_places or query == "Same address":
        message = [SystemMessage(content=f"You are helpful assistant. Please extract specific places from this search query:{user_message}. Examples: 1. User: 'I want to know if there is the Angel Stadium nearby?' Assistant: 'Angel Stadium' 2. User: 'Is the house close to any high schools?' Assistant: 'high schools'")]
        query = llm(message).content
        print("PARAPHRASED_QUERY: ", f"{query}, {city_state}")
        result_places = google_places_wrapper(f"{query}, {city_state}")
    messages = chatmodel.history_add(message_history, contact_name)
    messages.append(SystemMessage(
            content=f"""You have information from google about places: {result_places}.
            Please extract and provide only addresses of each place line by line. Example: 1.Place: place name, Address: address of this place"""
        )
    )
    addresses_str = llm(messages).content

    addresses = addresses_str.split("\n")
    print("ADDRESSES: ", addresses)
    list_addresses = []
    for element in addresses:
        if "Address:" in element:
            list_addresses.append(element)
    final_addresses = f"{address}"

    for element in list_addresses:
        final_addresses += f"|{element}"
    distances_result = find_distance(final_addresses)
    if not distances_result:
        print("Place address: ", place_address)
        list_addresses = []
        list_addresses.append(place_address)
        final_addresses = f"{address}"

        for element in list_addresses:
            final_addresses += f"|{element}"
        distances_result = find_distance(final_addresses)
        if distances_result == "Sorry, couldn't find the distance":
            print("TRIIIIGER")
            result_places = google_places_wrapper(place_address)
            messages = [SystemMessage(
                content=f"""You have information from google about places: {result_places}.
                        Please extract and provide only addresses of each place line by line. Example: 1.Place: place name, Address: address of this place"""
            )]
            addresses_str = llm(messages).content
            print("ADRESSES_STR: ", addresses_str)

            addresses = addresses_str.split("\n")
            print("ADDRESSES: ", addresses)
            list_addresses = []
            for element in addresses:
                if "Address:" in element:
                    list_addresses.append(element)
            final_addresses = f"{address}"
            print("last_check_address_field: ", address)
            for element in list_addresses:
                final_addresses += f"|{element}"
            distances_result = find_distance(final_addresses)
        messages = chatmodel.history_add(message_history, contact_name)
    print("DISTANCES_RESULT: ", distances_result)
    messages.append(SystemMessage(
        content=f"""
        Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

Your main task is provide response to the user's message: "{user_message}", utilize information from google about places: "{result_places}" and information about distances "{distances_result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."

Craft responses that are short, concise, with links, and directly related to the user's inquiry within their message.

Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
    ))
    result = llm_gpt_4(messages).content
    print("MESSAGES: ", messages)
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass
    return {"bot_response": result}


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


@app.post("/realtor_get_tax_or_price_info")
async def realtor_get_tax_or_price_info(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    user_message = res["customData"]["message"]
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_tax_and_price_information_from_realtor(address)
    messages.append(SystemMessage(
            content=f"""You have User message:{user_message}.
            This property located at: {address}.
            You have information about taxes: {result}.
            Use this information to provide a concise answer on the User message.
            Always ask if the lead needs anything else"""
        )
    )
    result = llm(messages).content
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/realtor_get_property_without_address")
async def realtor_get_property_without_address(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    user_message = res["customData"]["message"]
    user_query = f"{user_message} + {address}"
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = realtor_search_properties_without_address(user_query)
    messages.append(SystemMessage(
            content=f"""You have User message:{user_message}.
            This is information about homes:{result}.
            Use this information to provide a concise answer on the User message
            Always ask if the lead needs anything else"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


@app.post("/realtor_get_property_details")
async def realtor_get_property_details(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    user_message = res["customData"]["message"]
    user_query = f"{user_message} + {address}"
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = realtor_get_house_details(user_query)
    messages.append(SystemMessage(
            content=f"""This is User message:{user_message}.
            Property located at {address}.
            You have information about this property:{result}.
            Use this information to provide a concise answer on the User message.
            Always ask if the lead needs anything else"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload, ssl=False) as response:
            pass

    return {"bot_response": result}


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
#     requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c',json={'prompt':prompt,'message_history' : message_history, 'phone':phone,'email':email})
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
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c', json = {'message':user_message,'need_extra_info':'True', 'email':email,'phone':phone})

#         return {'need_extra_info':'True'}
#     else:
#         print('No need to ask extra info')
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c', json = {'message':user_message,'need_extra_info':'False', 'email':email,'phone':phone})

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
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c', json = {'message':user_message,'address':match.group(), 'email':email,'phone':phone})

#         return {'address':match.group(), 'status':200}
#     else:
#         print('Address not found  ',user_message)
#         requests.post('https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c', json = {'message':user_message,'address':'not found', 'email':email,'phone':phone})
#         return {'address':'not found','status':200}
