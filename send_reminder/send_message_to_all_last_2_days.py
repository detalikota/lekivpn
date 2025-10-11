import sys
import requests
import time
import datetime
from datetime import timezone, timedelta
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN, CHANNEL_ID, SHOP_ID, YUKASSA_API

# Configuration
MARZBAN_URL = "https://oblakovpn.org:8000"  # Replace with your Marzban URL
MESSAGE = ("Инструкция по оплате VPN-подписки 😎\n\n"
            "1. Запуск бота:\n"
            "Если у вас не отображается главное меню, введите команду /start. Это запустит бота и отобразит главное меню. 🚀\n\n"
            "2. Выбор оплаты:\n"
            "В главном меню нажмите кнопку «Оплатить подписку». 💳\n\n"
            "3. Проверка статуса:\n"
            "Вы можете в любой момент проверить, сколько дней подписки у вас осталось, непосредственно в боте. ⏰\n\n"
            "Важно:\n"
            "Если у вас возникают трудности с отображением главного меню, введите команду /start для повторного запуска бота и получения доступа к нужной функции. 🔄"
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
    
    # Calculate the timestamp for 2 days ago
    two_days_ago = datetime.datetime.now(timezone.utc) - timedelta(days=2)
    
    # Send message to each user that hasn't been online for the last 2 days
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    log_message("Beginning message broadcast to users who haven't been online for 2 days...")
    for i, user in enumerate(users, 1):
        username = user.get("username", "")
        online_at_str = user.get("online_at")
        
        # Skip if no online_at data
        if not online_at_str:
            log_message(f"Skipping user {i}/{len(users)}: No online_at data")
            skipped_count += 1
            continue
        
        # Parse the online_at timestamp
        try:
            # Ensure we're parsing to timezone-aware datetime
            if 'Z' in online_at_str:
                online_at = datetime.datetime.fromisoformat(online_at_str.replace('Z', '+00:00'))
            else:
                # If no timezone info in string, assume UTC
                online_at = datetime.datetime.fromisoformat(online_at_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            log_message(f"Skipping user {i}/{len(users)}: Invalid online_at format: {online_at_str}")
            skipped_count += 1
            continue
        
        # Check if user hasn't been online for 2 days
        if online_at < two_days_ago:
            # Check if username is a number (likely a Telegram ID)
            if username and username.isdigit():
                telegram_id = username
                log_message(f"Processing user {i}/{len(users)}: Telegram ID {telegram_id}, Last online: {online_at}")
                
                if send_telegram_message(telegram_id, MESSAGE):
                    success_count += 1
                else:
                    failed_count += 1
                
                # Sleep to avoid hitting Telegram API rate limits
                time.sleep(1)
            else:
                log_message(f"Skipping user {i}/{len(users)}: Username '{username}' is not a valid Telegram ID")
                skipped_count += 1
        else:
            log_message(f"Skipping user {i}/{len(users)}: User was online recently: {online_at}")
            skipped_count += 1
    
    log_message(f"\nBroadcast complete: {success_count} messages sent successfully, {failed_count} failed, {skipped_count} skipped")

if __name__ == "__main__":
    main()