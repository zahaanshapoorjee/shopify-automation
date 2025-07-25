import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict
from config import settings

logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis)
rate_limit_store: Dict[str, list] = {}
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
MAX_MESSAGES_PER_HOUR = 10  # Max messages per phone number per hour

async def is_rate_limited(phone: str) -> bool:
    """Check if phone number is rate limited"""
    now = datetime.now()
    cutoff_time = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    if phone not in rate_limit_store:
        rate_limit_store[phone] = []
    
    # Remove old entries
    rate_limit_store[phone] = [
        timestamp for timestamp in rate_limit_store[phone] 
        if timestamp > cutoff_time
    ]
    
    # Check if limit exceeded
    if len(rate_limit_store[phone]) >= MAX_MESSAGES_PER_HOUR:
        logger.warning(f"[WhatsApp] Rate limit exceeded for {phone}")
        return True
    
    return False

async def record_message_sent(phone: str):
    """Record that a message was sent"""
    if phone not in rate_limit_store:
        rate_limit_store[phone] = []
    rate_limit_store[phone].append(datetime.now())

async def send_whatsapp_template(phone: str, template: str, parameters: list):
    """
    Sends a templated WhatsApp message with rate limiting.
    """
    # Check rate limit first
    if await is_rate_limited(phone):
        logger.error(f"[WhatsApp] Message blocked due to rate limit: {phone}")
        raise Exception(f"Rate limit exceeded for {phone}")
    
    # TESTING MODE: Comment out actual WhatsApp sending
    print(f"📱 [TESTING] Would send WhatsApp to {phone}")
    print(f"   Template: {template}")
    print(f"   Parameters: {parameters}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Record successful send
    await record_message_sent(phone)
    logger.info(f"[WhatsApp] TEST MODE - Would send template '{template}' to {phone}")
    return {"message_id": f"test_msg_{datetime.now().timestamp()}", "status": "sent"}
    
    # COMMENTED OUT FOR TESTING - UNCOMMENT FOR PRODUCTION
    # url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_ID}/messages"

    # headers = {
    #     "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    #     "Content-Type": "application/json"
    # }

    # body = {
    #     "messaging_product": "whatsapp",
    #     "to": phone,
    #     "type": "template",
    #     "template": {
    #         "name": template,
    #         "language": { "code": "en_US" },
    #         "components": [
    #             {
    #                 "type": "body",
    #                 "parameters": [
    #                     {"type": "text", "text": str(val)} for val in parameters
    #                 ]
    #             }
    #         ]
    #     }
    # }

    # max_retries = 3
    # retry_count = 0
    
    # while retry_count < max_retries:
    #     try:
    #         async with httpx.AsyncClient() as client:
    #             response = await client.post(url, headers=headers, json=body)
    #             response.raise_for_status()
                
    #             # Record successful send
    #             await record_message_sent(phone)
    #             logger.info(f"[WhatsApp] Sent template '{template}' to {phone}")
    #             return response.json()
                
    #     except httpx.HTTPStatusError as e:
    #         retry_count += 1
    #         logger.error(f"[WhatsApp] Attempt {retry_count} failed to send to {phone}: {e.response.text}")
    #         if retry_count >= max_retries:
    #             logger.error(f"[WhatsApp] Max retries reached for {phone}")
    #             raise
    #         await asyncio.sleep(2 ** retry_count)  # Exponential backoff
    #     except Exception as e:
    #         retry_count += 1
    #         logger.error(f"[WhatsApp] Attempt {retry_count} failed with error: {str(e)}")
    #         if retry_count >= max_retries:
    #             logger.error(f"[WhatsApp] Max retries reached for {phone}")
    #             raise
    #         await asyncio.sleep(2 ** retry_count)
