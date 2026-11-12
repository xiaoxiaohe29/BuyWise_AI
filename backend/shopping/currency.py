
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.request import urlopen


def convert_to_usd(amount, currency, payment_date):
    """
    Convert a payment amount to USD using the
    historical exchange rate on its payment date.
    """

    amount = Decimal(str(amount))
    currency = currency.upper()

    # No conversion needed for USD payments
    if currency == "USD":
        return amount.quantize(Decimal("0.01"))

    # Get the payment date
    if isinstance(payment_date, str):
        payment_date = date.fromisoformat(payment_date[:10])
    elif hasattr(payment_date, "date"):
        payment_date = payment_date.date()

    # Try payment date and previous days
    # to handle weekends and holidays.
    for days_back in range(8):
        rate_date = payment_date - timedelta(days=days_back)

        query = urlencode({"date": rate_date.isoformat()})
        url = (
            f"https://api.frankfurter.dev/v2/rate/"
            f"{currency}/USD?{query}"
        )

        try:
            with urlopen(url, timeout=10) as response:
                data = json.load(response)

            returned_date = date.fromisoformat(data["date"])

            # Never use a rate after the payment date
            if returned_date > payment_date:
                continue

            rate = Decimal(str(data["rate"]))

            return (amount * rate).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        except Exception:
            continue

    raise ValueError(
        f"Historical exchange rate unavailable for "
        f"{currency}/USD on {payment_date}"
    )
