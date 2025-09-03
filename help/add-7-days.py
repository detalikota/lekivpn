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

def extend_all_users():
    # Get token for authentication
    token = get_marzban_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all users
    users_response = requests.get(f"{MARZBAN_URL}/api/users", headers=headers)
    users_data = users_response.json()
    
    success_count = 0
    skipped_count = 0
    failed_count = 0
    
    for user in users_data["users"]:
        username = user["username"]
        current_expire = user.get("expire")
        
        # Skip if expire is None or 0
        if current_expire is None or current_expire == 0:
            print(f"Skipping user {username} - no active days left")
            skipped_count += 1
            continue
            
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
            success_count += 1
        else:
            print(f"Failed to extend duration for user {username}")
            print(f"Error: {update_response.text}")
            failed_count += 1
            
    print("\nSummary:")
    print(f"Successfully extended: {success_count} users")
    print(f"Skipped (no days left): {skipped_count} users")
    print(f"Failed to extend: {failed_count} users")

if __name__ == "__main__":
    extend_all_users()

