import asyncio
import datetime
import re

import aiohttp
import requests
import os
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from asyncio import Task
from ai_model import (Model,
                      get_tax_informatiom,
                      google_places_wrapper,
                      get_info_about_nearby_homes,
                      search_properties_without_address,
                      get_house_property, find_distance, get_info_about_similar_homes, get_agent_listings)
from realtor_tools import (realtor_search_properties_without_address,
                           get_tax_and_price_information_from_realtor,
                           realtor_get_house_details)
from utils import add_distance_to_google_places,get_nearby_places


# Load .env file
load_dotenv()

# Read an environment variable

os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GPLACES_API_KEY"] = os.getenv('GPLACES_API_KEY')


app = FastAPI()

current_request_task = None

llm = ChatOpenAI(temperature=0.7, max_tokens=500, model="gpt-3.5-turbo-16k")
llm_gpt_4 = ChatOpenAI(temperature=0.3, max_tokens=500, model="gpt-4-1106-preview")


@app.post('/send_message_to_ai')
async def send_message_to_ai(request: Request):
    chatmodel = Model()
    global current_request_task
    if current_request_task and not current_request_task.done():
        current_request_task.cancel()
    try:
        res = await request.json()
        user_message = res['customData']['message']
        if '[' in user_message:
            user_message = user_message.split('[')
        address = res['customData'].get('address', '')
        message_history = res['customData'].get('message_history', '')
        email = res.get('email')
        phone = res.get('phone')


        user_query = f'{user_message} +  I am interested in {address}'
        contact_name = res["customData"]["contact_name"]
        current_request_task = asyncio.create_task(chatmodel.response(user_query, message_history, contact_name))
        ai_response = await current_request_task
        # ai_response = current_request_task.result()
        print("BOT_RESPONSE:", ai_response)
        # ai_response = chatmodel.response(user_query, message_history)
        ## make post request on GHL's inbound webhook
        async with aiohttp.ClientSession() as session:
            webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
           #  webhook_url = 'https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c'
            payload = {'bot_response': ai_response, 'phone': phone, 'email': email}
            async with session.post(webhook_url, json=payload) as response:
                pass
        return {'bot_response': ai_response}
    except asyncio.CancelledError:
        pass
    finally:
        current_request_task = None

