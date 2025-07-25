from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from app.models.checkout import CheckoutPayload
from app.services.handlers import handle_checkout_flow
from app.state.store import update_checkout_status
from app.database.postgres_store import postgres_store  # Add this import
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

@router.delete("/admin/reset-database")
async def reset_database():
    """
    DANGER: Reset database - FOR TESTING ONLY
    Deletes all checkout flows from the database
    """
    try:
        async with postgres_store.pool.acquire() as conn:
            # Delete all checkout flows
            result = await conn.execute("DELETE FROM checkout_flows")
            
            # Extract count from result string like "DELETE 5"
            deleted_count = int(result.split()[-1]) if result and result.split() else 0
            
            logger.info(f"[Admin] Database reset - Deleted {deleted_count} checkout flows")
            
            return {
                "status": "success",
                "message": f"Database reset successfully",
                "deleted_rows": deleted_count,
                "warning": "All checkout flows have been deleted"
            }
            
    except Exception as e:
        logger.error(f"[Admin] Database reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")

@router.get("/admin/database-state")
async def get_database_state():
    """
    Get complete database state - all checkout flows and statistics
    """
    try:
        async with postgres_store.pool.acquire() as conn:
            # Get all flows
            flows = await conn.fetch("""
                SELECT 
                    email, 
                    status, 
                    step_status, 
                    customer_name, 
                    customer_phone, 
                    client_id,
                    created_at, 
                    updated_at
                FROM checkout_flows 
                ORDER BY created_at DESC
            """)
            
            # Get statistics
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_flows,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_flows,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_flows,
                    COUNT(*) FILTER (WHERE status = 'blocked') as blocked_flows,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as flows_last_hour,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as flows_last_24h,
                    MIN(created_at) as oldest_flow,
                    MAX(created_at) as newest_flow
                FROM checkout_flows
            """)
            
            # Convert flows to list of dicts
            flows_data = []
            for flow in flows:
                flows_data.append({
                    "email": flow["email"],
                    "status": flow["status"],
                    "step_status": flow["step_status"],
                    "customer_name": flow["customer_name"],
                    "customer_phone": flow["customer_phone"],
                    "client_id": flow["client_id"],
                    "created_at": flow["created_at"].isoformat() if flow["created_at"] else None,
                    "updated_at": flow["updated_at"].isoformat() if flow["updated_at"] else None
                })
            
            return {
                "statistics": {
                    "total_flows": stats["total_flows"],
                    "pending_flows": stats["pending_flows"],
                    "completed_flows": stats["completed_flows"],
                    "blocked_flows": stats["blocked_flows"],
                    "flows_last_hour": stats["flows_last_hour"],
                    "flows_last_24h": stats["flows_last_24h"],
                    "oldest_flow": stats["oldest_flow"].isoformat() if stats["oldest_flow"] else None,
                    "newest_flow": stats["newest_flow"].isoformat() if stats["newest_flow"] else None
                },
                "flows": flows_data,
                "total_records": len(flows_data)
            }
            
    except Exception as e:
        logger.error(f"[Admin] Database state query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database state query failed: {str(e)}")