import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD
import requests
import datetime
import time
import re

MARZBAN_URL = "https://oblakovpn.org:8000"

def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    print("Token response:", response.json())
    return response.json()["access_token"]

def get_users(token):
    url = f"{MARZBAN_URL}/api/users"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["users"]
    else:
        print(f"Error getting users: {response.status_code}")
        print(response.text)
        return []

def update_user_expiration(token, username, expiration_timestamp):
    url = f"{MARZBAN_URL}/api/user/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "expire": expiration_timestamp
    }
    
    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Successfully updated expiration for user {username}")
        return True
    else:
        print(f"Error updating user {username}: {response.status_code}")
        print(response.text)
        return False

def is_numeric_username(username):
    return re.match(r'^\d+$', username) is not None

def main():
    token = get_marzban_token()
    users = get_users(token)
    
    # Calculate timestamp for 1 month from now
    current_time = int(time.time())
    one_month_seconds = 30 * 24 * 60 * 60  # 30 days in seconds
    expiration_timestamp = current_time + one_month_seconds
    
    # Format for display
    expiration_date = datetime.datetime.fromtimestamp(expiration_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    print(f"Setting expiration date to: {expiration_date} (timestamp: {expiration_timestamp})")
    
    # Find users with numeric usernames, without expiration, and not disabled
    users_to_update = []
    for user in users:
        username = user.get("username", "")
        
        # Check if username is numeric, expire is 0 or None, and status is not disabled
        if is_numeric_username(username) and (user.get("expire") == 0 or user.get("expire") is None) and user.get("status") != "disabled":
            users_to_update.append(user)
    
    print(f"Found {len(users_to_update)} active users with numeric usernames and without expiration to update:")
    
    # Update each user
    successful_updates = 0
    for i, user in enumerate(users_to_update, 1):
        username = user["username"]
        print(f"\n{i}. Updating user: {username}, Current status: {user.get('status')}, Current expiration: {user.get('expire')}")
        
        # Update the user's expiration
        if update_user_expiration(token, username, expiration_timestamp):
            successful_updates += 1
    
    print(f"\nSummary: Updated {successful_updates} out of {len(users_to_update)} users")

if __name__ == "__main__":
    main()