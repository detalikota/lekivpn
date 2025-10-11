import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN
import requests
import telebot
from datetime import datetime, timedelta

MARZBAN_URL = "https://oblakovpn.org:8000"
TIME_DIFFERENCE = 3  # Time difference in hours

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    return response.json()["access_token"]

def check_new_users_traffic():
    try:
        # Get current time and time 3 hours ago, adjusted for time difference
        current_time = datetime.now() - timedelta(hours=TIME_DIFFERENCE)
        three_hours_ago = current_time - timedelta(hours=3)
        one_hour_ago = current_time - timedelta(hours=1)

        # Get all users
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/users"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        users = response.json()["users"]

        # Check each user
        for user in users:
            try:
                # Convert created_at string to datetime
                created_at = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))

                # Check if user was created between 1 and 3 hours ago
                if three_hours_ago <= created_at <= one_hour_ago:
                    # Check if lifetime_used_traffic is 0
                    if user["lifetime_used_traffic"] == 0:
                        # Try to send message to user
                        try:
                            user_id = int(user["username"])  # username contains Telegram ID
                            print(f"Sent help message to {user_id}")
                            result = bot.send_message(
                                user_id,
                                "Не получается подключиться к VPN?🤔 Бывает! 👉 Нажмите «Помощь», и мы вместе все исправим! 🚀"
                            )
                        except Exception as e:
                            print(f"Error sending message to user {user['username']}: {e}")
            except Exception as e:
                print(f"Error processing user {user['username']}: {e}")
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    check_new_users_traffic()


