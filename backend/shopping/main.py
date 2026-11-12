from pathlib import Path
import os
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from .paypal import create_paypal_order
from .paypal import get_paypal_order
from .paypal import capture_paypal_order
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from .auth import verify_password, create_access_token
from .schemas import UserLogin, TokenResponse
from .currency import convert_to_usd
from fastapi import Query, HTTPException

from .models import User
from .schemas import UserRegister, UserResponse
from .database import engine, Base, get_db
from . import models
from .schemas import OrderCreate, OrderResponse

load_dotenv()

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key is not configured"
        )

    return OpenAI(api_key=api_key)


# Smart Shopping frontend location
SHOPPING_FRONTEND = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "shopping"
)

app = FastAPI(
    title="Smart Shopping API",
    description="Payment and Purchase Management System",
    version="1.0.0"
)


password_hash = PasswordHash.recommended()


@app.post("/api/register", response_model=UserResponse, status_code=201)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    username = user_data.username.strip()
    email = str(user_data.email).lower()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Username cannot be empty"
        )

    existing_username = db.query(User).filter(
        User.username == username
    ).first()

    if existing_username:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    existing_email = db.query(User).filter(
        User.email == email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    new_user = User(
        username=username,
        email=email,
        password_hash=password_hash.hash(user_data.password)
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists"
        )

    return new_user


@app.post("/api/login", response_model=TokenResponse)
def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    email = str(login_data.email).lower()

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user or not verify_password(
        login_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    access_token = create_access_token(user.user_id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "Welcome to Smart Shopping System",
        "status": "Running"
    }

@app.get("/ai-test")
def test_openai():

    response = get_openai_client().responses.create(
        model="gpt-4.1-mini",
        input="Reply with exactly: OpenAI connection successful."
    )

    return {
        "message": response.output_text
    }

@app.get("/db-status")
def database_status():
    inspector = inspect(engine)

    return {
        "database": "connected",
        "tables": inspector.get_table_names()
    }

import ollama

def categorise_product(product_name, description=None):

    text = f"{product_name} {description or ''}".lower()

    # Step 1: Check specific accessories first
    accessory_keywords = [
        "phone case", "phone cover", "screen protector",
        "laptop sleeve", "phone holder", "charger cable"
    ]

    if any(word in text for word in accessory_keywords):
        return "Accessories"

    # Step 2: Check other categories
    categories = {
        "Electronics": [
            "iphone", "samsung", "phone", "laptop",
            "computer", "tablet", "ipad", "headphone",
            "camera", "smartwatch", "charger"
        ],

        "Accessories": [
            "case", "cover", "cable", "holder",
            "screen protector"
        ],

        "Clothing": [
            "shirt", "dress", "pants", "jeans",
            "shoes", "jacket"
        ],

        "Food & Beverage": [
            "food", "coffee", "tea", "snack",
            "chocolate", "drink"
        ]
    }

    for category, keywords in categories.items():
        if any(word in text for word in keywords):
            return category

    # Step 3: Use Ollama if no keyword matches
    prompt = f"""
    Classify this product into exactly ONE category:
    Electronics, Accessories, Clothing, Food & Beverage, Others.

    Product: {product_name}
    Description: {description or "Not provided"}

    Return ONLY the category name.
    """

    try:
        response = ollama.chat(
            model="llama3.2:1b",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.message.content.strip()

    except (ConnectionError, TimeoutError) as error:
        print(f"Ollama unavailable: {error}")
        return "Others"

    allowed_categories = {
        "Electronics",
        "Accessories",
        "Clothing",
        "Food & Beverage",
        "Others"
    }

    if result in allowed_categories:
        return result

    return "Others"


# Create a new order
@app.post("/api/orders", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db)
):
    total_amount = sum(
        item.unit_price * item.quantity
        for item in order_data.items
    )

    new_order = models.Order(
        user_id=order_data.user_id,
        merchant_name=order_data.merchant_name,
        platform=order_data.platform,
        total_amount=total_amount,
        currency=order_data.currency,
        items=[
            models.OrderItem(
                product_name=item.product_name,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                category=(
                    item.category.strip()
                    if item.category and item.category.strip()
                    else categorise_product(
                        item.product_name,
                        item.description
                    )
                )
            )
            for item in order_data.items
        ]
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


# Get all orders
@app.get("/api/orders", response_model=list[OrderResponse])
def get_orders(db: Session = Depends(get_db)):
    return db.query(models.Order).all()


# Get one order by ID
@app.get("/api/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):

    order = db.query(models.Order).filter(
        models.Order.order_id == order_id
    ).first()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return order


# Convert an order's original amount to USD
@app.get("/api/orders/{order_id}/usd")
def get_order_usd(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).filter(
        models.Order.order_id == order_id
    ).first()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    try:
        from datetime import date

        usd_amount = convert_to_usd(
            order.total_amount,
            order.currency,
            date.today()
        )

        return {
            "order_id": order.order_id,
            "original_currency": order.currency,
            "original_amount": float(order.total_amount),
            "usd_currency": "USD",
            "usd_amount": float(usd_amount),
            "rate_date_requested": date.today().isoformat()
        }

    except Exception as error:
        print("Currency Conversion Error:", repr(error))

        raise HTTPException(
            status_code=502,
            detail="Unable to convert currency to USD"
        )


@app.post("/api/paypal/test-order")
def test_paypal_order():
    try:
        # Create a test payment of USD 1.00
        result = create_paypal_order(1.00, "USD")

        # Find the PayPal approval link
        approval_url = next(
            (
                link["href"]
                for link in result.get("links", [])
                if link.get("rel") in ("approve", "payer-action")
            ),
            None
        )

        if not approval_url:
            raise HTTPException(
                status_code=502,
                detail="PayPal approval URL not found"
            )

        return {
            "paypal_order_id": result["id"],
            "status": result["status"],
            "approval_url": approval_url
        }

    except HTTPException:
        raise

    except Exception as error:
        print("PayPal Test Error:", repr(error))

        if hasattr(error, "response") and error.response is not None:
            print("PayPal Error Details:", error.response.text)

        raise HTTPException(
            status_code=502,
            detail="PayPal Sandbox order creation failed"
        )


@app.get("/api/paypal/order-status/{order_id}")
def paypal_order_status(order_id: str):
    try:
        result = get_paypal_order(order_id)

        return {
            "paypal_order_id": result["id"],
            "status": result["status"]
        }

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve PayPal order status"
        )

@app.post("/api/paypal/capture/{order_id}")
def capture_payment(order_id: str):

    try:
        result = capture_paypal_order(order_id)

        captures = [
            capture
            for unit in result.get("purchase_units", [])
            for payment in [unit.get("payments", {})]
            for capture in payment.get("captures", [])
        ]

        return {
            "paypal_order_id": result["id"],
            "order_status": result["status"],
            "captures": [
                {
                    "capture_id": capture["id"],
                    "status": capture["status"],
                    "amount": capture["amount"]
                }
                for capture in captures
            ]
        }

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="PayPal payment capture failed"
        )



@app.post("/api/orders/{order_id}/paypal")
def start_order_payment(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.get(models.Order, order_id)

    if order is None:
        raise HTTPException(404, "Order not found")

    if order.order_status != "PENDING":
        raise HTTPException(400, "Order is not pending")

    payments = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == order_id)
        .order_by(models.Payment.payment_id.desc())
        .all()
    )

    if any(p.payment_status == "COMPLETED" for p in payments):
        raise HTTPException(
            409,
            "This order has already been paid"
        )

    for payment in payments:
        if not payment.paypal_order_id:
            continue

        try:
            paypal_order = get_paypal_order(
                payment.paypal_order_id
            )
        except Exception:
            raise HTTPException(
                502,
                "Unable to verify existing PayPal payment"
            )

        status = paypal_order.get("status")

        if status == "COMPLETED":
            raise HTTPException(
                409,
                "Existing PayPal payment is completed. "
                "Reconciliation required."
            )

        if status == "APPROVED":
            raise HTTPException(
                409,
                "Payment already approved. "
                "Capture the existing payment first."
            )

        if status in ("CREATED", "PAYER_ACTION_REQUIRED", "SAVED"):
            approval_url = next(
                (
                    link["href"]
                    for link in paypal_order.get("links", [])
                    if link.get("rel") in ("approve", "payer-action")
                ),
                None
            )

            if not approval_url:
                raise HTTPException(
                    409,
                    "Existing checkout has no approval URL"
                )

            return {
                "order_id": order.order_id,
                "paypal_order_id": payment.paypal_order_id,
                "status": status,
                "approval_url": approval_url
            }

        if status != "VOIDED":
            raise HTTPException(
                409,
                f"PayPal status {status} requires review"
            )
    
    try:
        from datetime import date

        # Convert the original order amount to USD
        payment_amount_usd = convert_to_usd(
            order.total_amount,
            order.currency,
            date.today()
        )

        print("Original amount:", order.total_amount, order.currency)
        print("PayPal payment amount:", payment_amount_usd, "USD")

        # Send the converted USD amount to PayPal
        result = create_paypal_order(
            payment_amount_usd,
            "USD"
        )

    except Exception as error:
        print("PayPal Sandbox Error:", repr(error))

        if hasattr(error, "response") and error.response is not None:
            print("PayPal Error Details:", error.response.text)

        raise HTTPException(
            status_code=502,
            detail="PayPal Sandbox order creation failed"
        )


    # Extract approval URL from the new PayPal order
    approval_url = next(
        (
            link.get("href")
            for link in result.get("links", [])
            if link.get("rel") in ("approve", "payer-action")
        ),
        None
    )

    if not approval_url:
        raise HTTPException(
            status_code=502,
            detail="PayPal approval URL missing"
        )


    payment = models.Payment(
        order_id=order.order_id,
        paypal_order_id=result["id"],
        amount=payment_amount_usd,
        currency="USD",
        payment_status="PENDING"
    )

    db.add(payment)
    db.commit()

    return {
        "order_id": order.order_id,
        "paypal_order_id": result["id"],
        "status": result["status"],
        "approval_url": approval_url
    }


@app.post("/api/orders/{order_id}/capture")
def capture_order_payment(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.get(models.Order, order_id)

    if order is None:
        raise HTTPException(404, "Order not found")

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == order_id)
        .order_by(models.Payment.payment_id.desc())
        .first()
    )

    if payment is None:
        raise HTTPException(404, "Payment not found")

    if payment.payment_status == "COMPLETED":
        return {
            "message": "Payment already completed",
            "order_id": order_id
        }

    if not payment.paypal_order_id:
        raise HTTPException(409, "Missing PayPal order ID")

    try:
        # Check whether PayPal has already captured this order
        result = get_paypal_order(payment.paypal_order_id)

        if result.get("status") != "COMPLETED":
            if result.get("status") != "APPROVED":
                raise HTTPException(
                    409,
                    "PayPal payment is not approved"
                )

            # Capture only when PayPal confirms approval
            result = capture_paypal_order(payment.paypal_order_id)

    except HTTPException:
        raise

    except Exception as error:
        print("PayPal Capture Error:", repr(error))
        raise HTTPException(
            502,
            "Unable to verify PayPal payment; check status before retrying"
        )

    captures = [
        capture
        for unit in result.get("purchase_units", [])
        for capture in unit.get("payments", {}).get("captures", [])
    ]

    matching = [
        c for c in captures
        if c.get("status") == "COMPLETED"
        and c.get("amount", {}).get("currency_code") == payment.currency
        and Decimal(c["amount"]["value"]) == Decimal(str(payment.amount))
    ]

    if result.get("status") != "COMPLETED" or len(matching) != 1:
        raise HTTPException(
            409,
            "Payment not verified as completed"
        )

    capture = matching[0]

    payment.capture_id = capture["id"]
    payment.payment_status = "COMPLETED"

    # Use PayPal's actual capture timestamp
    payment.paid_at = datetime.fromisoformat(
        capture["create_time"].replace("Z", "+00:00")
    )

    order.order_status = "COMPLETED"


    # Automatically create a delivery record after payment
    existing_delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.order_id == order_id)
        .first()
    )

    if existing_delivery is None:
        delivery = models.Delivery(
            order_id=order_id,
            courier=None,
            tracking_number=None,
            delivery_method="Standard",
            delivery_status="NOT_SHIPPED"
        )

        db.add(delivery)

    db.commit()

    return {
        "order_id": order_id,
        "order_status": order.order_status,
        "payment_status": payment.payment_status,
        "capture_id": payment.capture_id
    }

