
import os
import requests
from dotenv import load_dotenv

load_dotenv()

PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")


def get_paypal_access_token():
    if not all([PAYPAL_BASE_URL, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET]):
        raise ValueError("Missing PayPal credentials in .env")

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=15
    )

    response.raise_for_status()

    return response.json()["access_token"]


def create_paypal_order(amount, currency="USD"):
    token = get_paypal_access_token()

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(__import__("uuid").uuid4())
        },
        json={
            "intent": "CAPTURE",
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "return_url": os.getenv(
                         "APP_BASE_URL",
                                "http://127.0.0.1:8001"
                            ) + "/dashboard",

                            "cancel_url": os.getenv(
                         "APP_BASE_URL",
                                "http://127.0.0.1:8001"
                            ) + "/dashboard"
                    }
                }
            },
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": f"{amount:.2f}"
                    }
                }
            ]
        },
        timeout=15
    )

    def capture_paypal_order(order_id):
        token = get_paypal_access_token()

        response = requests.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": f"capture-{order_id}"
            },
            json={},
            timeout=20
        )

        response.raise_for_status()
        return response.json()

    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    token = get_paypal_access_token()
    print("PayPal Sandbox connection successful!")


def get_paypal_order(order_id):
    token = get_paypal_access_token()

    response = requests.get(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
        timeout=15
    )

    response.raise_for_status()
    return response.json()


def capture_paypal_order(order_id):
    token = get_paypal_access_token()

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"capture-{order_id}"
        },
        json={},
        timeout=20
    )

    response.raise_for_status()
    return response.json()
