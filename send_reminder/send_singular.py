import sys
import requests
import argparse
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN, CHANNEL_ID, SHOP_ID, YUKASSA_API

# Configuration
MARZBAN_URL = "https://oblakovpn.org:8000"  # Replace with your Marzban URL

DEFAULT_MESSAGE = """👋 Мы заметили, что Вы не завершили подключение к нашему VPN.

🎁 Попробуйте ещё раз - дарим Вам 20 дней бесплатного доступа.

🫶 Далее - всего 50 руб/мес.

⚙️ Просто запустите бота 👉🏻 /start и следуйте инструкции — это займёт не больше минуты.

❓ Если всё равно что-то не получится — напишите нам в поддержку, мы обязательно поможем.

📩 Связаться с нами — @vpnoblako"""

DEFAULT_MESSAGE2 = ("Инструкция по оплате VPN-подписки 😎\n\n"
                   "1. Запуск бота:\n"
                    "Если у вас не отображается главное меню, введите команду /start. Это запустит бота и отобразит главное меню. 🚀\n\n"
                    "2. Выбор оплаты:\n"
                    "В главном меню нажмите кнопку «Оплатить подписку». 💳\n\n"
                    "3. Проверка статуса:\n"
                    "Вы можете в любой момент проверить, сколько дней подписки у вас осталось, непосредственно в боте. ⏰\n\n"
                    "Важно:\n"
                    "Если у вас возникают трудности с отображением главного меню, введите команду /start для повторного запуска бота и получения доступа к нужной функции. 🔄"
                    )

DEFAULT_MESSAGE3 = ("🔥 ВРЕМЕННАЯ АКЦИЯ! 🔥\n\n"
            "🚀 Вечная подписка всего за 700 рублей! 🚀\n"
            "⏳ Успей до конца акции! Ведь такого больше НЕ БУДЕТ!"
            )

# Import credentials



def get_marzban_token():
    """Get authentication token from Marzban API"""
    url = f"{MARZBAN_URL}/api/admin/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"Failed to get token: {response.text}")
        return None
    return response.json().get("access_token")

def send_telegram_message(chat_id, message):
    """Send message to a Telegram user"""
    url = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return True
    else:
        print(f"Error sending message: {response.text}")
        return False

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Send a Telegram message to a specific user")
    parser.add_argument("telegram_id", type=int, help="Telegram user ID to send the message to")
    parser.add_argument("--message", "-m", type=str, default=DEFAULT_MESSAGE, 
                        help="Message to send (default: the predefined message)")
    
    args = parser.parse_args()
    
    # Get the target Telegram ID and message
    telegram_id = args.telegram_id
    message = args.message
    
    print(f"Sending message to Telegram ID: {telegram_id}")
    print(f"Message: {message}")
    
    # Send the message
    if send_telegram_message(telegram_id, message):
        print(f"✓ Message sent successfully to Telegram ID {telegram_id}")
    else:
        print(f"✗ Failed to send message to Telegram ID {telegram_id}")

if __name__ == "__main__":
    main()