# Get all payment records
@app.get("/api/payments")
def get_all_payments(db: Session = Depends(get_db)):

    payments = db.query(models.Payment).all()

    return [
        {
            "payment_id": p.payment_id,
            "order_id": p.order_id,
            "paypal_order_id": p.paypal_order_id,
            "capture_id": p.capture_id,
            "amount": p.amount,
            "currency": p.currency,
            "payment_status": p.payment_status,
            "paid_at": p.paid_at
        }
        for p in payments
    ]



# Get payments belonging to a user (with USD equivalent)
@app.get("/api/users/{user_id}/payments")
def get_user_payments(
    user_id: str,
    db: Session = Depends(get_db)
):

    payments = (
        db.query(models.Payment)
        .join(models.Order)
        .filter(models.Order.user_id == user_id)
        .all()
    )

    results = []

    for p in payments:
        usd_amount = None

        try:
            if p.currency.upper() == "USD":
                usd_amount = p.amount

            elif p.paid_at is not None:
                usd_amount = convert_to_usd(
                    p.amount,
                    p.currency,
                    p.paid_at
                )

        except Exception as error:
            print(
                f"Currency conversion failed for Payment #{p.payment_id}:",
                repr(error)
            )

        results.append({
            "payment_id": p.payment_id,
            "order_id": p.order_id,

            # Original payment information
            "amount": float(p.amount),
            "currency": p.currency,

            # Converted amount
            "usd_amount": (
                float(usd_amount)
                if usd_amount is not None
                else None
            ),

            "payment_status": p.payment_status,
            "paid_at": p.paid_at
        })

    return results