@app.post('/get_summary')
async def get_summary(request:Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    message_history = res["customData"]["message_history"]
    summary = chatmodel.get_summary_of_conversation(message_history)

   # summary = f"{summary}"
    async with aiohttp.ClientSession() as session:
        webhook_url = 'https://services.leadconnectorhq.com/hooks/Cr4I5rLHxAhYI19SvpP6/webhook-trigger/f15fe780-1831-47de-8bfd-9241b8ac626c'
        payload = {'summary': summary, 'phone': phone, 'email': email}
        async with session.post(webhook_url, json=payload) as response:
            pass
    return {'summary': summary}


@app.post("/get_tax_or_price_info")
async def get_tax_or_price_info(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")

    user_message = res["customData"]["message"]
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)

    res = get_tax_informatiom(address)
    messages.append(SystemMessage(
            content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.

            Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and available tax information: "{res}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information." Emphasize utilizing tax details from the last two years unless specified otherwise by the user.
            Craft responses in 2-3 sentences that are short, concise, and directly related to the user's inquiry within their message.
            Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed.
"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}

        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result}


@app.post("/google_places")
async def google_places(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")

    user_message = res["customData"]["message"]
    user_query = f"{user_message}, nearby {address}, USA"
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    print("USER_QUERY: ", user_query)

    city_state = address.split(",")
    print("FIRST_SPLIT_ADDRESS: ", city_state)
    if len(city_state) > 2:
        city_state = city_state[-2:]
    else:
        city_state = city_state[-1]
    # result = google_places_wrapper(user_query)

    # message = [SystemMessage(
    #     content=f"You are helpful assistant. If {result} is the same with full address: {address} - write 'Same address', otherwise write - 'Not same address'")]
    # query = llm(message).content
    # if "Google Places did not find" in result or query == "Same address":
    message = [HumanMessage(content=f"""You are helpful assistant. Your aim is to extract specific places from user query. 
If there are any specific places in user query, write 'There are no specific places in user query'

Example 1: 
User: 'I want to know if there is the Angel Stadium nearby?' 
Assistant: Angel Stadium

Example 2 : 
User: 'Is the house close to any high schools?'
Assistant: high schools

Example 3: 
User: Hello 
Assistant: There are no specific places in user query

Example 4: 
User: Are there any shops? 
Assistant: shops


Proceed with this: 
User : {user_message}
Assistant : 
""")]
    query = llm(message).content
    print("PARAPHRASED_QUERY: ", f"{query} near {address}")
    #change to google nearby search
    # result = google_places_wrapper(f"{query} near {address}")
    try :
        result = get_nearby_places(query,address)
    except Exception as e:
        print(f"During get_nearby_places the following error occured :{str(e)}")
        result = f"Sorry, I was not able to find {query} near {address} within 30 miles."
        async with aiohttp.ClientSession() as session:
            webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
            payload = {"bot_response": result, "phone": phone, "email": email}

            async with session.post(webhook_url, json=payload) as response:
                pass
        return {"bot_response": result}
    result = add_distance_to_google_places(result,address)
    print(result)
    messages = chatmodel.history_add(message_history, contact_name)
    messages.append(SystemMessage(
            content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.
            Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information from google about places: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."
            Craft responses in 2-3 sentences that are short, concise, and directly related to the user's inquiry within their message.
            Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
        )
    )
    result = llm_gpt_4(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}

        async with session.post(webhook_url, json=payload) as response:
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

    print("USER_QUERY: ", f"{user_message}, {address}")
    contact_name = res["customData"]["contact_name"]
    agent_id = res["customData"].get("agent_id", "")
    print("CONTACT_NAME: ", contact_name)
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_info_about_similar_homes(address, agent_id)
    messages.append(SystemMessage(
        content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.
        Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about similar houses: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."
        Craft responses that are short, concise, with links, and directly related to the user's inquiry within their message.
        Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
    )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}

        async with session.post(webhook_url, json=payload) as response:
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

    agent_id = res["customData"].get("agent_id", "")
    messages = chatmodel.history_add(message_history, contact_name)
    result = get_info_about_nearby_homes(address, agent_id)
    messages.append(SystemMessage(
            content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.
            Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about homes nearby: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."
            Craft responses that are short, concise, with links, and directly related to the user's inquiry within their message.
            Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}

        async with session.post(webhook_url, json=payload) as response:
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
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    photo_link = ""
    if agent_id:
        listings = get_agent_listings(agent_id)
        messages.append(SystemMessage(

                content=f"""This is user message:{user_message}.
                You have information about real estate agent listings: {listings["res"]}
                Use this listings and provide 1 option which parameters match the best with User request..
                If there are no options in the listings that are suitable according to user message, write 'I will send more later'.
                If you have an option then ask 'do you want something like this?' ant the end"""
            )
        )
        result = llm(messages).content
        address_regex = "\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}"
        match = re.findall(address_regex, result)
        print("one_address: ", match[0])

        if match[0] in listings["photos"]:
            photo_link = listings["photos"][match[0]]

    else:
        print("ELSE_OPTION")
        result = await find_properties_without_address_tool(request)
        photo_link = result["photos"]

        result = result["bot_response"]
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email, "photo_link": photo_link}
        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result, "photo_link": photo_link}



@app.post("/find_properties_without_address_tool_OLD_VERSION")
async def find_properties_without_address_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    user_message = res["customData"]["message"]
    preferences = res["customData"].get("preferences", "")
    budget = res["customData"].get("budget", "")
    user_query = f"{user_message}. {address}, {preferences}, {budget}"
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    print("CONTACT_NAME: ", contact_name)
    messages = chatmodel.history_add(message_history, contact_name)
    address_regex_full = "\d+\s[A-Za-z0-9\s]+\,\s[A-Za-z\s]+\,\s[A-Z]{2}\s\d{5}"
    mes_str = [str(element) for element in messages]
    used_addresses = re.findall(address_regex_full, ", ".join(mes_str))
    result = search_properties_without_address(user_query)
    print("USER_QUERY: ", user_query)
    messages.append(SystemMessage(
            content=f"""You have User message:{user_message}, {preferences}, {budget}.
            This is information about homes:{result["res"]}.
            If there is information use it to show up to 3 options with base info (such as full address, price, number of bedrooms/bathrooms, property detailUrl without []() markdown format,  living area) which parameters match the best with User request.Don't use options: {used_addresses} that you already show in previous messages.
            If there is no results in information - just write 'There are no properties with such requirements currently available in our records. Would you like to adjust any of your preferences?',
             - Never use phrases like 'don't have access to current real estate listings' and don't provide any advices how to get listings or reaching real estates agents.

            Use this rules and information to provide a short and concise answer on the User message.
            Always ask if the lead needs anything else"""
        )
    )
    response = llm_gpt_4(messages).content
    address_regex_small = "\d+\s[A-Za-z0-9\s]+\,"
    match = re.findall(address_regex_full, response)
    if not match:
        print("NEW_MATCH")
        match = re.findall(address_regex_small, response)
    print("MATHCED_LIST: ", match)
    addresses_list = [address.split(", ")[0] for address in match]
    print("ADDRESSES_LIST: ", addresses_list)
    photos = result["photos"]
    keys_to_remove = []
    for key in photos.keys():
        address = key.split(", ")[0]
        if not any(address_part in address for address_part in addresses_list):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del photos[key]
    count = 1
    links = {}
    for key, value in photos.items():
        links[f"Photo link {count}"] = value
        count += 1
    print("PHOTOS: ", links)

   # async with aiohttp.ClientSession() as session:
    #    webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
     #   payload = {"bot_response": result, "phone": phone, "email": email}
      #  async with session.post(webhook_url, json=payload) as response:
       #     pass

    return {"bot_response": response, "photos": links}


@app.post("/get_house_details_tool")
async def get_house_details_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    user_message = res["customData"]["message"]
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    print("ADDRESS: ", address)
    print("CONTACT_NAME: ", contact_name)
    messages = chatmodel.history_add(message_history, contact_name)

    result = get_house_property(address)
   #  photo_link = result["imgSrc"]
    messages.append(SystemMessage(
            content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.
            Your main task is provide response to the user's message: "{user_message}", utilize property details: "{address}" and information about this property: "{result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."
            Craft responses in 2 - 3 sentences that are short, concise, and directly related to the user's inquiry within their message.
            Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""

        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result}


@app.post("/find_distance_tool")
async def find_distance_tool(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    address = res["customData"].get("address", "")
    address = address.strip()
    user_message = res["customData"]["message"]
    user_query = f"{user_message}, nearby {address}, USA"
    message_history = res["customData"].get("message_history", "")
    contact_name = res["customData"]["contact_name"]
    place_address = res["customData"].get("place_address", "")
    print("ADDRESS: ", address)
    print("PLACE_ADDRESS: ", place_address)
    city_state = address.split(",")
    print("FIRST_SPLIT_ADDRESS: ", city_state)
    if len(city_state) > 2:
        city_state = city_state[-2:]
    else:
        city_state = city_state[-1]
    print("CITY_STATE: ", city_state)
    print("USER_QUERY: ", user_query)
    result_places = google_places_wrapper(user_query)
    message = [SystemMessage(
        content=f"You are helpful assistant. If {result_places} is the same with full address: {address} - write 'Same address', otherwise write - 'Not same address'")]
    query = llm(message).content
    print("CHECK if address is same: ", query)
    if "Google Places did not find" in result_places or query == "Same address":
        message = [HumanMessage(content=f"""
You are helpful assistant. Your aim is to extract specific places from user query. 
If there are any specific places in user query, write 'There are no specific places in user query'

Example 1: 
User: 'I want to know if there is the Angel Stadium nearby?' 
Assistant: Angel Stadium

Example 2 : 
User: 'Is the house close to any high schools?'
Assistant: high schools

Example 3: 
User: Hello 
Assistant: There are no specific places in user query

Proceed with this: 
User : {user_message}
Assistant : 
""")]
        query = llm(message).content
        print("PARAPHRASED_QUERY: ", f"{query}, {city_state}, USA")
        result_places = google_places_wrapper(f"{query}, {city_state}, USA")
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
        if distances_result == "Sorry, couldn't find the distance" or distances_result == "Ask about name of the location that user interested in":
            print("TRIGER")
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
            for element in list_addresses:
                final_addresses += f"|{element}"
            distances_result = find_distance(final_addresses)
        messages = chatmodel.history_add(message_history, contact_name)
    print("DISTANCES_RESULT: ", distances_result)
    messages.append(SystemMessage(
        content=f"""Your role is to provide assistance with a human touch, akin to a helpful companion supporting a real estate agent. Aim for a conversational and friendly tone.
        Your main task is provide response to the user's message: "{user_message}", utilize information from google about places: "{result_places}" and information about distances "{distances_result}". Start with a friendly note, by mentioning the data's source without using the phrase "Based on available information."
        Craft responses in 2 - 3 sentences that are short, concise, with links, and directly related to the user's inquiry within their message.
        Always keep the conversation inviting by asking if there's more they'd like to know or if further assistance is needed."""
    ))
    result = llm_gpt_4(messages).content
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result}




LOG_FILE = "logfile.txt"


@app.post('/test_webhook')
async def test_webhook(request: Request):
    try:
        res = await request.json()
        marker = res.get("name")
        location = res.get("workflow")
        message_history = res["customData"]["message"]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_message = f"{timestamp} - Marker:{marker} - Location: {location} - Message History: {message_history} - {res}\n"

        with open(LOG_FILE, "a") as file:
            file.write(log_message)

        print(log_message)

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
            Always ask if lead need anything else"""
        )
    )
    result = llm(messages).content
    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result}


@app.post("/realtor_get_property_without_address")
async def realtor_get_property_without_address(request: Request):
    chatmodel = Model()
    res = await request.json()
    email = res.get("email")
    phone = res.get("phone")
    user_message = res["customData"]["message"]
    address = res["customData"].get("address", "")
    message_history = res["customData"].get("message_history", "")
    user_query = f"{user_message} + {address}"
    contact_name = res["customData"]["contact_name"]
    messages = chatmodel.history_add(message_history, contact_name)
    result = realtor_search_properties_without_address(user_query)
    messages.append(SystemMessage(
            content=f"""You have User message:{user_message}.
            This is information about homes:{result}.
            Use this information to provide a concise answer on the User message
            Always ask if lead need anything else"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload) as response:
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
            Always ask if lead need anything else"""
        )
    )
    result = llm(messages).content

    async with aiohttp.ClientSession() as session:
        webhook_url = "https://hooks.zapier.com/hooks/catch/15488019/3s3kzre/"
        payload = {"bot_response": result, "phone": phone, "email": email}
        async with session.post(webhook_url, json=payload) as response:
            pass

    return {"bot_response": result}

