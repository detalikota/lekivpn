import sys
import requests
import time
import datetime
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN, CHANNEL_ID, SHOP_ID, YUKASSA_API
# Configuration
MARZBAN_URL = "https://oblakovpn.org:8000"  # Replace with your Marzban URL
MESSAGE = ("🔥 ВРЕМЕННАЯ АКЦИЯ! 🔥\n\n"
            "🚀 Вечная подписка всего за 700 рублей! 🚀\n"
            "⏳ Успей до конца акции! Ведь такого больше НЕ БУДЕТ!"
            )

def log_message(message):
    """Print a timestamped log message"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_marzban_token():
    """Get authentication token from Marzban API"""
    log_message("Attempting to authenticate with Marzban API...")
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        log_message(f"Failed to get token: {response.text}")
        return None
    log_message("Successfully obtained authentication token")
    return response.json().get("access_token")

def get_users(token):
    """Get all users from Marzban API"""
    log_message("Retrieving users from Marzban API...")
    url = f"{MARZBAN_URL}/api/users"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        log_message(f"Failed to get users: {response.text}")
        return []
    users_count = len(response.json().get("users", []))
    log_message(f"Successfully retrieved {users_count} users")
    return response.json().get("users", [])

def send_telegram_message(chat_id, message):
    """Send message to a Telegram user"""
    log_message(f"Sending message to Telegram ID: {chat_id}...")
    url = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data)
    success = response.status_code == 200
    if success:
        log_message(f"✓ Message successfully delivered to {chat_id}")
    else:
        log_message(f"✗ Failed to send message to {chat_id}: {response.status_code} - {response.text}")
    return success

def main():
    log_message("Starting message broadcast script")
    
    # Get authentication token
    token = get_marzban_token()
    if not token:
        log_message("Failed to authenticate with Marzban API. Exiting.")
        return
    
    # Get all users
    users = get_users(token)
    log_message(f"Found {len(users)} users in Marzban")
    
    # Send message to each user using username as telegram_id
    success_count = 0
    failed_count = 0
    
    log_message("Beginning message broadcast to users...")
    for i, user in enumerate(users, 1):
        username = user.get("username", "")
        
        # Check if username is a number (likely a Telegram ID)
        if username and username.isdigit():
            telegram_id = username
            log_message(f"Processing user {i}/{len(users)}: Telegram ID {telegram_id}")
            
            if send_telegram_message(telegram_id, MESSAGE):
                success_count += 1
            else:
                failed_count += 1
            
            # Sleep to avoid hitting Telegram API rate limits
            time.sleep(1)
        else:
            log_message(f"Skipping user {i}/{len(users)}: Username '{username}' is not a valid Telegram ID")
    
    log_message(f"\nBroadcast complete: {success_count} messages sent successfully, {failed_count} failed")

if __name__ == "__main__":
    main()
