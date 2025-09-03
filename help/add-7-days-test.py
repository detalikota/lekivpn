import sys
sys.path.append('/opt/marzban')
from datetime import datetime, timedelta
import requests
from cred import USERNAME, PASSWORD


# Marzban settings
MARZBAN_URL = "https://oblakovpn.org:8000"

def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    return response.json()["access_token"]

def extend_single_user(username="277164510"):
    # Get token for authentication
    token = get_marzban_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get user data
    user_response = requests.get(f"{MARZBAN_URL}/api/user/{username}", headers=headers)
    user_data = user_response.json()
    
    current_expire = user_data.get("expire", 0)
    
    # Skip if user has no days left (expire = 0)
    if current_expire <= int(datetime.now().timestamp()):
        print(f"Skipping user {username} - no active days left")
        return
        
    # Calculate new expiry date (current + 7 days)
    new_expire = current_expire + (7 * 24 * 60 * 60)  # Add 7 days in seconds

    # Prepare update data
    update_data = {
        "expire": new_expire,
        "status": "active"
    }

    # Update user
    update_response = requests.put(
        f"{MARZBAN_URL}/api/user/{username}",
        headers=headers,
        json=update_data
    )
    
    if update_response.status_code == 200:
        print(f"Successfully extended duration for user {username}")
        print(f"Old expire timestamp: {current_expire}")
        print(f"New expire timestamp: {new_expire}")
    else:
        print(f"Failed to extend duration for user {username}")
        print(f"Error: {update_response.text}")

if __name__ == "__main__":
    extend_single_user()

