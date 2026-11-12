from pydantic import BaseModel, ConfigDict, Field, EmailStr
from decimal import Decimal
from typing import List

class OrderItemCreate(BaseModel):
    product_name: str
    description: str | None = None
    quantity: int = Field(default=1, gt=0)
    unit_price: Decimal = Field(gt=0)
    category: str | None = None


class OrderCreate(BaseModel):
    user_id: str
    merchant_name: str
    platform: str
    currency: str = "MYR"
    items: List[OrderItemCreate]


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    product_name: str
    description: str | None
    quantity: int
    unit_price: Decimal
    category: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    user_id: str
    merchant_name: str
    platform: str
    total_amount: Decimal
    currency: str
    order_status: str
    items: List[OrderItemResponse]

class UserRegister(BaseModel):
        username: str = Field(min_length=3, max_length=50)
        email: EmailStr
        password: str = Field(min_length=8, max_length=128)

class UserResponse(BaseModel):
        user_id: int
        username: str
        email: EmailStr

        model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

