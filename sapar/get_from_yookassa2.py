#!/usr/bin/env python3
import sys
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.append('/opt/marzban')
from cred import SHOP_ID, YUKASSA_API
from yookassa import Configuration, Payment

Configuration.account_id = SHOP_ID
Configuration.secret_key = YUKASSA_API

def read_usernames():
    try:
        with open('/root/usernames.txt', 'r') as f:
            usernames = set(line.strip() for line in f if line.strip())
        return usernames
    except FileNotFoundError:
        print("Error: /root/usernames.txt not found")
        return set()

def extract_user_id(description):
    if not description:
        return None
    match = re.search(r'ID:\s*(\d+)', description)
    return match.group(1) if match else None

def get_all_payments_filtered(days_back=30):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    
    all_payments = []
    next_cursor = None

    while True:
        try:
            params = {
                "limit": 100
            }
            if next_cursor:
                params["cursor"] = next_cursor

            response = Payment.list(params)

            for payment in response.items:
                # Parse and make aware
                payment_time = datetime.fromisoformat(payment.created_at.replace("Z", "+00:00"))
                if start_date <= payment_time <= end_date:
                    all_payments.append(payment)

            if hasattr(response, 'next_cursor') and response.next_cursor:
                next_cursor = response.next_cursor
            else:
                break

        except Exception as e:
            print(f"Error fetching payments: {e}")
            break

    return all_payments

def main():
    usernames = read_usernames()

    if not usernames:
        print("No usernames found")
        return

    all_payments = get_all_payments_filtered()
    print(f"Total payments found (in last 30 days): {len(all_payments)}")

    relevant_payments = []
    target_amount = Decimal('50.00')

    for payment in all_payments:
        if payment.status == "succeeded" and payment.amount.value == target_amount:
            user_id = extract_user_id(payment.description)
            if user_id and user_id in usernames:
                relevant_payments.append({
                    'user_id': user_id,
                    'id': payment.id,
                    'amount': payment.amount.value,
                    'created_at': payment.created_at,
                    'description': payment.description
                })

    print(f"Relevant payments: {len(relevant_payments)}")

    user_payments = {}
    for payment in relevant_payments:
        user_id = payment['user_id']
        if user_id not in user_payments:
            user_payments[user_id] = []
        user_payments[user_id].append(payment)

    print(f"\nPayments for {len(user_payments)} users:")
    print("-" * 60)

    total_payments = 0
    total_amount = 0

    for user_id in sorted(user_payments.keys()):
        payments = user_payments[user_id]
        user_total = len(payments)
        user_amount = user_total * 50

        print(f"User {user_id}: {user_total} payments (50r each) = {user_amount}r")
        for payment in payments:
            print(f"    {payment['id']} - {payment['created_at']}")

        total_payments += user_total
        total_amount += user_amount
        print()

    print("-" * 60)
    print(f"TOTAL: {total_payments} payments of 50r = {total_amount}₽")

if __name__ == "__main__":
    main()
