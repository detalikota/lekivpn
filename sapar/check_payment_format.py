#!/usr/bin/env python3

import sys
sys.path.append('/opt/marzban')
from cred import SHOP_ID, YUKASSA_API
from yookassa import Configuration, Payment
import json

# Configure YooKassa
Configuration.account_id = SHOP_ID
Configuration.secret_key = YUKASSA_API

def check_payment_response():
    try:
        # Get recent payments
        response = Payment.list()
        
        print("Response type:", type(response))
        print("Response attributes:", dir(response))
        print("\n" + "="*50)
        
        # Try to access items different ways
        try:
            if hasattr(response, 'items'):
                print("Found 'items' attribute")
                items = response.items
                print(f"Items count: {len(items)}")
            elif hasattr(response, 'data'):
                print("Found 'data' attribute")
                items = response.data
                print(f"Data count: {len(items)}")
            else:
                print("Response is list-like")
                items = response
                print(f"Items count: {len(items)}")
                
            # Show first payment details
            if items and len(items) > 0:
                first_payment = items[0]
                print("\nFirst payment details:")
                print("Type:", type(first_payment))
                print("Attributes:", dir(first_payment))
                print("\nPayment data:")
                print(f"ID: {first_payment.id}")
                print(f"Status: {first_payment.status}")
                print(f"Amount: {first_payment.amount.value}")
                print(f"Description: {first_payment.description}")
                print(f"Created: {first_payment.created_at}")
                
        except Exception as e:
            print(f"Error accessing items: {e}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_payment_response()