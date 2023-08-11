import streamlit as st
# from ai_model import Model
from ai_model import Model
import requests

@st.cache_resource()  # Set allow_output_mutation to True for classes
def get_my_class_instance():
    return Model()

chatmodel = get_my_class_instance()

def get_bot_response(user_input):
    # Add your chatbot logic here and return the bot's response
    # For a simple example, you can use rule-based or pre-trained models.

    # Replace the following line with your actual chatbot logic
    # response = chatmodel.response(user_input)
    response = requests.post('http://127.0.0.1:8000/send_message_to_ai',json={'message':user_input}).json()
    return response

def main():
    st.title("Chatbot Template")

    user_input = st.text_input("You:", "")

    if st.button("Send"):
        bot_response = get_bot_response(user_input)
        st.text_area("Bot:", bot_response)

if __name__ == "__main__":
    main()
