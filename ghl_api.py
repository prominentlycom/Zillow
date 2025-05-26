import os
import re
import aiohttp
from typing import Optional, List

async def get_ghl_location_id(email: Optional[str] = None, phone: Optional[str] = None, api_keys: Optional[List[str]] = None) -> Optional[str]:
    """
    Get the location ID from GHL using either email or phone number, trying multiple API keys if provided.
    
    Args:
        email (Optional[str]): The email address of the contact
        phone (Optional[str]): The phone number of the contact
        api_keys (Optional[List[str]]): List of API keys to try
        
    Returns:
        Optional[str]: The location ID if found, None otherwise
    """
    if not email and not phone:
        return None

    # Gather API keys from argument or environment
    if api_keys is None:
        api_keys = [
            os.getenv('GHL_API_KEY'),
            os.getenv('GHL_API_Key')
        ]
    api_keys = [k for k in api_keys if k]  # Remove None values

    # Try each API key in order
    for i, api_key in enumerate(api_keys, 1):
        print(f"\nTrying API Key #{i}")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try email first if available
        print("EMAIL: ", email)
        if email:
            url = f"https://rest.gohighlevel.com/v1/contacts/lookup?email={email}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    print("EMAIL RESPONSE: ", response.status)
                    if response.status == 200:
                        data = await response.json()
                        print("EMAIL DATA: ", data)
                        if data and 'contacts' in data and len(data['contacts']) > 0:
                            print(f"Successfully found Location ID using API Key #{i}")
                            return data['contacts'][0]['locationId']
        
        # If email lookup failed or wasn't available, try phone
        if phone:
            # Format phone number to E.164 format (e.g., +12345678900)
            # Remove all non-numeric characters
            phone_clean = re.sub(r'\D', '', phone)
            # Add +1 if it's a 10-digit number (US/Canada)
            if len(phone_clean) == 10:
                phone_clean = f"+1{phone_clean}"
            # Add + if it's an 11-digit number starting with 1
            elif len(phone_clean) == 11 and phone_clean.startswith('1'):
                phone_clean = f"+{phone_clean}"
            
            print("FORMATTED PHONE: ", phone_clean)
            url = f"https://rest.gohighlevel.com/v1/contacts/lookup?phone={phone_clean}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    print("PHONE RESPONSE: ", response.status)
                    if response.status == 200:
                        data = await response.json()
                        print("PHONE DATA: ", data)
                        if data and 'contacts' in data and len(data['contacts']) > 0:
                            print(f"Successfully found Location ID using API Key #{i}")
                            return data['contacts'][0]['locationId']
                    else:
                        response_text = await response.text()
                        print("ERROR RESPONSE: ", response_text)
    
    print("No Location ID found with any API key")
    return None