# Get one payment by ID
@app.get("/api/payments/{payment_id}")
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = db.get(models.Payment, payment_id)

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    return {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "paypal_order_id": payment.paypal_order_id,
        "capture_id": payment.capture_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_status": payment.payment_status,
        "paid_at": payment.paid_at
    }


# Expense Summary by User
@app.get("/api/users/{user_id}/expenses/summary")
def get_expense_summary(
    user_id: str,
    db: Session = Depends(get_db)
):
    orders = (
        db.query(models.Order)
        .join(models.Payment)
        .filter(
            models.Order.user_id == user_id,
            models.Order.order_status == "COMPLETED",
            models.Payment.payment_status == "COMPLETED"
        )
        .distinct()
        .all()
    )

    summaries = {}

    for order in orders:
        currency = order.currency

        if currency not in summaries:
            summaries[currency] = {
                "total_spending": Decimal("0.00"),
                "transaction_count": 0,
                "spending_by_category": {}
            }

        summary = summaries[currency]
        summary["total_spending"] += order.total_amount
        summary["transaction_count"] += 1

        for item in order.items:
            category = item.category
            amount = item.unit_price * item.quantity

            if category not in summary["spending_by_category"]:
                summary["spending_by_category"][category] = Decimal("0.00")

            summary["spending_by_category"][category] += amount

    return {
        "user_id": user_id,
        "currencies": {
            currency: {
                "total_spending": str(data["total_spending"]),
                "transaction_count": data["transaction_count"],
                "spending_by_category": {
                    category: str(amount)
                    for category, amount in data["spending_by_category"].items()
                }
            }
            for currency, data in summaries.items()
        }
    }


