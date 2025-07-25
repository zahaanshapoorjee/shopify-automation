from app.database.postgres_store import postgres_store
import logging

logger = logging.getLogger(__name__)

# Keep in-memory cache for frequently accessed data
checkout_flows = {}

async def init_database():
    """Initialize database connection"""
    await postgres_store.init_pool()

async def set_checkout_flow(email: str, data: dict):
    """Set checkout flow in both cache and database"""
    checkout_flows[email] = data
    await postgres_store.set_flow(email, data)

async def get_checkout_flow(email: str) -> dict:
    """Get checkout flow from cache or database"""
    if email not in checkout_flows:
        # Load from database if not in cache
        flow_data = await postgres_store.get_flow(email)
        if flow_data:
            checkout_flows[email] = flow_data
        return flow_data
    return checkout_flows.get(email, {})

async def update_checkout_status(email: str, status: str):
    """Update checkout status in both cache and database"""
    if email in checkout_flows:
        checkout_flows[email]["status"] = status
    await postgres_store.update_status(email, status)

async def update_step_status(email: str, step: str, status: str):
    """Update step status in both cache and database"""
    if email in checkout_flows and "step_status" in checkout_flows[email]:
        checkout_flows[email]["step_status"][step] = status
    await postgres_store.update_step_status(email, step, status)

async def cleanup_old_flows(days: int = 30):
    """Clean up old flows"""
    await postgres_store.cleanup_old_flows(days)
    # Clear cache
    checkout_flows.clear()