from yookassa import Configuration, Payment
from yookassa.domain.exceptions import ApiError

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
