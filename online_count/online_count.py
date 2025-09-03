import sys
sys.path.append('/opt/marzban')
import requests
from prometheus_client import start_http_server, Gauge
import time
from datetime import datetime, timedelta
from cred import USERNAME, PASSWORD

MARZBAN_URL = "https://oblakovpn.org:8000"

# Prometheus metrics
online_users_gauge = Gauge('marzban_online_users', 'Number of currently online users in Marzban')
daily_unique_users = Gauge('marzban_daily_unique_users', 'Number of unique users connected in last 24 hours')

def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    return response.json()["access_token"]

def fetch_marzban_users(token):
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = requests.get(f"{MARZBAN_URL}/api/users", headers=headers)
        data = response.json()
        users = data.get('users', [])
        return users
    except Exception as e:
        print(f"Error fetching Marzban users: {e}")
        return []

def is_user_online(online_at):
    if online_at is None:
        return False
    online_time = datetime.fromisoformat(online_at.replace('Z', '+00:00')) + timedelta(hours=3)
    current_time = datetime.utcnow()
    return (current_time - online_time) <= timedelta(minutes=1)

def get_last_24h_unique_users(users):
    current_time = datetime.utcnow()
    unique_users = set()
    
    for user in users:
        online_at = user.get('online_at')
        if online_at:
            user_last_seen = datetime.fromisoformat(online_at.replace('Z', '+00:00')) + timedelta(hours=3)
            if current_time - user_last_seen <= timedelta(hours=24):
                unique_users.add(user['username'])
                
    return len(unique_users)

def update_metrics():
    token = get_marzban_token()
    users = fetch_marzban_users(token)
    
    # Update current online users metric
    online_users = 0
    for user in users:
        if is_user_online(user.get('online_at')):
            online_users += 1
    online_users_gauge.set(online_users)
    
    # Update rolling 24h unique users metric
    users_24h = get_last_24h_unique_users(users)
    daily_unique_users.set(users_24h)

if __name__ == '__main__':
    # Start Prometheus HTTP server
    start_http_server(8008)
    while True:
        update_metrics()
        time.sleep(60)  # Update every minute