@app.get("/api/users/{user_id}/expenses/summary-usd")
def get_expense_summary_usd(
    user_id: str,
    db: Session = Depends(get_db)
):
    payments = (
        db.query(models.Payment)
        .join(models.Order)
        .filter(
            models.Order.user_id == user_id,
            models.Order.order_status == "COMPLETED",
            models.Payment.payment_status == "COMPLETED",
            models.Payment.paid_at.isnot(None)
        )
        .all()
    )

    total_usd = Decimal("0.00")
    transaction_count = 0

    for payment in payments:
        try:
            converted_amount = convert_to_usd(
                payment.amount,
                payment.currency,
                payment.paid_at
            )
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Exchange rate unavailable for "
                    f"payment {payment.payment_id}: {error}"
                )
            )

        total_usd += converted_amount
        transaction_count += 1

    return {
        "user_id": user_id,
        "currency": "USD",
        "total_spending": str(total_usd),
        "transaction_count": transaction_count
    }


# Spending by Category Converted to USD
@app.get("/api/users/{user_id}/expenses/categories-usd")
def get_expense_categories_usd(
    user_id: str,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db)
):
    
    # Prevent users from selecting future months
    if month is not None:
        current_month = datetime.now().strftime("%Y-%m")

        if month > current_month:
            raise HTTPException(
                status_code=400,
                detail="Future months are not allowed."
            )


    orders = (
        db.query(models.Order)
        .join(models.Payment)
        .filter(
            models.Order.user_id == user_id,
            models.Order.order_status == "COMPLETED",
            models.Payment.payment_status == "COMPLETED",
            models.Payment.paid_at.isnot(None)
        )
        .distinct()
        .all()
    )

    categories = {}

    for order in orders:
        # Use the completed payment date for conversion
        payment = next(
            (
                p for p in order.payments
                if p.payment_status == "COMPLETED"
                and p.paid_at is not None
            ),
            None
        )

        
        if payment is None:
            continue

        # Filter by payment month if selected
        if month is not None:
            payment_month = payment.paid_at.strftime("%Y-%m")

            if payment_month != month:
                continue

        for item in order.items:

            category = item.category or "Uncategorized"
            amount = item.unit_price * item.quantity

            try:
                amount_usd = convert_to_usd(
                    amount,
                    order.currency,
                    payment.paid_at
                )
            except Exception as error:
                raise HTTPException(
                    status_code=503,
                    detail=f"Currency conversion failed: {error}"
                )

            if category not in categories:
                categories[category] = Decimal("0.00")

            categories[category] += amount_usd

    return {
        "user_id": user_id,
        "currency": "USD",
        "spending_by_category": {
            category: str(amount)
            for category, amount in categories.items()
        }
    }

