from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    merchant_name = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="MYR")
    order_status = Column(String, default="PENDING")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")
    deliveries = relationship("Delivery", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    item_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    product_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    category = Column(String, default="Uncategorized")

    order = relationship("Order", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    paypal_order_id = Column(String, nullable=True, unique=True)
    capture_id = Column(String, nullable=True, unique=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="MYR")
    payment_status = Column(String, default="PENDING")
    paid_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payments")


class Delivery(Base):
    __tablename__ = "deliveries"

    delivery_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    courier = Column(String, nullable=True)
    delivery_method = Column(String, nullable=True)
    tracking_number = Column(String, nullable=True)
    delivery_status = Column(String, default="NOT_SHIPPED")
    estimated_delivery = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="deliveries")