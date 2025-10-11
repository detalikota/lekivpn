import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN, CHANNEL_ID, SHOP_ID, YUKASSA_API
import requests
from collections import defaultdict
import time

MARZBAN_URL = "https://oblakovpn.org:8000"
CHANNEL_LINK = "https://t.me/VPN_OBLAKO"

def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    print("Token response:", response.json())
    return response.json()["access_token"]

notified_users = defaultdict(bool)  # Track who has been notified

def check_subscriptions():
    try:
        current_time = int(time.time())
        print(f"Current time: {current_time}")
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/users"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        users = response.json()["users"]
        print(f"Total users found: {len(users)}")
        
        for user in users:
            # print(f"\nChecking user: {user['username']}")
            # print(f"Status: {user['status']}")
            # print(f"Expire: {user.get('expire')}")
            
            if user["status"] == "active" and "expire" in user and user["expire"] is not None:
                time_to_expire = user["expire"] - current_time
                user_id = user["username"]
                # print(f"Time to expire for {user_id}: {time_to_expire} seconds") df
                
                # 2 days before (172800 seconds = 48 hours)
                if 85400 < time_to_expire <= 172800 and not notified_users[f"warning_48h_{user_id}"]:
                    print(f"Истекает через 2 дня для {user_id}")
                    notified_users[f"warning_48h_{user_id}"] = True
                
                # 1 day before (86400 seconds = 24 hours)
                elif 100 < time_to_expire <= 86400 and not notified_users[f"warning_24h_{user_id}"]:
                    print(f"Истекает завтра для {user_id}")
                    notified_users[f"warning_24h_{user_id}"] = True
                
                # On expiration
                elif time_to_expire <= 0 and not notified_users[f"expired_{user_id}"]:
                    print(f"Истекло для {user_id}")
                    notified_users[f"expired_{user_id}"] = True
                
                # Reset notification flags if subscription is renewed
                elif time_to_expire > 172800:  # More than 2 days
                    notified_users[f"warning_48h_{user_id}"] = False
                    notified_users[f"warning_24h_{user_id}"] = False
                    notified_users[f"expired_{user_id}"] = False
            # else:
            #     print("User skipped - not active or no expiration")
                    
    except Exception as e:
        print(f"Subscription check error: {e}")
        print(f"Full error details:", sys.exc_info())

print("Starting subscription checker...")
while True:
    print("\nRunning check cycle...")
    check_subscriptions()
    print("Sleeping for 1 hour...")
    time.sleep(3600)  # Check every hour