@app.get("/api/users/{user_id}/expenses/monthly")
def get_monthly_expenses(
    user_id: str,
    db: Session = Depends(get_db)
):
    payments = (
        db.query(models.Payment)
        .join(models.Order)
        .filter(
            models.Order.user_id == user_id,
            models.Order.order_status == "COMPLETED",
            models.Payment.payment_status == "COMPLETED",
            models.Payment.paid_at.isnot(None)
        )
        .all()
    )

    monthly = {}

    for payment in payments:
        month = payment.paid_at.strftime("%Y-%m")
        currency = payment.currency

        if currency not in monthly:
            monthly[currency] = {}

        if month not in monthly[currency]:
            monthly[currency][month] = Decimal("0.00")

        monthly[currency][month] += payment.amount

    return {
        "user_id": user_id,
        "monthly_spending": {
            currency: {
                month: str(amount)
                for month, amount in sorted(months.items())
            }
            for currency, months in monthly.items()
        }
    }


# Monthly Spending Converted to USD
@app.get("/api/users/{user_id}/expenses/monthly-usd")
def get_monthly_expenses_usd(
    user_id: str,
    db: Session = Depends(get_db)
):
    payments = (
        db.query(models.Payment)
        .join(models.Order)
        .filter(
            models.Order.user_id == user_id,
            models.Order.order_status == "COMPLETED",
            models.Payment.payment_status == "COMPLETED",
            models.Payment.paid_at.isnot(None)
        )
        .all()
    )

    monthly = {}

    for payment in payments:
        month = payment.paid_at.strftime("%Y-%m")

        try:
            amount_usd = convert_to_usd(
                payment.amount,
                payment.currency,
                payment.paid_at
            )
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=f"Currency conversion failed: {error}"
            )

        if month not in monthly:
            monthly[month] = Decimal("0.00")

        monthly[month] += amount_usd

    return {
        "user_id": user_id,
        "currency": "USD",
        "monthly_spending": {
            month: str(amount)
            for month, amount in sorted(monthly.items())
        }
    }



