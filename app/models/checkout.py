from pydantic import BaseModel
from typing import List, Optional

class CartItem(BaseModel):
    name: str
    quantity: int
    price: float  

class CheckoutPayload(BaseModel):
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]
    cart_items: List[CartItem]
    created_at: str  
