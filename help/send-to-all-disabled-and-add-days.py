import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN
import requests
import telebot
import time
from datetime import datetime, timedelta

MARZBAN_URL = "https://oblakovpn.org:8000"
bot = telebot.TeleBot(API_TOKEN)

def get_marzban_token():
    print("🔑 Authenticating with Marzban API...")
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    print("✅ Authentication successful")
    return response.json()["access_token"]

def get_all_users():
    print("👥 Fetching all users...")
    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    users = response.json()["users"]
    print(f"📊 Found {len(users)} total users")
    return users

def enable_user(username):
    print(f"🔓 Enabling user {username}...")
    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/user/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"status": "active"}
    response = requests.put(url, headers=headers, json=data)
    return response.json()

def extend_user_subscription(username, days=20):
    print(f"⏰ Extending subscription for {username} by {days} days...")
    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/user/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    user_data = response.json()
    
    current_time = int(datetime.now().timestamp())
    current_expire = user_data.get("expire", 0) or 0
    
    if current_expire > current_time:
        new_expire = current_expire + (days * 24 * 3600)
    else:
        new_expire = current_time + (days * 24 * 3600)
    
    data = {
        "expire": new_expire,
        "status": "active"
    }
    
    response = requests.put(url, headers=headers, json=data)
    return response.json()

def send_message_and_extend():
    print("🚀 Starting user processing...")
    print("=" * 50)
    
    users = get_all_users()
    
    message_text = """👋 Мы заметили, что Вы не завершили подключение к нашему VPN.

🎁 Попробуйте ещё раз - дарим Вам 20 дней бесплатного доступа.

🫶 Далее - всего 50 руб/мес.

⚙️ Просто запустите бота 👉🏻 /start и следуйте инструкции — это займёт не больше минуты.

❓ Если всё равно что-то не получится — напишите нам в поддержку, мы обязательно поможем.

📩 Связаться с нами — @vpnoblako"""
    
    stats = {
        'total_users': len(users),
        'zero_traffic_users': 0,
        'enabled_users': 0,
        'extended_subscriptions': 0,
        'messages_sent': 0,
        'message_errors': 0,
        'processing_errors': 0
    }
    
    for user in users:
        try:
            if user["lifetime_used_traffic"] == 0:
                stats['zero_traffic_users'] += 1
                username = user["username"]
                
                print(f"🔄 Processing user {username} (zero traffic)...")
                
                if user["status"] == "disabled":
                    enable_user(username)
                    stats['enabled_users'] += 1
                    print(f"✅ User {username} enabled")
                
                extend_user_subscription(username, 20)
                stats['extended_subscriptions'] += 1
                print(f"✅ Subscription extended for {username}")
                
                try:
                    user_id = int(username)
                    bot.send_message(user_id, message_text)
                    stats['messages_sent'] += 1
                    print(f"✅ Message sent to user {user_id}")
                    time.sleep(1)
                except Exception as e:
                    stats['message_errors'] += 1
                    print(f"❌ Error sending message to user {username}: {e}")
                    
        except Exception as e:
            stats['processing_errors'] += 1
            print(f"❌ Error processing user {user['username']}: {e}")
    
    print("\n" + "=" * 50)
    print("📈 EXECUTION STATISTICS")
    print("=" * 50)
    print(f"👥 Total users: {stats['total_users']}")
    print(f"🎯 Users with zero traffic: {stats['zero_traffic_users']}")
    print(f"🔓 Users enabled: {stats['enabled_users']}")
    print(f"⏰ Subscriptions extended: {stats['extended_subscriptions']}")
    print(f"📨 Messages sent successfully: {stats['messages_sent']}")
    print(f"❌ Message sending errors: {stats['message_errors']}")
    print(f"⚠️  Processing errors: {stats['processing_errors']}")
    print(f"✅ Success rate: {((stats['messages_sent'] / max(stats['zero_traffic_users'], 1)) * 100):.1f}%")
    print("=" * 50)
    print("🏁 Execution completed!")

if __name__ == "__main__":
    send_message_and_extend()