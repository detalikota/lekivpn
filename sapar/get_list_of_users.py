import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD
import requests
from datetime import datetime

def get_marzban_token():
    """Get authentication token from Marzban server."""
    MARZBAN_URL = "https://oblakovpn.org:8000"
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def get_users_in_timeframe():
    """Extract users created between specified dates."""
    MARZBAN_URL = "https://oblakovpn.org:8000"
    
    start_time = datetime(2025, 6, 15, 12, 30, 0)
    end_time = datetime(2025, 6, 16, 18, 0, 0)
    
    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    users_data = response.json()
    filtered_users = []
    
    for user in users_data["users"]:
        created_at_str = user.get("created_at")
        if created_at_str:
            try:
                if 'T' in created_at_str:
                    date_part, time_part = created_at_str.split('T')
                    time_part = time_part.rstrip('Z')
                    if '.' in time_part:
                        time_part = time_part.split('.')[0]
                    created_at_str_clean = f"{date_part} {time_part}"
                else:
                    created_at_str_clean = created_at_str
                
                created_at = datetime.strptime(created_at_str_clean, '%Y-%m-%d %H:%M:%S')
                
                if start_time <= created_at <= end_time:
                    filtered_users.append(user)
            except ValueError as e:
                print(f"Error parsing date {created_at_str}: {e}")
                continue
    
    return filtered_users

if __name__ == "__main__":
    try:
        users = get_users_in_timeframe()
        print(f"Found {len(users)} users created between the specified timeframe")
        
        with open("/root/usernames.txt", "w") as f:
            for user in users:
                username = user['username']
                created_at = user['created_at']
                print(f"Username: {username}, Created: {created_at}")
                f.write(f"{username}\n")
        
        print(f"Usernames saved to /root/usernames.txt")
        
    except Exception as e:
        print(f"Error: {e}")