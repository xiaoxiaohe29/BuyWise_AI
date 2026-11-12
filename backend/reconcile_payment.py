
from shopping.database import SessionLocal
from shopping import models
from shopping.paypal import get_paypal_order
from decimal import Decimal
from datetime import datetime

def reconcile_payment():
    db = SessionLocal()

    try:
        payment = db.query(models.Payment).filter(
            models.Payment.payment_id == 4,
            models.Payment.order_id == 4
        ).first()

        order = db.get(models.Order, 4)

        if payment is None or order is None:
            print("Payment or order not found")
            return

        if not payment.paypal_order_id:
            print("Missing PayPal order ID")
            return

        if payment.payment_status == "COMPLETED":
            print("Payment already reconciled")
            return

        paypal_order = get_paypal_order(payment.paypal_order_id)

        captures = [
            c
            for unit in paypal_order.get("purchase_units", [])
            for c in unit.get("payments", {}).get("captures", [])
            if c.get("status") == "COMPLETED"
        ]

        if (
            paypal_order.get("id") != payment.paypal_order_id
            or paypal_order.get("status") != "COMPLETED"
            or len(captures) != 1
            or captures[0].get("amount", {}).get("currency_code") != "USD"
            or Decimal(captures[0]["amount"]["value"]) != Decimal("74.87")
        ):
            print("Verification failed. No changes made.")
            return

        capture = captures[0]

        payment.amount = Decimal(capture["amount"]["value"])
        payment.currency = capture["amount"]["currency_code"]
        payment.capture_id = capture["id"]
        payment.payment_status = "COMPLETED"
        payment.paid_at = datetime.fromisoformat(
            capture["create_time"].replace("Z", "+00:00")
        )

        order.order_status = "COMPLETED"

        db.commit()

        print("Payment #4 reconciled successfully!")

    except Exception as error:
        db.rollback()
        print("Error:", repr(error))

    finally:
        db.close()


if __name__ == "__main__":
    reconcile_payment()
