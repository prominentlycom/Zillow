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

6. The API endpoints will now be accessible for integration with the GHL+Zappychat platforms.

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

## Additional info
There are also other endpoints that were meant to be used as custom webhooks, however since custom webhooks were working poorly in GHL, the decision of using inbound webhook + webhook in GHL was made, therefor using other webhooks was not that convinient anymore and they were replaced by Zapier webhooks.