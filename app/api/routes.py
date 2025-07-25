from fastapi import APIRouter, BackgroundTasks, Request
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
    payload: CheckoutPayload,
    background_task: BackgroundTasks,
    request: Request
):
    background_task.add_task(
        handle_checkout_flow,  
        payload
    )
    return {"status": "true", "queued": True}

@router.post("/orders/create")
async def order_created_webhook(payload: CheckoutPayload):
    email = payload.customer_email
    if email:
        await update_checkout_status(email, "completed")
        logger.info(f"[Order Completed] Cancelled flow for: {email}")
    return {"status": "received"}

@router.get("/stats")
async def get_stats():
    """Get messaging statistics"""
    async with postgres_store.pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_flows,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_flows,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_flows,
                COUNT(*) FILTER (WHERE status = 'blocked') as blocked_flows,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as flows_last_24h
            FROM checkout_flows
        """)
        
        return {
            "total_flows": stats["total_flows"],
            "pending_flows": stats["pending_flows"], 
            "completed_flows": stats["completed_flows"],
            "blocked_flows": stats["blocked_flows"],
            "flows_last_24h": stats["flows_last_24h"]
        }
