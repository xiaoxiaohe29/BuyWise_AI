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

    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.message.content.strip()

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
                category=categorise_product(
                    item.product_name,
                    item.description
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


@app.post("/api/paypal/test-order")
def test_paypal_order():
    try:
        result = create_paypal_order(1.00, "USD")

        approval_url = next(
            (
                link["href"]
                for link in result.get("links", [])
                if link["rel"] in ("approve", "payer-action")
            ),
            None
        )

        return {
            "paypal_order_id": result["id"],
            "status": result["status"],
            "approval_url": approval_url
        }

    except Exception:
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
        result = create_paypal_order(
            order.total_amount,
            order.currency
        )
    except Exception:
        raise HTTPException(502, "PayPal API error")

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
            502,
            "PayPal approval URL missing"
        )

    payment = models.Payment(
        order_id=order.order_id,
        paypal_order_id=result["id"],
        amount=order.total_amount,
        currency=order.currency,
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

    payment = db.query(models.Payment).filter(
        models.Payment.order_id == order_id
    ).first()

    if payment is None:
        raise HTTPException(404, "Payment not found")

    if payment.payment_status == "COMPLETED":
        return {
            "message": "Payment already completed",
            "order_id": order_id
        }

    try:
        result = capture_paypal_order(
            payment.paypal_order_id
        )
    except Exception:
        raise HTTPException(
            502,
            "PayPal capture failed; check status before retrying"
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
        and Decimal(c["amount"]["value"]) == payment.amount
    ]

    if result.get("status") != "COMPLETED" or len(matching) != 1:
        raise HTTPException(
            409,
            "Payment not verified as completed"
        )

    payment.capture_id = matching[0]["id"]
    payment.payment_status = "COMPLETED"
    payment.paid_at = datetime.now(timezone.utc)

    order.order_status = "COMPLETED"

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


# Get payments belonging to a user
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

    return [
        {
            "payment_id": p.payment_id,
            "order_id": p.order_id,
            "amount": p.amount,
            "currency": p.currency,
            "payment_status": p.payment_status,
            "paid_at": p.paid_at
        }
        for p in payments
    ]


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


# Create Delivery Record
@app.post("/api/orders/{order_id}/delivery")
def create_delivery(
    order_id: int,
    courier: str,
    tracking_number: str,
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
