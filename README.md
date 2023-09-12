# Integration of Chatbot with GHL+Zappychat Platforms

This project aims to integrate another chatbot with GHL+Zappychat platforms. The objective is to enhance the functionality of the platforms by incorporating an additional chatbot. The project has been tested successfully on Python versions 3.9.6 and 3.10.12.

## Core Libraries and Services Used

The project utilizes the following core libraries and services:

1. **rapidAPI**: This service is used to retrieve data from Zillow, providing the chatbot with relevant information.

2. **langchain**: The Langchain library is employed as an LLM-agent, which aids in searching for answers to user messages using various tools.

3. **google-api**: This library leverages Google Maps and Google Distance Matrix to provide location-based services within the chatbot.

4. **FastAPI**: FastAPI is the framework utilized to develop the API, allowing seamless communication between the integrated chatbot and the GHL+Zappychat platforms.

## Setup and Configuration

To set up and use the project, follow these steps:

1. Clone the repository from GitLab.

2. Ensure you have Python versions 3.9.6 or 3.10.12 installed on your system. (Other versions might work as well)

3. Install the necessary dependencies using the following command:
   ```shell
   pip install -r requirements.txt
   ```

4. Obtain API keys for the required services (rapidAPI, Google Maps, OpenAI) and configure them in the .env file.

5. Start the FastAPI server using the following command:
   ```shell
   uvicorn api:app --host 0.0.0.0 --reload
   ```

6. The API endpoints will now be accessible for integration with the GHL+Zappychat platforms. You might need to change the IP address in GHL for webhooks on this API.

## API Endpoints

The following API endpoints are available for interacting with the integrated chatbot:

1. `/send_message_to_ai` (POST): This endpoint receives user messages and returns the chatbot's response. It expects the following payload format:
   ```json
   {
     "email": "user's email", (optional, but is required for sending email via GHL)
     "phone": "user's phone number", (optional, but is required for sending sms via GHL)
     "customData":{
        "message":"User_message",
        "address":"address of the house regarding which the question is asked",
        "message_history":"message history in following format You: user_message AI:ai_message You: user_message AI: ai_message",
        "platform":"Zillow", #platform from which user came, if passed Zillow, zillow listings are used, else realtor.com
     }
     ...
   }
   ```

2. `/get_summary` (POST): This endpoint receives message history and returns the questions that were not answered by AI, so that agent could gather more information about user needs:
   ```json
   {
     "email": "user's email", (optional, but is required for sending email via GHL)
     "phone": "user's phone number", (optional, but is required for sending sms via GHL)
     "customData":{
        "message_history":"message history in following format You: user_message AI:ai_message You: user_message AI: ai_message"
     }
     ...
   }
   ```
## Usage Examples

To interact with the integrated chatbot, you can use the following examples:

1. **Send a Message**:
   ```shell
    curl -X POST -H "Content-Type: application/json" -d '{
        "customData": {
            "message": "What is the closest pub?",
        "address": "13545 Cielo Azul Way, Desert Hot Springs, CA 92240",
            "message_history": ""
        }
    }' http://ip_address:8000/send_message_to_ai

   ```

2. **Get summary**:
   ```shell
    curl -X POST -H "Content-Type: application/json" -d '{
        "customData": {
            "message_history": "You:user_message AI:ai_response  You : ...."
        }
    }' http://ip_address:8000/get_summary

   ```

Note. To send the response within GHL phone number or email address is required. Check more in workflows that are used to send messages.

## Additional info
There are also other endpoints that were meant to be used as custom webhooks, however since custom webhooks were working poorly in GHL, the decision of using inbound webhook + webhook in GHL was made, therefore using other webhooks was not that convinient anymore and they were replaced by Zapier webhooks.

## GHL workflows
There is a folder in GHL>Automation that was used only for this project and it is named "Test Workflow with inbound webhooks", and there are several workflows that are used to combine everything, here is brief description of each one:

- 0.0 Get user message :
   
   Workflow that receives user message and passes it through different zapier webhooks (webhook to extract address; webhook to determine whether extra info is needed, if so langchain is used otherwise ZC; check if message is related to booking, then switch to booking workflow).Depending on these webhooks, workflow branches on using LangChain to answer specific question, ZC to answer general question and zc to answer booking-related questions.
   
    Also in this workflow there is a temporary check if user asked for summary, it requires exact phrase in the message "get summary" and outputs questions that were not answered by the AI.

- 1.0 Langchain/zc answer non-booking workflow
   
   Workflow that answers using LangChain or ZC depending on whether extra info is needed. If LangChain is used the request to the send_message_to_ai endpoint is made, otherwise non-booking zc used. 

- 1.1 ZC booking workflow

   ZC booking workflow, the only difference with zc non-booking is the prompt, so probably it might be merged with non-booking zc later on.

- 3.2 Robot reply - copy.

   Workflow that sends ZC answer to user.

- 4.0 Send LangChain answer

   Workflow that sends LangChain answer to user and is triggered within this API in the send_message_to_ai endpoint.

## Zapier 

Zaps on Zapier are used in webhooks in 0.0 Get user message workflow, their main goal is to navigate the flow. This webhooks are requests to ChatGPT within Zapier, for more informaion check zaps on Zapier.