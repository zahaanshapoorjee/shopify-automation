import asyncio
import logging
from app.models.checkout import CheckoutPayload
from app.services.whatsapp import send_whatsapp_template
from app.state.store import set_checkout_flow, get_checkout_flow, update_step_status
from app.database.postgres_store import postgres_store
from config_flows.client_flows import FLOW_CONFIG 

logger = logging.getLogger(__name__)

async def handle_checkout_flow(payload: CheckoutPayload, client_id="zuzumonk"):
    email = payload.customer_email
    phone = payload.customer_phone
    logger.info(f"[Checkout Flow] Starting flow for: {email}")

    if not email or not phone:
        logger.warning(f"[Checkout Flow] Missing email or phone for payload: {payload}")
        return

    if client_id not in FLOW_CONFIG:
        logger.error(f"[Checkout Flow] Unknown client_id: {client_id}")
        return

    # Anti-spam checks
    # 1. Check if user had a recent flow (prevent duplicate flows)
    recent_flow = await postgres_store.check_recent_flow(email, hours=2)
    if recent_flow:
        logger.info(f"[Checkout Flow] Blocked duplicate flow for {email} (recent flow exists)")
        return

    # 2. Check phone number message frequency
    phone_msg_count = await postgres_store.get_phone_message_count(phone, hours=24)
    if phone_msg_count >= 3:  # Max 3 flows per phone per day
        logger.warning(f"[Checkout Flow] Blocked flow for {phone} (daily limit reached)")
        await set_checkout_flow(email, {
            "status": "blocked",
            "step_status": {"reason": "daily_limit_exceeded"},
            "customer_name": payload.customer_name,
            "customer_phone": payload.customer_phone,
            "client_id": client_id
        })
        return

    # Store flow in database
    flow_data = {
        "status": "pending",
        "step_status": {},
        "customer_name": payload.customer_name,
        "customer_phone": payload.customer_phone,
        "client_id": client_id
    }
    await set_checkout_flow(email, flow_data)

    flow_steps = FLOW_CONFIG[client_id]["checkout"]

    variable_map = {
        "customer_name": payload.customer_name or "there",
        "checkout_url": "https://zuzumonk.com/checkout"
    }

    for step_index, step in enumerate(flow_steps):
        delay = step["delay"]
        template = step["template"]
        param_vars = step["params"]

        try:
            await asyncio.sleep(delay)

            # Check if flow was completed
            current_flow = await get_checkout_flow(email)
            if current_flow.get("status") == "completed":
                logger.info(f"[Checkout Flow] Stopped at step {step_index+1}, order completed: {email}")
                return

            resolved_params = [
                variable_map.get(param.strip("{}"), "") for param in param_vars
            ]

            logger.info(f"[Checkout Flow] Sending step {step_index+1} to {email} using template {template}")
            
            # This will now check rate limits before sending
            await send_whatsapp_template(phone, template, resolved_params)
            await update_step_status(email, f"step_{step_index+1}", "sent")
            
        except Exception as e:
            logger.error(f"[Checkout Flow] Error in step {step_index+1} for {email}: {str(e)}")
            await update_step_status(email, f"step_{step_index+1}", "failed")
            
            # If rate limited, stop the entire flow
            if "rate limit" in str(e).lower():
                logger.info(f"[Checkout Flow] Stopping flow due to rate limit: {email}")
                return
            continue

    logger.info(f"[Checkout Flow] Flow completed for {email}")
