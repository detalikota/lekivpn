import sys
sys.path.append('/opt/marzban')
from cred import USERNAME, PASSWORD, API_TOKEN, CHANNEL_ID, SHOP_ID, YUKASSA_API
import telebot
from telebot import types
import requests
import json
from datetime import datetime, timedelta
import threading
import time
from yookassa import Configuration, Payment
import uuid
from collections import defaultdict
import logging
import threading
from flask import Flask, request
from notification_store import notification_store

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/remote/bot.log')
    ]
)
logger = logging.getLogger(__name__)
interaction_logger = logging.getLogger('user_interactions')
interaction_handler = logging.FileHandler('/var/log/remote/user_interactions.log')
interaction_formatter = logging.Formatter('%(asctime)s - USER:%(message)s')
interaction_handler.setFormatter(interaction_formatter)
interaction_logger.addHandler(interaction_handler)
interaction_logger.setLevel(logging.INFO)

def log_user_interaction(user_id, username, action, additional_info=""):
    """Log user interactions with detailed information."""
    user_info = f"{user_id}"
    if username:
        user_info += f" (@{username})"
    log_message = f"{user_info} - {action}"
    if additional_info:
        log_message += f" - {additional_info}"
    interaction_logger.info(log_message)

# Configure YooKassa
Configuration.account_id = SHOP_ID
Configuration.secret_key = YUKASSA_API

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

# Marzban settings
MARZBAN_URL = "https://lekivpn.ru"
CHANNEL_LINK = "https://t.me/lekivpn"

# Thread-safe notification tracker
app = Flask(__name__)

YOOKASSA_IP_RANGES = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.156.11',
    '77.75.156.35',
    '77.75.154.128/25',
    '2a02:5180::/32'
]