# Create Delivery Record
@app.post("/api/orders/{order_id}/delivery")
def create_delivery(
    order_id: int,
    courier: str | None = None,
    tracking_number: str | None = None,
    delivery_method: str = "Standard",
    db: Session = Depends(get_db)
):
    order = db.get(models.Order, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    if order.order_status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Order must be paid before delivery"
        )

    existing_delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.order_id == order_id)
        .first()
    )

    if existing_delivery:
        raise HTTPException(
            status_code=409,
            detail="Delivery already exists for this order"
        )

    delivery = models.Delivery(
        order_id=order_id,
        courier=courier,
        tracking_number=tracking_number,
        delivery_method=delivery_method,
        delivery_status="NOT_SHIPPED"
    )

    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    return {
        "delivery_id": delivery.delivery_id,
        "order_id": delivery.order_id,
        "courier": delivery.courier,
        "tracking_number": delivery.tracking_number,
        "delivery_method": delivery.delivery_method,
        "delivery_status": delivery.delivery_status
    }

# Get Delivery Status by Order ID
@app.get("/api/orders/{order_id}/delivery")
def get_delivery_status(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.get(models.Order, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.order_id == order_id)
        .first()
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery record not found"
        )

    return {
        "delivery_id": delivery.delivery_id,
        "order_id": delivery.order_id,
        "courier": delivery.courier,
        "tracking_number": delivery.tracking_number,
        "delivery_method": delivery.delivery_method,
        "delivery_status": delivery.delivery_status,
        "estimated_delivery": delivery.estimated_delivery
    }


# Request body for updating delivery status
class DeliveryStatusUpdate(BaseModel):
    delivery_status: str


@app.patch("/api/deliveries/{delivery_id}")
def update_delivery_status(
    delivery_id: int,
    data: DeliveryStatusUpdate,
    db: Session = Depends(get_db)
):
    delivery = db.get(models.Delivery, delivery_id)

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )

    allowed_transitions = {
        "NOT_SHIPPED": ["SHIPPED"],
        "SHIPPED": ["IN_TRANSIT"],
        "IN_TRANSIT": ["DELIVERED"],
        "DELIVERED": []
    }

    current_status = delivery.delivery_status
    new_status = data.delivery_status.upper()

    if new_status not in allowed_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change delivery status from {current_status} to {new_status}"
        )

    delivery.delivery_status = new_status

    db.commit()
    db.refresh(delivery)

    return {
        "delivery_id": delivery.delivery_id,
        "order_id": delivery.order_id,
        "delivery_status": delivery.delivery_status,
        "message": "Delivery status updated successfully"
    }


@app.get("/dashboard")
def dashboard():
    return FileResponse(SHOPPING_FRONTEND / "index.html")


app.mount(
    "/frontend",
    StaticFiles(directory=str(SHOPPING_FRONTEND)),
    name="frontend"
)
