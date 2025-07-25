from typing import Dict, List, Any

# Rate limiting configuration
RATE_LIMITS = {
    "max_messages_per_phone_per_hour": 10,
    "max_flows_per_phone_per_day": 3,
    "min_hours_between_flows": 2,
    "global_daily_limit": 1000
}

# Configuration for different client checkout flows
FLOW_CONFIG: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "zuzumonk": {
        "checkout": [
            {
                "delay": 10,  # TESTING: 10 seconds (was 300 = 5 minutes)
                "template": "abandoned_cart_reminder_1",
                "params": ["{customer_name}"]
            },
            {
                "delay": 10,  # TESTING: 10 seconds (was 1800 = 30 minutes)
                "template": "abandoned_cart_reminder_2", 
                "params": ["{customer_name}", "{checkout_url}"]
            },
            {
                "delay": 10,  # TESTING: 10 seconds (was 3600 = 1 hour)
                "template": "abandoned_cart_final",
                "params": ["{customer_name}", "{checkout_url}"]
            }
        ]
    }
}