def setup_referral_database():
    """Set up the referral database."""
    import sqlite3
    try:
        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id TEXT NOT NULL,
            referred_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_status INTEGER DEFAULT 0,
            UNIQUE(referred_id)
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            reward_type TEXT NOT NULL,
            reward_days INTEGER NOT NULL,
            awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            referral_count INTEGER NOT NULL
        )
        ''')
        conn.commit()
        conn.close()
        logger.info("Referral database initialized")
        return True
    except Exception as e:
        logger.error(f"Error setting up referral database: {e}")
        return False

def generate_referral_link(user_id):
    """Generate a referral link for a user."""
    import base64
    encoded_id = base64.b64encode(str(user_id).encode()).decode()
    return f"https://t.me/leki_vpn_bot?start=ref_{encoded_id}"

def decode_referral_code(code):
    """Decode referral code to get user ID."""
    try:
        import base64
        if code.startswith('ref_'):
            encoded_id = code[4:]
            decoded_id = base64.b64decode(encoded_id.encode()).decode()
            return decoded_id
        return None
    except Exception:
        return None

def add_referral(referrer_id, referred_id):
    """Add a referral relationship only if it's a new user."""
    import sqlite3
    try:
        existing_config = get_user_config(str(referred_id))
        if "error" not in existing_config or "User not found" not in existing_config.get("error", ""):
            logger.info(f"User {referred_id} already exists in Marzban, not counting as referral")
            return False

        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM referrals WHERE referred_id = ?", (referred_id,))
        if cursor.fetchone():
            conn.close()
            logger.info(f"User {referred_id} already has a referrer")
            return False

        cursor.execute(
            "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (referrer_id, referred_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"Added referral: {referrer_id} -> {referred_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding referral: {e}")
        return False

def get_referral_stats(user_id):
    """Get referral statistics for a user."""
    import sqlite3
    try:
        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user_id,)
        )
        total_referrals = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND paid_status = 1",
            (user_id,)
        )
        paid_referrals = cursor.fetchone()[0]
        conn.close()
        return total_referrals, paid_referrals
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        return 0, 0

def mark_referral_as_paid(referred_id):
    """Mark a referral as paid and check for rewards."""
    import sqlite3
    try:
        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE referrals SET paid_status = 1 WHERE referred_id = ? AND paid_status = 0",
            (referred_id,)
        )
        if cursor.rowcount == 0:
            conn.close()
            return None

        cursor.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id = ?",
            (referred_id,)
        )
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        referrer_id = result[0]

        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND paid_status = 1",
            (referrer_id,)
        )
        paid_count = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        reward = apply_referral_reward(referrer_id, 15, f"referral_{paid_count}")
        bonus_reward = None
        if paid_count == 10:
            bonus_reward = apply_referral_reward(referrer_id, 165, "ten_referrals_bonus")
        elif paid_count == 20:
            bonus_reward = apply_referral_reward(referrer_id, 715, "twenty_referrals_bonus")

        return {"referrer_id": referrer_id, "paid_count": paid_count, "reward": reward, "bonus_reward": bonus_reward}
    except Exception as e:
        logger.error(f"Error marking referral as paid: {e}")
        return None

def apply_referral_reward(user_id, days, reward_type):
    """Apply referral reward to user."""
    import sqlite3
    try:
        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO rewards (user_id, reward_type, reward_days, referral_count) VALUES (?, ?, ?, ?)",
            (user_id, reward_type, days, get_referral_stats(user_id)[1])
        )
        conn.commit()
        conn.close()

        user_config = get_user_config(str(user_id))
        if "error" in user_config:
            logger.error(f"Cannot get user config for reward: {user_id}")
            return False

        current_expire = user_config.get("expire", 0) or 0
        user_status = user_config.get("status", "")
        if current_expire == 0 and user_status == "active":
            logger.info(f"User {user_id} already has eternal subscription, skipping reward application")
            try:
                bot.send_message(
                    str(user_id),
                    f"🎁 Вы получили награду за реферала: {days} дней!\n"
                    f"Но у вас уже есть вечная подписка, поэтому изменений не требуется."
                )
            except Exception:
                pass
            return True

        current_time = int(time.time())
        if current_expire > current_time:
            new_expire = current_expire + (days * 24 * 3600)
        else:
            new_expire = current_time + (days * 24 * 3600)

        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/user/{user_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = {
            "expire": new_expire,
            "status": "active"
        }
        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Applied {days} days reward to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error applying referral reward: {e}")
        return False

def track_referral_user_creation(user_id):
    """Track when a referred user actually gets created in Marzban."""
    import sqlite3
    try:
        conn = sqlite3.connect('/var/lib/marzban/referral.sqlite3')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id = ? AND paid_status = 0",
            (user_id,)
        )
        result = cursor.fetchone()
        if result:
            referrer_id = result[0]
            logger.info(f"Referred user {user_id} was created in Marzban, referrer: {referrer_id}")
            try:
                bot.send_message(
                    referrer_id,
                    f"✅ Ваш реферал создал VPN аккаунт!\n"
                    f"Теперь ждем когда он оплатит подписку, чтобы вы получили награду."
                )
            except Exception as e:
                logger.error(f"Error sending referral creation notification: {e}")
        conn.close()
    except Exception as e:
        logger.error(f"Error tracking referral user creation: {e}")

def setup_payment_tracker():
    """Set up a database to track payments."""
    import sqlite3
    try:
        conn = sqlite3.connect('/opt/marzban/payments.db')
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            user_id TEXT,
            amount TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            attempts INTEGER DEFAULT 0,
            last_error TEXT
        )
        ''')
        cursor.execute("PRAGMA table_info(payments)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'subscription_extended' not in columns:
            cursor.execute('ALTER TABLE payments ADD COLUMN subscription_extended INTEGER DEFAULT 0')
            logger.info("Added subscription_extended column to payments table")

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhook_logs (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            ip TEXT,
            data TEXT
        )
        ''')
        conn.commit()
        conn.close()
        logger.info("Payment tracking database initialized")
        return True
    except Exception as e:
        logger.error(f"Error setting up payment tracker: {e}", exc_info=True)
        return False

def create_payment(user_id, amount="99.00"):
    """Create a payment for subscription."""
    try:
        idempotence_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {"value": amount, "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/leki_vpn_bot"
            },
            "capture": True,
            "description": f"Оплата подписки доступа к сервису для пользователя с ID: {user_id}",
            "metadata": {"user_id": str(user_id), "amount": amount},

            # >>> ОБЯЗАТЕЛЬНО, если в ЮKassa включена касса/54-ФЗ
            "receipt": {
                "customer": {
                    # хотя бы одно из полей обязательно
                    "email": f"{user_id}@lekivpn.local"  # или "phone": "+79XXXXXXXXX"
                },
                "items": [{
                    "description": "L-VPN подписка",
                    "amount": {"value": amount, "currency": "RUB"},
                    "quantity": "1",
                    "vat_code": 4,              # НДС 0%
                    "payment_subject": "service",
                    "payment_mode": "full_prepayment"
                }]
            }
        }, idempotence_key)

        # ... ваш код записи в БД без изменений ...
        return {"confirmation_url": payment.confirmation.confirmation_url, "payment_id": payment.id}

    except ApiError as e:
        # детальный разбор ошибки от ЮKassa
        logger.error(
            "YooKassa ApiError on create_payment: http_code=%s type=%s code=%s message=%s params=%s",
            getattr(e, "http_code", None), getattr(e, "type", None),
            getattr(e, "code", None), getattr(e, "message", None),
            getattr(e, "params", None),
            exc_info=True
        )
        raise Exception(f"Payment creation error: {e.code or e.type or 'unknown'}: {e.message or str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating payment: {e}", exc_info=True)
        raise Exception(f"Payment creation error: {str(e)}")

def apply_subscription_extension(user_id, payment_id):
    """Apply the subscription extension based on payment amount."""
    logger.info(f"Applying subscription extension for user {user_id}, payment {payment_id}")
    import sqlite3
    import requests
    from time import time

    conn = sqlite3.connect('/opt/marzban/payments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT amount FROM payments WHERE payment_id = ?", (payment_id,))
    row = cursor.fetchone()
    if not row:
        logger.error(f"No payment record found for {payment_id}")
        conn.close()
        return False

    raw_amount = row[0]
    try:
        amount_value = float(raw_amount)
    except (ValueError, TypeError):
        logger.error(f"Invalid amount stored for payment {payment_id}: {raw_amount}")
        amount_value = 0.0

    # Determine subscription type based on amount
    if amount_value >= 990.0:
        is_eternal = True
        is_yearly = False
        days_to_add = 0
        subscription_type = "eternal"
    elif amount_value >= 699.0:
        is_eternal = False
        is_yearly = True
        days_to_add =  365
        subscription_type = "yearly"
    elif amount_value >= 399.0:
        is_eternal = False
        is_yearly = False
        days_to_add = 180  # 6 months
        subscription_type = "6_months"
    elif amount_value >= 199.0:
        is_eternal = False
        is_yearly = False
        days_to_add = 90   # 3 months
        subscription_type = "3_months"
    else:
        is_eternal = False
        is_yearly = False
        days_to_add = 30   # 1 month
        subscription_type = "monthly"

    logger.info(f"Payment {payment_id} amount={amount_value}, type={subscription_type}, days={days_to_add}")

    user_str = str(user_id)
    user_conf = get_user_config(user_str)
    if "error" in user_conf:
        logger.error(f"Cannot fetch user config for {user_id}: {user_conf['error']}")
        cursor.execute("UPDATE payments SET last_error=? WHERE payment_id=?",
                       (user_conf['error'], payment_id))
        conn.commit()
        conn.close()
        return False

    if user_conf.get("status") in ("disabled", "expired"):
        logger.info(f"User {user_id} status={user_conf.get('status')}, forcing activation")
        act = force_activate_user(user_str)
        if isinstance(act, dict) and "error" in act:
            logger.error(f"Force-activate failed for {user_id}: {act['error']}")
            cursor.execute("UPDATE payments SET last_error=? WHERE payment_id=?",
                           (act['error'], payment_id))
            conn.commit()
            conn.close()
            return False

    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/user/{user_str}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if is_eternal:
        logger.info(f"Setting eternal subscription for user {user_id}")
        payload = {"expire": 0, "status": "active"}
        try:
            resp = requests.put(url, headers=headers, json=payload)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"HTTP error setting eternal subscription: {e}")
            cursor.execute("UPDATE payments SET last_error=? WHERE payment_id=?",
                           (str(e), payment_id))
            conn.commit()
            conn.close()
            return False

        final_conf = get_user_config(user_str)
        if final_conf.get("status") == "active" and final_conf.get("expire") in (None, 0):
            logger.info(f"Eternal subscription successfully set for {user_id}")
            cursor.execute("UPDATE payments SET subscription_extended=1 WHERE payment_id=?",
                           (payment_id,))
            conn.commit()
            conn.close()
            try:
                bot.send_message(user_str, "✅ Оплата прошла успешно! Вам установлена вечная подписка.")
            except Exception as e:
                logger.error(f"Error sending eternal subscription notification: {e}")
            
            referral_result = mark_referral_as_paid(user_id)
            if referral_result:
                send_referral_notification(referral_result)
            return True
    else:
        logger.info(f"Extending subscription for user {user_id} by {days_to_add} days")
        current_time = int(time())
        current_expire = user_conf.get("expire", 0) or 0
        if current_expire > current_time:
            new_expire = current_expire + (days_to_add * 24 * 3600)
        else:
            new_expire = current_time + (days_to_add * 24 * 3600)

        payload = {"expire": new_expire, "status": "active"}
        try:
            resp = requests.put(url, headers=headers, json=payload)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"HTTP error setting subscription: {e}")
            cursor.execute("UPDATE payments SET last_error=? WHERE payment_id=?",
                           (str(e), payment_id))
            conn.commit()
            conn.close()
            return False

        final_conf = get_user_config(user_str)
        if final_conf.get("status") == "active" and final_conf.get("expire", 0) > current_time:
            logger.info(f"Subscription successfully set for {user_id}, new expire={new_expire}")
            cursor.execute("UPDATE payments SET subscription_extended=1 WHERE payment_id=?",
                           (payment_id,))
            conn.commit()
            conn.close()
            try:
                days_left = (new_expire - current_time) // (24 * 3600)
                period_text = {
                    "3_months": "на 3 месяца",
                    "6_months": "на 6 месяцев", 
                    "yearly": "на 1 год",
                    "monthly": "на 30 дней"
                }.get(subscription_type, f"на {days_to_add} дней")
                bot.send_message(user_str, f"✅ Оплата прошла успешно! Ваша подписка продлена {period_text}. Осталось {days_left} дней.")
            except Exception as e:
                logger.error(f"Error sending subscription notification: {e}")
            
            referral_result = mark_referral_as_paid(user_id)
            if referral_result:
                send_referral_notification(referral_result)
            return True

    return False

def send_referral_notification(referral_result):
    """Send referral notification to referrer."""
    referrer_id = referral_result["referrer_id"]
    paid_count = referral_result["paid_count"]
    try:
        if paid_count == 1:
            bot.send_message(referrer_id,
                "🎉 Поздравляем! Ваш реферал оплатил подписку!\n"
                "🎁 Вы получили 15 дней бесплатного VPN!")
        elif paid_count == 10:
            bot.send_message(referrer_id,
                "🏆 Невероятно! У вас уже 10 оплаченных рефералов!\n"
                "🎁 Вы получили 15 дней + бонус 6 месяцев бесплатного VPN!")
        elif paid_count == 20:
            bot.send_message(referrer_id,
                "👑 Легенда! У вас 20 оплаченных рефералов!\n"
                "🎁 Вы получили 15 дней + бонус 2 года бесплатного VPN!")
        else:
            bot.send_message(referrer_id,
                f"🎉 Ваш реферал #{paid_count} оплатил подписку!\n"
                "🎁 Вы получили 15 дней бесплатного VPN!")
    except Exception as e:
        logger.error(f"Error sending referral reward notification: {e}")

def check_unprocessed_payments():
    """Check for unprocessed payments and process them."""
    while True:
        try:
            import sqlite3
            logger.info("Running scheduled payment verification")
            
            try:
                Configuration.account_id = SHOP_ID
                Configuration.secret_key = YUKASSA_API
                from yookassa import Payment as YooKassaPayment
                try:
                    recent_payments = YooKassaPayment.list()
                    logger.info(f"YooKassa API credentials verified successfully")
                except TypeError:
                    logger.info("Trying alternative YooKassa API call format")
                    recent_payments = YooKassaPayment.list({})
                    logger.info(f"YooKassa API credentials verified successfully using alternative format")
            except Exception as auth_error:
                logger.error(f"YooKassa API authentication error: {auth_error}")
                time.sleep(30)
                continue

            conn = sqlite3.connect('/opt/marzban/payments.db')
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payment_id, user_id FROM payments
                WHERE (
                    (status = 'created' OR status = 'webhook_received') AND attempts < 10
                    AND created_at > datetime('now', '-30 day')
                ) OR (
                    status = 'processed' AND subscription_extended = 0
                    AND created_at > datetime('now', '-30 day')
                    AND attempts < 10
                )
                """
            )
            unprocessed_payments = cursor.fetchall()
            logger.info(f"Found {len(unprocessed_payments)} unprocessed payments to verify")

            for payment_id, user_id in unprocessed_payments:
                try:
                    payment_info = YooKassaPayment.find_one(payment_id)
                    logger.info(f"Retrieved payment {payment_id} status: {payment_info.status}")
                    
                    cursor.execute(
                        "UPDATE payments SET attempts = attempts + 1 WHERE payment_id = ?",
                        (payment_id,)
                    )
                    conn.commit()

                    if payment_info.status == "succeeded":
                        logger.info(f"Found succeeded payment {payment_id} for user {user_id} - processing now")
                        extension_success = apply_subscription_extension(user_id, payment_id)
                        if extension_success:
                            cursor.execute(
                                "UPDATE payments SET status = 'processed', processed_at = datetime('now') WHERE payment_id = ?",
                                (payment_id,)
                            )
                            conn.commit()
                            logger.info(f"Payment {payment_id} successfully processed for user {user_id}")
                        else:
                            cursor.execute(
                                "SELECT status FROM payments WHERE payment_id = ?",
                                (payment_id,)
                            )
                            current_status = cursor.fetchone()[0]
                            if current_status == 'processed':
                                logger.error(f"Payment {payment_id} is marked as processed but subscription was not extended. Will retry.")
                            else:
                                cursor.execute(
                                    "UPDATE payments SET status = 'pending_extension' WHERE payment_id = ?",
                                    (payment_id,)
                                )
                                conn.commit()
                    elif payment_info.status == "canceled":
                        cursor.execute(
                            "UPDATE payments SET status = 'canceled', processed_at = datetime('now') WHERE payment_id = ?",
                            (payment_id,)
                        )
                        conn.commit()
                        logger.info(f"Payment {payment_id} marked as canceled")
                except Exception as e:
                    logger.error(f"Error checking payment {payment_id}: {e}")
            conn.close()
        except Exception as e:
            logger.error(f"Error in payment verification process: {e}", exc_info=True)
        time.sleep(120)

def setup_yookassa_webhook():
    return True

def is_valid_ip(ip_str):
    """Accept all IPs for YooKassa webhooks."""
    logger.info(f"Accepting webhook from IP: {ip_str}")
    from ipaddress import ip_address, ip_network
    
    yookassa_ip_ranges = [
        '185.71.76.0/27',
        '185.71.77.0/27',
        '77.75.153.0/25',
        '77.75.154.128/25',
        '77.75.156.11',
        '77.75.156.35',
        '2a02:5180::/32'
    ]
    try:
        client_ip = ip_address(ip_str)
        networks = []
        for ip_range in yookassa_ip_ranges:
            if '/' in ip_range:
                networks.append(ip_network(ip_range))
            else:
                networks.append(ip_network(f"{ip_range}/32"))

        in_known_range = False
        for network in networks:
            if client_ip in network:
                in_known_range = True
                break

        if not in_known_range:
            logger.info(f"IP {ip_str} not in YooKassa known ranges, but accepting anyway")
    except Exception as e:
        logger.error(f"Error checking IP {ip_str}: {e}")

    return True

@app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook():
    client_ip = request.remote_addr
    interaction_logger.info(f"WEBHOOK_ACCESS - IP: {client_ip}")
    
    try:
        client_ip = request.remote_addr
        logger.info(f"Webhook from IP: {client_ip}")

        try:
            event = request.get_json(force=True)
        except Exception as je:
            logger.error(f"Invalid JSON payload: {je}")
            return "Bad Request", 400

        logger.info(f"Webhook payload: {event}")

        try:
            import sqlite3
            conn_w = sqlite3.connect('/opt/marzban/webhook_logs.db')
            cur_w = conn_w.cursor()
            cur_w.execute('''
                CREATE TABLE IF NOT EXISTS webhook_logs (
                  id INTEGER PRIMARY KEY,
                  timestamp TEXT,
                  ip TEXT,
                  data TEXT
                )
            ''')
            cur_w.execute(
                "INSERT INTO webhook_logs (timestamp, ip, data) VALUES (?, ?, ?)",
                (datetime.now().isoformat(), client_ip, json.dumps(event))
            )
            conn_w.commit()
            conn_w.close()
        except Exception as db_e:
            logger.error(f"Failed to store webhook log: {db_e}")

        if event.get("event") != "payment.succeeded":
            return "OK", 200

        obj = event.get("object", {})
        payment_id = obj.get("id")
        if not payment_id:
            logger.error("No payment ID in webhook")
            return "Bad Request", 400

        meta = obj.get("metadata", {})
        user_id = meta.get("user_id")
        if not user_id:
            logger.error(f"No user_id in metadata for payment {payment_id}")
            return "Bad Request", 400

        raw_amt = obj.get("amount", {}).get("value", "0")
        try:
            amt = float(raw_amt)
        except (ValueError, TypeError):
            amt = 0.0

        logger.info(f"Webhook payment {payment_id} for user {user_id}, amount={amt}")

        import sqlite3
        conn = sqlite3.connect('/opt/marzban/payments.db')
        cursor = conn.cursor()
        cursor.execute("SELECT status, subscription_extended FROM payments WHERE payment_id = ?", (payment_id,))
        existing = cursor.fetchone()
        if existing:
            if existing[0] == 'processed' and existing[1] == 1:
                logger.info(f"{payment_id} already processed. Skipping.")
                conn.close()
                return "OK", 200
            cursor.execute("UPDATE payments SET status='webhook_received' WHERE payment_id=?", (payment_id,))
        else:
            cursor.execute(
                "INSERT INTO payments (payment_id, user_id, amount, status) VALUES (?, ?, ?, ?)",
                (payment_id, user_id, raw_amt, 'webhook_received')
            )
        conn.commit()

        success = apply_subscription_extension(user_id, payment_id)
        if success: 
            cursor.execute(
                "UPDATE payments SET status='processed', subscription_extended=1, processed_at=datetime('now')"
                " WHERE payment_id = ?",
                (payment_id,)
            )
            conn.commit()
            logger.info(f"Webhook processing completed for payment {payment_id}, user {user_id}")
        else:
            cursor.execute(
                "UPDATE payments SET status='webhook_received_extension_failed', processed_at=datetime('now')"
                " WHERE payment_id = ?",
                (payment_id,)
            )
            conn.commit()
        conn.close()

        return "OK", 200
    except Exception as e:
        interaction_logger.info(f"WEBHOOK_ERROR - IP: {client_ip} - Error: {str(e)[:100]}")
        logger.error(f"Unhandled exception in webhook handler: {e}", exc_info=True)
        return "Internal Server Error", 500

def run_webhook_server():
    """Run the Flask webhook server with proper configuration."""
    from werkzeug.serving import run_simple
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('/var/lib/marzban/certs/fullchain.pem', '/var/lib/marzban/certs/key.pem')
    run_simple('0.0.0.0', 8443, app, ssl_context=context)

webhook_thread = threading.Thread(target=run_webhook_server)
webhook_thread.daemon = True
webhook_thread.start()

def get_marzban_token():
    """Get authentication token from Marzban server."""
    try:
        url = f"{MARZBAN_URL}/api/admin/token"
        data = {
            "username": USERNAME,
            "password": PASSWORD
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting Marzban token: {e}")
        raise Exception(f"Authentication error: {e}")

def get_user_config(user_id):
    """Get user configuration from Marzban."""
    try:
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/user/{user_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return {"error": "User not found"}
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting user config for {user_id}: {e}")
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in get_user_config for {user_id}: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def extend_subscription(username):
    """Extend user subscription by 30 days."""
    logger.info(f"Attempting to extend subscription for user {username}")
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info(f"Getting Marzban token for subscription extension (attempt {retry_count+1}/{max_retries})")
            token = get_marzban_token()
            url = f"{MARZBAN_URL}/api/user/{username}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Get current user data
            logger.info(f"Fetching current user data for {username}")
            current_user = get_user_config(username)
            if "error" in current_user:
                logger.error(f"Error getting user data for {username}: {current_user['error']}")
                return {"error": current_user["error"]}
            if not current_user or "username" not in current_user:
                logger.error(f"User {username} not found or invalid response from API: {current_user}")
                return {"error": "User not found"}
            logger.info(f"Current user data for {username}: status={current_user.get('status')}, "
                       f"expire={current_user.get('expire')}, data_limit={current_user.get('data_limit')}")

            current_time = int(time.time())
            current_expire = current_user.get("expire", 0)
            if current_expire is None:
                logger.warning(f"User {username} has None expiry - treating as 0")
                current_expire = 0

            current_expire = int(current_expire)

            if current_expire > current_time:
                new_expire = current_expire + (30 * 24 * 3600)
                logger.info(f"Extending active subscription for {username} from {current_expire} "
                          f"({datetime.fromtimestamp(current_expire).strftime('%Y-%m-%d %H:%M:%S')}) "
                          f"to {new_expire} ({datetime.fromtimestamp(new_expire).strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                new_expire = current_time + (30 * 24 * 3600)
                logger.info(f"Starting new subscription period for {username} from now until {new_expire} "
                           f"({datetime.fromtimestamp(new_expire).strftime('%Y-%m-%d %H:%M:%S')})")

            data = {
                "expire": new_expire,
                "status": "active"
            }
            logger.info(f"Sending update request for {username} with data: {data}")
            response = requests.put(url, headers=headers, json=data)

            logger.info(f"API response status code: {response.status_code}")
            logger.info(f"API response headers: {response.headers}")
            logger.info(f"API response content: {response.text[:1000]}")
            response.raise_for_status()
            result = response.json()
            logger.info(f"API update successful for {username}: {result}")

            logger.info(f"Verifying subscription update for {username}")
            updated_user = get_user_config(username)
            if "error" in updated_user:
                logger.error(f"Error verifying user update for {username}: {updated_user['error']}")
                raise Exception(f"Update verification failed: {updated_user['error']}")

            if updated_user.get("status") != "active":
                logger.error(f"Status update failed for {username}. Expected: active, Got: {updated_user.get('status')}")
                logger.error(f"Full updated user data: {updated_user}")
                status_data = {"status": "active"}
                logger.info(f"Attempting to explicitly set just status for {username}")
                status_response = requests.put(url, headers=headers, json=status_data)
                status_response.raise_for_status()
                logger.info(f"Status update response: {status_response.text[:1000]}")

            updated_expire = updated_user.get("expire", 0)
            if updated_expire == 0:
                logger.error(f"Expiry is still 0 for {username} after update")
                expire_data = {"expire": new_expire}
                logger.info(f"Attempting to explicitly set just expire for {username}")
                expire_response = requests.put(url, headers=headers, json=expire_data)
                expire_response.raise_for_status()
                logger.info(f"Expire update response: {expire_response.text[:1000]}")
            elif abs(updated_expire - new_expire) > 120:
                logger.warning(f"Expiry differs from expected for {username}. Expected: {new_expire}, Got: {updated_expire}")
                logger.warning(f"Difference: {abs(updated_expire - new_expire)} seconds")

            final_user = get_user_config(username)
            if final_user.get("status") != "active" or final_user.get("expire", 0) == 0:
                logger.error(f"Final verification failed for {username}. Status: {final_user.get('status')}, Expire: {final_user.get('expire')}")
                return {"error": "Failed to properly update user subscription"}

            logger.info(f"Successfully extended subscription for {username}. New expiry: {final_user.get('expire')} "
                       f"({datetime.fromtimestamp(final_user.get('expire')).strftime('%Y-%m-%d %H:%M:%S')})")
            return final_user
        except requests.exceptions.RequestException as e:
            retry_count += 1
            logger.warning(f"API request error in extend_subscription for {username} (attempt {retry_count}/{max_retries}): {e}")
            logger.warning(f"Response content: {getattr(e.response, 'content', 'No response content')}")
            if retry_count >= max_retries:
                logger.error(f"API request failed after {max_retries} attempts for {username}: {e}", exc_info=True)
                return {"error": f"API request failed after {max_retries} attempts: {str(e)}"}
            logger.info(f"Waiting 2 seconds before retry {retry_count+1}/{max_retries}")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error in extend_subscription for {username}: {e}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}

    return {"error": f"Failed to extend subscription for {username} after {max_retries} attempts"}

def disable_expired_user(username):
    """Disable a user's VPN account."""
    try:
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/user/{username}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "status": "disabled",
            "expire": 0
        }
        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Successfully disabled user {username}")
        return response.json()
    except Exception as e:
        logger.error(f"Error disabling user {username}: {e}")
        return {"error": str(e)}

def force_activate_user(username):
    """Force activate a user's account regardless of previous state."""
    logger.info(f"Attempting to force activate user {username}")
    try:
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/user/{username}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "status": "active"
        }
        logger.info(f"Sending force activation request for {username}")
        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Force activation successful for {username}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error during force activation for {username}: {e}", exc_info=True)
        return {"error": str(e)}

def create_user(username):
    """Create a new VPN user account."""
    try:
        token = get_marzban_token()
        url = f"{MARZBAN_URL}/api/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        expire_date = datetime.now() + timedelta(days=7)
        expire_timestamp = int(expire_date.timestamp())
        data = {
            "username": str(username),
            "proxies": {
                "vless": {}
            },
            "inbounds": {
                "vless": ["VLESS TCP REALITY"]
            },
            "expire": expire_timestamp,
            "data_limit": 0,
            "status": "active"
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Successfully created user {username}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating user {username}: {e}")
        logger.error(f"Response content: {getattr(e.response, 'content', 'No response content')}")
        raise Exception(f"Failed to create user: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating user {username}: {e}")
        raise Exception(f"Unexpected error: {str(e)}")

@bot.message_handler(commands=['start'])
def start(message):
    log_user_interaction(
        message.from_user.id,
        message.from_user.username,
        "COMMAND_START",
        f"first_name: {message.from_user.first_name}"
    )
    
    existing_config = get_user_config(str(message.from_user.id))
    is_new_user = "error" in existing_config and "User not found" in existing_config.get("error", "")

    referral_added = False
    if len(message.text.split()) > 1 and is_new_user:
        referral_code = message.text.split()[1]
        referrer_id = decode_referral_code(referral_code)
        if referrer_id and referrer_id != str(message.from_user.id):
            if add_referral(referrer_id, str(message.from_user.id)):
                referral_added = True
                try:
                    bot.send_message(
                        referrer_id,
                        f"🎉 Новый пользователь присоединился по вашей реферальной ссылке!\n"
                        f"Когда он оплатит подписку, вы получите 15 дней бесплатно!"
                    )
                except Exception:
                    pass
    elif len(message.text.split()) > 1 and not is_new_user:
        logger.info(f"Referral link used by existing user {message.from_user.id}, not counting")

    permanent_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_button = types.KeyboardButton('Главное меню')
    help_button = types.KeyboardButton('Помощь')
    permanent_keyboard.add(start_button, help_button)

    inline_markup = types.InlineKeyboardMarkup()
    subscribe_button = types.InlineKeyboardButton('📢 Подписаться на канал', url=CHANNEL_LINK)
    get_config_button = types.InlineKeyboardButton('🔑 Получить конфигурацию', callback_data='get_config')
    auto_config_button = types.InlineKeyboardButton('⚙️ Авто-настройка', callback_data='auto_config')
    select_device_button = types.InlineKeyboardButton('📱 Скачать приложение', callback_data='select_device')
    payment_button = types.InlineKeyboardButton('💳 Оплатить подписку', callback_data='payment')
    check_days_button = types.InlineKeyboardButton('⏳ Проверить остаток дней', callback_data='check_days')
    referral_button = types.InlineKeyboardButton('👥 Реферальная программа', callback_data='referral')
    help_button_inline = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    inline_markup.add(subscribe_button)
    inline_markup.add(get_config_button)
    inline_markup.add(auto_config_button)
    inline_markup.add(select_device_button)
    inline_markup.add(payment_button)
    inline_markup.add(check_days_button)
    inline_markup.add(referral_button)
    inline_markup.add(help_button_inline)

    welcome_text = ("🌟 _Добро пожаловать в VPN бот!_\n\n"
                   "🎁 7 дней для новых пользователей _бесплатно_\n"
                   "💰 Далее всего 99₽ в месяц\n"
                   "🚀 Безлимитный трафик\n"
                   "🔒 Надежная защита\n"
                   "⚡️Высокая скорость без перебоев\n"
                   "⚙️ Техническая поддержка пользователей\n\n"
                   "Мы с командой стараемся создать для вас лучший пользовательский опыт🤝\n\n"
                   "Спасибо , что выбираете нас !💖")

    if referral_added:
        welcome_text += "\n\n🎉 _Вы присоединились по реферальной ссылке!_"

    bot.send_message(message.chat.id,
                     welcome_text,
                     reply_markup=permanent_keyboard,
                     parse_mode='Markdown')

    bot.send_message(message.chat.id,
                     "📝 _Для начала использования VPN:_\n\n"
                     "1️⃣ Подпишитесь на канал\n"
                     "2️⃣ Нажмите 'Получить конфигурацию'\n\n"
                     "⚠️ _Важно:_ не отписывайтесь от канала, иначе ключ доступа будет удален.",
                     reply_markup=inline_markup,
                     parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "Главное меню")
def main_menu(message):
    log_user_interaction(
        message.from_user.id,
        message.from_user.username,
        "BUTTON_MAIN_MENU"
    )
    start(message)

@bot.message_handler(func=lambda message: message.text == "Помощь")
def help_menu(message):
    log_user_interaction(
        message.from_user.id,
        message.from_user.username,
        "BUTTON_HELP"
    )
    markup = types.InlineKeyboardMarkup()
    video_instruction_button = types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_instruction')
    vpn_not_working_button = types.InlineKeyboardButton('🚫 Не работает VPN?', callback_data='vpn_not_working')
    contact_us_button = types.InlineKeyboardButton('📞 Связаться с нами', url='https://t.me/lekivpn?direct')
    close_button = types.InlineKeyboardButton('❌ Закрыть', callback_data='close')
    markup.add(video_instruction_button)
    markup.add(vpn_not_working_button)
    markup.add(contact_us_button)
    markup.add(close_button)
    bot.send_message(message.chat.id,
                     "❓*Помощь*",
                     reply_markup=markup,
                     parse_mode='Markdown')

def check_subscription_status():
    """Thread function to check if users are still subscribed to the channel."""
    while True:
        try:
            token = get_marzban_token()
            url = f"{MARZBAN_URL}/api/users"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            users = response.json()["users"]

            for user in users:
                if user["status"] == "active":
                    try:
                        if user["username"].isdigit():
                            user_id = int(user["username"])
                            user_status = bot.get_chat_member(CHANNEL_ID, user_id)
                            if user_status.status not in ['member', 'administrator', 'creator']:
                                logger.info(f"User {user_id} unsubscribed from channel, disabling account")
                                result = disable_expired_user(user["username"])
                                if "error" not in result:
                                    try:
                                        bot.send_message(user_id,
                                                        "❌ Ваш VPN аккаунт деактивирован, так как вы отписались от канала. "
                                                        "Для восстановления доступа подпишитесь на канал и получите новую конфигурацию.")
                                    except Exception as msg_e:
                                        logger.error(f"Could not send notification to user {user_id}: {msg_e}")
                    except Exception as e:
                        logger.error(f"Error checking subscription for user {user['username']}: {e}")
        except Exception as e:
            logger.error(f"Subscription check error: {e}")
        time.sleep(3600)

def check_subscriptions():
    """Thread function to check subscription expiry and send notifications."""
    while True:
        try:
            current_time = int(time.time())
            token = get_marzban_token()
            url = f"{MARZBAN_URL}/api/users"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            users = response.json()["users"]

            for user in users:
                user_id = user["username"]
                if not user_id.isdigit():
                    continue

                if user["status"] == "expired":
                    logger.info(f"Processing expired user: {user_id}")
                    result = disable_expired_user(user_id)
                    if "error" not in result and not notification_store.is_notified(f"expired_{user_id}"):
                        try:
                            bot.send_message(user_id,
                                "❌ Ваша VPN подписка истекла. Аккаунт деактивирован. Для продления напишите в чате /start, нажмите кнопку 'Главное меню -> Оплатить подписку'")
                            notification_store.set_notified(f"expired_{user_id}")
                            logger.info(f"Sent expiration notification to user {user_id}")
                        except Exception as e:
                            logger.error(f"Error sending message to user {user_id}: {e}")
                elif user["status"] == "active" and "expire" in user and user["expire"] is not None:
                    time_to_expire = user["expire"] - current_time
                    if 85400 < time_to_expire <= 172800 and not notification_store.is_notified(f"warning_48h_{user_id}"):
                        try:
                            bot.send_message(user_id,
                                "⚠️ Ваша VPN подписка истекает через 2 дня! Для продления напишите в чате /start, нажмите кнопку 'Главное меню -> Оплатить подписку'")
                            notification_store.set_notified(f"warning_48h_{user_id}")
                            logger.info(f"Sent 48h warning to user {user_id}")
                        except Exception as e:
                            logger.error(f"Error sending 48h warning to user {user_id}: {e}")
                    elif 64800 < time_to_expire <= 86400 and not notification_store.is_notified(f"warning_24h_{user_id}"):
                        try:
                            bot.send_message(user_id,
                                "⚠️ Ваша VPN подписка истекает завтра! Для продления напишите в чате /start, нажмите кнопку 'Главное меню -> Оплатить подписку'")
                            notification_store.set_notified(f"warning_24h_{user_id}")
                            logger.info(f"Sent 24h warning to user {user_id}")
                        except Exception as e:
                            logger.error(f"Error sending 24h warning to user {user_id}: {e}")
                    elif time_to_expire > 172800:
                        notification_store.reset_notification(f"warning_48h_{user_id}")
                        notification_store.reset_notification(f"warning_24h_{user_id}")
                        notification_store.reset_notification(f"expired_{user_id}")
        except Exception as e:
            logger.error(f"Subscription check error: {e}")
        time.sleep(3600)

def create_app_buttons(device):
    """Create buttons for app download links based on device type."""
    markup = types.InlineKeyboardMarkup()
    if device == 'ios':
        apps = {
            'v2RayTun': 'https://apps.apple.com/kz/app/v2raytun/id6476628951'
        }
        markup.add(types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_phone'))
    elif device == 'android':
        apps = {
            'v2RayTun': 'https://play.google.com/store/apps/details?id=com.v2raytun.android&hl=en',
            'Hiddify': 'https://play.google.com/store/apps/details?id=app.hiddify.com&hl=en'
        }
        markup.add(types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_phone'))
    elif device == 'windows':
        apps = {
            'V2raytun': 'https://v2raytun.com',
            'InvisibleManXRay': 'https://github.com/InvisibleManVPN/InvisibleMan-XRayClient/releases/download/v3.2.5/InvisibleManXRay-x64.zip'
        }
        markup.add(types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_windows'))
    elif device == 'macos':
        apps = {
            'Hiddify-Next': 'https://github.com/hiddify/hiddify-next/releases',
        }
    elif device == 'androidtv':
        apps = {
            'v2RayTun': 'https://play.google.com/store/apps/details?id=com.v2ray.v2raytun',
            'Hiddify-Next': 'https://play.google.com/store/apps/details?id=app.hiddify.com'
        }

    for app_name, app_url in apps.items():
        markup.add(types.InlineKeyboardButton(app_name, url=app_url))
    markup.add(types.InlineKeyboardButton('❌ Закрыть', callback_data='close'))
    return markup

def generate_auto_config_link(user_id, app_name):
    """Generate auto-configuration link for the specified app."""
    try:
        # Get user config
        user_config = get_user_config(str(user_id))
        if "error" in user_config:
            return None
        
        subscription_path = user_config.get("subscription_url")
        if not subscription_path:
            return None
        
        # Create subscription link
        subscription_url = f"{MARZBAN_URL}{subscription_path}"
        
        # Generate redirect URL based on app
        if app_name.lower() == "v2raytun":
            return f"http://77.110.103.189:80/redirect-v2raytun?url={subscription_url}"
        elif app_name.lower() == "hiddify":
            return f"http://77.110.103.189:80/redirect-hiddify?url={subscription_url}"
        
        return None
    except Exception as e:
        logger.error(f"Error generating auto-config link: {e}")
        return None
@bot.callback_query_handler(func=lambda call: True) 
def callback_handler(call):
    log_user_interaction(
        call.from_user.id,
        call.from_user.username,
        f"CALLBACK_{call.data.upper()}",
        f"from_message_id: {call.message.message_id}"
    )
    
    """Handle callback queries from inline buttons."""
    try:
        if call.data == 'auto_config':
            markup = types.InlineKeyboardMarkup()
            android_button = types.InlineKeyboardButton('📱 Android', callback_data='auto_android')
            iphone_button = types.InlineKeyboardButton('📱 iPhone', callback_data='auto_iphone')
            back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_menu')
            
            markup.add(android_button, iphone_button)
            markup.add(back_button)
            
            bot.edit_message_text(
                "⚙️ Выберите платформу для авто-настройки:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            
        elif call.data == 'auto_android':
            markup = types.InlineKeyboardMarkup()
            hiddify_button = types.InlineKeyboardButton('📱 Hiddify', callback_data='auto_hiddify')
            v2raytun_button = types.InlineKeyboardButton('📱 v2raytun', callback_data='auto_v2raytun_android')
            back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='auto_config')
            
            markup.add(hiddify_button)
            markup.add(v2raytun_button)
            markup.add(back_button)
            
            bot.edit_message_text(
                "📱 Выберите приложение для Android:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            
        elif call.data == 'auto_iphone':
            markup = types.InlineKeyboardMarkup()
            v2raytun_button = types.InlineKeyboardButton('📱 v2raytun', callback_data='auto_v2raytun_ios')
            back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='auto_config')
            
            markup.add(v2raytun_button)
            markup.add(back_button)
            
            bot.edit_message_text(
                "📱 Приложение для iPhone:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            
        elif call.data in ['auto_hiddify', 'auto_v2raytun_android', 'auto_v2raytun_ios']:
            # Extract app name from callback data
            if call.data == 'auto_hiddify':
                app_name = 'hiddify'
            elif 'v2raytun' in call.data:
                app_name = 'v2raytun'
            else:
                app_name = 'v2raytun'
            
            # Generate auto-config link
            auto_link = generate_auto_config_link(call.from_user.id, app_name)
            
            if auto_link:
                markup = types.InlineKeyboardMarkup()
                auto_button = types.InlineKeyboardButton('⚡ Автоматическая настройка', url=auto_link)
                back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='auto_config')
                
                markup.add(auto_button)
                markup.add(back_button)
                
                bot.edit_message_text(
                    f"⚡ Автоматическая настройка для {app_name.capitalize()}\n\n"
                    f"Нажмите кнопку ниже для автоматической настройки приложения.\n"
                    f"Ссылка откроет приложение и автоматически добавит конфигурацию.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    "❌ Не удалось создать ссылку для автонастройки. Сначала получите конфигурацию.",
                    show_alert=True
                )
        
        elif call.data == 'select_device':
            markup = types.InlineKeyboardMarkup()
            devices = [
                ('📱 iPhone', 'ios'),
                ('📱 Android', 'android'),
                ('💻 Windows', 'windows'),
                ('💻 MacOS', 'macos'),
                ('📺 AndroidTV', 'androidtv')
            ]
            for device_name, callback_data in devices:
                markup.add(types.InlineKeyboardButton(device_name, callback_data=callback_data))
            markup.add(types.InlineKeyboardButton('❌ Закрыть', callback_data='close'))
            bot.send_message(call.message.chat.id,
                            "🔽 Выберите ваше устройство:",
                            reply_markup=markup)
        elif call.data in ['ios', 'android', 'windows', 'macos', 'androidtv']:
            log_user_interaction(
                call.from_user.id,
                call.from_user.username,
                f"DEVICE_SELECTED_{call.data.upper()}"
            )
            markup = create_app_buttons(call.data)
            bot.edit_message_text("📲 Выберите приложение для установки:",
                                call.message.chat.id,
                                call.message.message_id,
                                reply_markup=markup)
        elif call.data == 'close':
            bot.delete_message(call.message.chat.id, call.message.message_id)
        elif call.data == 'back_to_menu':
            inline_markup = types.InlineKeyboardMarkup()
            subscribe_button = types.InlineKeyboardButton('📢 Подписаться на канал', url=CHANNEL_LINK)
            get_config_button = types.InlineKeyboardButton('🔑 Получить конфигурацию', callback_data='get_config')
            auto_config_button = types.InlineKeyboardButton('⚙️ Авто-настройка', callback_data='auto_config')
            select_device_button = types.InlineKeyboardButton('📱 Скачать приложение', callback_data='select_device')
            payment_button = types.InlineKeyboardButton('💳 Оплатить подписку', callback_data='payment')
            check_days_button = types.InlineKeyboardButton('⏳ Проверить остаток дней', callback_data='check_days')
            referral_button = types.InlineKeyboardButton('👥 Реферальная программа', callback_data='referral')
            help_button_inline = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
            inline_markup.add(subscribe_button)
            inline_markup.add(get_config_button)
            inline_markup.add(auto_config_button)
            inline_markup.add(select_device_button)
            inline_markup.add(payment_button)
            inline_markup.add(check_days_button)
            inline_markup.add(referral_button)
            inline_markup.add(help_button_inline)
            bot.edit_message_text(
                "📝 _Для начала использования VPN:_\n\n"
                "1️⃣ Подпишитесь на канал\n"
                "2️⃣ Нажмите 'Получить конфигурацию'\n\n"
                "⚠️ _Важно:_ не отписывайтесь от канала, иначе ключ доступа будет удален.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=inline_markup,
                parse_mode='Markdown'
            )
        elif call.data == 'referral':
            try:
                total_refs, paid_refs = get_referral_stats(str(call.from_user.id))
                referral_link = generate_referral_link(call.from_user.id)
                markup = types.InlineKeyboardMarkup()
                share_button = types.InlineKeyboardButton('📤 Поделиться ссылкой', url=f"https://t.me/share/url?url={referral_link}")
                back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_menu')
                markup.add(share_button)
                markup.add(back_button)
                message_text = (
                    f"👥 _Реферальная программа_\n\n"
                    f"📊 Ваша статистика:\n"
                    f"• Всего приглашено: {total_refs}\n"
                    f"• Оплатили подписку: {paid_refs}\n\n"
                    f"🎁 _Награды:_\n"
                    f"• За каждого оплатившего друга 👥 = +15 дней бесплатно\n"
                    f"• Достиг 10 оплативших друзей? 👥👥 = +6 месяцев бесплатно\n"
                    f"• Достиг 20 оплативших друзей? 👥👥👥 = +2 года бесплатно\n\n"
                    f"🔗 Ваша реферальная ссылка:\n`{referral_link}`"
                )
                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error in referral handler: {e}")
                bot.answer_callback_query(call.id, "❌ Ошибка при загрузке реферальной программы", show_alert=True)
        elif call.data == 'payment':
            log_user_interaction(
                call.from_user.id,
                call.from_user.username,
                "PAYMENT_INITIATED"
            )
            markup = types.InlineKeyboardMarkup()
            try:
                existing_config = get_user_config(str(call.from_user.id))
                if "error" in existing_config and "User not found" in existing_config["error"]:
                    try:
                        logger.info(f"User {call.from_user.id} not found. Creating new user before payment")
                        vpn_account = create_user(str(call.from_user.id))
                        track_referral_user_creation(str(call.from_user.id))
                        logger.info(f"User {call.from_user.id} created successfully before payment")
                    except Exception as create_e:
                        logger.error(f"Error creating user {call.from_user.id} before payment: {create_e}")
                        bot.answer_callback_query(
                            call.id,
                            f"❌ Ошибка создания аккаунта: {str(create_e)[:50]}... Попробуйте позже."
                        )
                        return

                # Create payment buttons for different subscription periods
                payment_1m = create_payment(call.from_user.id, "99.00")
                pay_1m_button = types.InlineKeyboardButton(
                    '💳 1 месяц - 99₽',
                    url=payment_1m["confirmation_url"]
                )

                payment_3m = create_payment(call.from_user.id, "199.00")
                pay_3m_button = types.InlineKeyboardButton(
                    '💳 3 месяца - 199₽',
                    url=payment_3m["confirmation_url"]
                )

                payment_6m = create_payment(call.from_user.id, "399.00")
                pay_6m_button = types.InlineKeyboardButton(
                    '💳 6 месяцев - 399₽',
                    url=payment_6m["confirmation_url"]
                )

                payment_12m = create_payment(call.from_user.id, "699.00")
                pay_12m_button = types.InlineKeyboardButton(
                    '💳 12 месяцев - 699₽',
                    url=payment_12m["confirmation_url"]
                )

                eternal_payment = create_payment(call.from_user.id, "990.00")
                eternal_pay_button = types.InlineKeyboardButton(
                    '💫 Вечная подписка - 990₽',
                    url=eternal_payment["confirmation_url"]
                )

                back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_menu')
                markup.add(pay_1m_button)
                markup.add(pay_3m_button)
                markup.add(pay_6m_button)
                markup.add(pay_12m_button)
                #markup.add(eternal_pay_button)
                markup.add(back_button)

                message_text = (
                    "💫 _VPN подписка_\n\n"
                    "💰 1 месяц: 99 ₽\n"
                    "💰 3 месяца: 199 ₽\n"
                    "💰 6 месяцев: 399 ₽\n"
                    "💰 12 месяцев: 699 ₽\n\n"
                    "✨ Включено:\n"
                    "   • Безлимитный трафик\n"
                    "   • Высокая скорость\n"
                    "   • Поддержка 24/7\n"
                    "   • Работает на всех устройствах\n\n"
                    "🔒 Безопасная оплата через ЮKassa"
                )
                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error creating payment for user {call.from_user.id}: {e}")
                bot.answer_callback_query(
                    call.id,
                    f"❌ Произошла ошибка при создании платежа: {str(e)[:50]}... Попробуйте позже."
                )
        elif call.data == 'check_days':
            try:
                user_config = get_user_config(str(call.from_user.id))
                if "error" in user_config:
                    bot.answer_callback_query(call.id, f"❌ Ошибка: {user_config['error']}", show_alert=True)
                    return

                if "username" in user_config:
                    current_time = int(time.time())
                    expire_time = user_config.get("expire")
                    account_active = user_config.get("status") != "disabled"

                    if (expire_time is None or expire_time == 0) and account_active:
                        bot.answer_callback_query(call.id, "✅ У Вас вечная подписка", show_alert=True)
                    elif expire_time is None or expire_time == 0:
                        bot.answer_callback_query(call.id, "❌ Подписка не активна", show_alert=True)
                    else:
                        days_left = (expire_time - current_time) // (24 * 3600)
                        hours_left = ((expire_time - current_time) % (24 * 3600)) // 3600
                        if days_left > 0:
                            status_text = f"✅ У вас осталось {days_left} дней и {hours_left} часов подписки"
                        elif hours_left > 0:
                            status_text = f"⚠️ У вас осталось всего {hours_left} часов подписки"
                        else:
                            status_text = "❌ Ваша подписка истекла"
                        bot.answer_callback_query(call.id, status_text, show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ У вас нет активной подписки", show_alert=True)
            except Exception as e:
                logger.error(f"Error checking subscription days for user {call.from_user.id}: {e}")
                bot.answer_callback_query(call.id, f"❌ Ошибка при проверке подписки: {str(e)[:50]}", show_alert=True)
        elif call.data == 'check_sub':
            try:
                user_status = bot.get_chat_member(CHANNEL_ID, call.from_user.id)
                status_text = ""
                if user_status.status in ['member', 'administrator', 'creator']:
                    existing_config = get_user_config(str(call.from_user.id))
                    if "error" in existing_config:
                        status_text = "✅ Вы подписаны на группу. Теперь вы можете получить VPN, нажав кнопку 'Получить конфигурацию'"
                    elif "username" in existing_config and existing_config.get("status") == "disabled":
                        token = get_marzban_token()
                        url = f"{MARZBAN_URL}/api/user/{call.from_user.id}"
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        }
                        data = {
                            "status": "active"
                        }
                        response = requests.put(url, headers=headers, json=data)
                        if response.status_code == 200:
                            status_text = "✅ Ваш аккаунт успешно активирован! Нажмите 'Получить конфигурацию' для получения данных VPN"
                        else:
                            status_text = f"❌ Ошибка при активации аккаунта. Код: {response.status_code}"
                    else:
                        status_text = "✅ Вы подписаны на группу. Теперь вы можете получить VPN, нажав кнопку 'Получить конфигурацию'"
                else:
                    status_text = "❌ Вы не подписаны на группу. Пожалуйста, подпишитесь для получения VPN"
                bot.answer_callback_query(call.id, status_text)
                if user_status.status in ['member', 'administrator', 'creator']:
                    bot.send_message(call.message.chat.id, status_text)
            except Exception as e:
                logger.error(f"Error checking subscription for user {call.from_user.id}: {e}")
                bot.send_message(call.message.chat.id, f"❌ Произошла ошибка: {str(e)[:100]}")
        elif call.data == 'get_config':
            log_user_interaction(
                call.from_user.id,
                call.from_user.username,
                "CONFIG_REQUESTED"
            )
            try:
                user_status = bot.get_chat_member(CHANNEL_ID, call.from_user.id)
                if user_status.status in ['member', 'administrator', 'creator']:
                    existing_config = get_user_config(str(call.from_user.id))
                    
                    if "error" in existing_config and "User not found" in existing_config["error"]:
                        try:
                            vpn_account = create_user(str(call.from_user.id))
                            track_referral_user_creation(str(call.from_user.id))
                            if "subscription_url" in vpn_account:
                                subscription_path = vpn_account["subscription_url"]
                                # Create full URL by combining base URL with the subscription path
                                subscription_link = f"{MARZBAN_URL}{subscription_path}"
                                markup = types.InlineKeyboardMarkup()
                                download_app_button = types.InlineKeyboardButton('📲 Скачать приложение', callback_data='select_device')
                                video_instruction_button = types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_instruction')
                                markup.add(download_app_button)
                                markup.add(video_instruction_button)
                                response1 = (
                                    "✅ VPN аккаунт создан!\n\n"
                                    "ℹ️ Срок действия: 7 дней\n"
                                    "⚠️ За день до истечения срока вы получите уведомление\n\n"
                                    "1. Скачайте приложение\n"
                                    "2. Скопируйте представленную ниже конфигурацию в приложение"
                                )
                                bot.send_message(call.message.chat.id, response1, reply_markup=markup)
                                bot.send_message(call.message.chat.id, subscription_link)
                            else:
                                bot.send_message(call.message.chat.id, "❌ Ошибка создания аккаунта. Ответ API не содержит ссылок.")
                        except Exception as create_e:
                            logger.error(f"Error creating user {call.from_user.id}: {create_e}")
                            bot.send_message(call.message.chat.id, f"❌ Ошибка создания аккаунта: {str(create_e)[:100]}. Попробуйте позже")
                    elif "error" in existing_config:
                        bot.send_message(call.message.chat.id, f"❌ Ошибка получения конфигурации: {existing_config['error']}")
                        return
                    elif "username" in existing_config and existing_config.get("status") == "disabled":
                        bot.send_message(call.message.chat.id,
                            "❌ Ваша VPN подписка истекла. Аккаунт деактивирован. Для продления напишите в чате /start, нажмите кнопку 'Главное меню -> Оплатить подписку'")
                    elif "username" in existing_config and existing_config.get("status") == "active":
                        subscription_path = existing_config["subscription_url"]
                        # Create full URL by combining base URL with the subscription path
                        subscription_link = f"{MARZBAN_URL}{subscription_path}"
                        markup = types.InlineKeyboardMarkup()
                        download_app_button = types.InlineKeyboardButton('📲 Скачать приложение', callback_data='select_device')
                        video_instruction_button = types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_instruction')
                        markup.add(download_app_button)
                        markup.add(video_instruction_button)
                        response1 = (
                            "✅ Инструкция по подключению\n\n"
                            "1. Скачайте приложение\n"
                            "2. Скопируйте представленную ниже конфигурацию в приложение"
                        )
                        bot.send_message(call.message.chat.id, response1, reply_markup=markup)
                        bot.send_message(call.message.chat.id, subscription_link)
                else:
                    bot.answer_callback_query(call.id, "❌ Вы не подписаны на группу. Пожалуйста, подпишитесь для получения VPN")
            except Exception as e:
                logger.error(f"Error in get_config for user {call.from_user.id}: {e}")
                bot.send_message(call.message.chat.id, f"❌ Произошла ошибка: {str(e)[:100]}")
        elif call.data == 'video_instruction':
            markup = types.InlineKeyboardMarkup()
            phone_button = types.InlineKeyboardButton('📱 Телефон', callback_data='video_phone')
            windows_button = types.InlineKeyboardButton('💻 Windows', callback_data='video_windows')
            close_button = types.InlineKeyboardButton('❌ Закрыть', callback_data='close')
            markup.add(phone_button, windows_button)
            markup.add(close_button)
            bot.edit_message_text(
                "🎥 Выберите устройство для видео инструкции:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        elif call.data == 'video_phone':
            try:
                with open('android_tutorial.mp4', 'rb') as video:
                    bot.send_video(call.message.chat.id, video)
            except Exception as e:
                logger.error(f"Error sending android video instruction: {e}")
                bot.send_message(call.message.chat.id, "❌ Видео инструкция для телефона не найдена.")
        elif call.data == 'video_windows':
            try:
                with open('windows_tutorial.mp4', 'rb') as video:
                    bot.send_video(call.message.chat.id, video)
            except Exception as e:
                logger.error(f"Error sending windows video instruction: {e}")
                bot.send_message(call.message.chat.id, "❌ Видео инструкция для Windows не найдена.")
        elif call.data == 'vpn_not_working':
            markup = types.InlineKeyboardMarkup()
            contact_us_button = types.InlineKeyboardButton('📞 Связаться с нами', url='https://t.me/lekivpn?direct')
            close_button = types.InlineKeyboardButton('❌ Закрыть', callback_data='close')
            markup.add(contact_us_button)
            markup.add(close_button)
            troubleshooting_text = (
                "🚀 Решение типичных проблем в L-VPN!\n"
                "Если VPN не подключается или работает нестабильно, попробуй эти простые шаги. Часто это решает вопрос! 🔧\n\n"
                "📜 Шаги по устранению неисправностей:\n"
                "🔄 Перезапусти приложение: Полностью закрой наше VPN-приложение (свайпни вверх или через настройки), затем открой заново.\n"
                "✈️ Включи/выключи авиарежим: Активируй авиарежим на 10-15 секунд, затем выключи. Это обновит соединение.\n"
                "🔄 Комбинируй шаги: Сделай перезапуск + авиарежим для лучшего эффекта.\n\n"
                "Если проблема осталась, напиши в поддержку с описанием! 🌟"
            )
            bot.edit_message_text(
                troubleshooting_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        elif call.data == 'help':
            markup = types.InlineKeyboardMarkup()
            video_instruction_button = types.InlineKeyboardButton('🎥 Видео инструкция', callback_data='video_instruction')
            vpn_not_working_button = types.InlineKeyboardButton('🚫 Не работает VPN?', callback_data='vpn_not_working')
            contact_us_button = types.InlineKeyboardButton('📞 Связаться с нами', url='https://t.me/lekivpn?direct')
            markup.add(video_instruction_button)
            markup.add(vpn_not_working_button)
            markup.add(contact_us_button)
            bot.send_message(call.message.chat.id,
                             "❓*Помощь*",
                             reply_markup=markup,
                             parse_mode='Markdown')
        elif call.data == 'payment_services':
            markup = types.InlineKeyboardMarkup()
            services = [
                ('Booking', "Добрый день, хочу оплатить подписку Booking"),
                ('Airbnb', "Добрый день, хочу оплатить подписку Airbnb"),
                ('ChatGPT', "Добрый день, хочу оплатить подписку ChatGPT"),
                ('Youtube Premium', "Добрый день, хочу оплатить подписку Youtube Premium"),
                ('Steam', "Добрый день, хочу оплатить подписку Steam"),
                ('PlayStation Plus', "Добрый день, хочу оплатить подписку PlayStation Plus"),
                ('Netflix', "Добрый день, хочу оплатить подписку Netflix"),
                ('Adobe', "Добрый день, хочу оплатить подписку Adobe"),
                ('Windows', "Добрый день, хочу оплатить подписку Windows"),
                ('PUBG Mobile', "Добрый день, хочу оплатить подписку PUBG Mobile"),
                ('Другое', "Добрый день, хочу оплатить подписку на зарубежный сервис ")
            ]
            for service_name, message_text in services:
                button = types.InlineKeyboardButton(
                    service_name,
                    url=f'https://t.me/vpnoblako?text={requests.utils.quote(message_text)}'
                )
                markup.add(button)
            back_button = types.InlineKeyboardButton('◀️ Назад', callback_data='back_to_menu')
            markup.add(back_button)
            bot.edit_message_text(
                "💳 _Оплата подписок на зарубежные сервисы_",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        log_user_interaction(
            call.from_user.id,
            call.from_user.username,
            f"ERROR_IN_CALLBACK_{call.data.upper()}",
            f"error: {str(e)[:100]}"
        )
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        try:
            bot.answer_callback_query(
                call.id,
                "❌ Произошла ошибка при обработке запроса. Попробуйте позже.",
                show_alert=True
            )
        except Exception:
            pass

# Start subscription checkers in separate threads
setup_payment_tracker()
setup_referral_database()
subscription_checker = threading.Thread(target=check_subscription_status)
subscription_checker.daemon = True
subscription_checker.start()
expiry_checker = threading.Thread(target=check_subscriptions)
expiry_checker.daemon = True
expiry_checker.start()

setup_yookassa_webhook()
payment_checker_thread = threading.Thread(target=check_unprocessed_payments)
payment_checker_thread.daemon = True
payment_checker_thread.start()

logger.info("Starting the bot...")
bot.polling(none_stop=True)