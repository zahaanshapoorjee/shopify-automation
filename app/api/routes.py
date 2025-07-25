from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from app.models.checkout import CheckoutPayload
from app.services.handlers import handle_checkout_flow
from app.state.store import update_checkout_status
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/ping")
async def ping():
    return {"status": "ok", "database": "neon-postgresql"}

@router.post("/checkouts/create")
async def checkout_webhook(
    payload: dict,  # Accept raw dict instead of CheckoutPayload
    background_task: BackgroundTasks,
    request: Request
):
    try:
        logger.info(f"[Webhook] Received checkout webhook")
        
        # Extract data from Shopify's format
        email = payload.get("email")
        customer = payload.get("customer") or {}
        
        # Handle name - could be in different formats
        first_name = customer.get("first_name", "")
        last_name = customer.get("last_name", "")
        customer_name = f"{first_name} {last_name}".strip() or None
        
        # Phone number can be in multiple places in Shopify
        customer_phone = None
        
        # Try customer phone first
        if customer.get("phone"):
            customer_phone = customer.get("phone")
        # Try customer default address
        elif customer.get("default_address", {}).get("phone"):
            customer_phone = customer.get("default_address", {}).get("phone")
        # Try billing address
        elif payload.get("billing_address", {}).get("phone"):
            customer_phone = payload.get("billing_address", {}).get("phone")
        # Try shipping address
        elif payload.get("shipping_address", {}).get("phone"):
            customer_phone = payload.get("shipping_address", {}).get("phone")
        # Try top-level phone
        elif payload.get("phone"):
            customer_phone = payload.get("phone")
        # Try SMS marketing phone
        elif payload.get("sms_marketing_phone"):
            customer_phone = payload.get("sms_marketing_phone")
        
        # Extract line items
        line_items = payload.get("line_items", [])
        cart_items = []
        for item in line_items:
            cart_items.append({
                "name": item.get("title", "Unknown Product"),
                "quantity": item.get("quantity", 1),
                "price": float(item.get("price", "0"))
            })
        
        # Create our payload format
        checkout_data = CheckoutPayload(
            customer_name=customer_name,
            customer_email=email,
            customer_phone=customer_phone,
            cart_items=cart_items,
            created_at=payload.get("created_at", "")
        )
        
        logger.info(f"[Webhook] Parsed data - Email: {email}, Phone: {customer_phone}, Name: {customer_name}")
        
        # Only process if we have email (phone is optional but preferred)
        if email:
            background_task.add_task(handle_checkout_flow, checkout_data)
            return {"status": "received", "email": email, "phone": customer_phone}
        else:
            logger.warning(f"[Webhook] No email found in checkout payload")
            return {"status": "skipped", "reason": "no_email"}
        
    except Exception as e:
        logger.error(f"[Webhook] Error processing checkout: {str(e)}")
        logger.error(f"[Webhook] Raw payload keys: {list(payload.keys())}")
        raise HTTPException(status_code=400, detail=f"Error processing webhook: {str(e)}")

@router.post("/orders/create")
async def order_created_webhook(payload: dict):
    try:
        logger.info(f"[Webhook] Received order webhook")
        
        # Extract email from order payload
        email = payload.get("email")
        customer = payload.get("customer") or {}
        if not email and customer:
            email = customer.get("email")
            
        if email:
            await update_checkout_status(email, "completed")
            logger.info(f"[Order Completed] Cancelled flow for: {email}")
            
        return {"status": "received", "email": email}
        
    except Exception as e:
        logger.error(f"[Webhook] Error processing order: {str(e)}")
        logger.error(f"[Webhook] Raw payload: {payload}")
        return {"status": "error", "message": str(e)}

@router.post("/debug/webhook")
async def debug_webhook(payload: dict, request: Request):
    """Debug endpoint to see what Shopify sends"""
    logger.info(f"[DEBUG] Headers: {dict(request.headers)}")
    logger.info(f"[DEBUG] Payload: {payload}")
    
    print(f"\n{'='*50}")
    print(f"SHOPIFY WEBHOOK DEBUG")
    print(f"{'='*50}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Payload: {payload}")
    print(f"{'='*50}\n")
    
    return {"status": "debug_received", "payload_keys": list(payload.keys())}