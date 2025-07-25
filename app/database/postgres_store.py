import asyncpg
import json
from typing import Dict, Any, Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

class PostgresStore:
    def __init__(self):
        self.connection_string = settings.DATABASE_URL
        self.pool = None
        
    async def init_pool(self):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("[Database] Connection pool initialized")
            await self.init_tables()
        except Exception as e:
            logger.error(f"[Database] Failed to initialize pool: {e}")
            raise
    
    async def init_tables(self):
        """Create tables if they don't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkout_flows (
                    email VARCHAR(255) PRIMARY KEY,
                    status VARCHAR(50) NOT NULL,
                    step_status JSONB NOT NULL DEFAULT '{}',
                    customer_name VARCHAR(255),
                    customer_phone VARCHAR(50),
                    client_id VARCHAR(100) DEFAULT 'zuzumonk',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_checkout_flows_status 
                ON checkout_flows(status);
                
                CREATE INDEX IF NOT EXISTS idx_checkout_flows_updated_at 
                ON checkout_flows(updated_at);
                
                CREATE INDEX IF NOT EXISTS idx_checkout_flows_client_id 
                ON checkout_flows(client_id);
            """)
            logger.info("[Database] Tables initialized")
    
    async def set_flow(self, email: str, data: Dict[str, Any]):
        """Create or update a checkout flow"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO checkout_flows 
                (email, status, step_status, customer_name, customer_phone, client_id, updated_at) 
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (email) DO UPDATE SET 
                    status = $2, 
                    step_status = $3, 
                    customer_name = $4,
                    customer_phone = $5,
                    client_id = $6,
                    updated_at = NOW()
            """, 
                email, 
                data["status"], 
                json.dumps(data.get("step_status", {})),
                data.get("customer_name"),
                data.get("customer_phone"),
                data.get("client_id", "zuzumonk")
            )
            logger.info(f"[Database] Set flow for {email}")
    
    async def get_flow(self, email: str) -> Dict[str, Any]:
        """Get checkout flow by email"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT status, step_status, customer_name, customer_phone, client_id, created_at
                FROM checkout_flows 
                WHERE email = $1
            """, email)
            
            if row:
                return {
                    "status": row["status"],
                    "step_status": json.loads(row["step_status"]),
                    "customer_name": row["customer_name"],
                    "customer_phone": row["customer_phone"],
                    "client_id": row["client_id"],
                    "created_at": row["created_at"]
                }
            return {}
    
    async def update_status(self, email: str, status: str):
        """Update flow status"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE checkout_flows 
                SET status = $1, updated_at = NOW() 
                WHERE email = $2
            """, status, email)
            
            if result == "UPDATE 1":
                logger.info(f"[Database] Updated status for {email} to {status}")
            else:
                logger.warning(f"[Database] No flow found for {email}")
    
    async def update_step_status(self, email: str, step: str, status: str):
        """Update specific step status"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE checkout_flows 
                SET step_status = jsonb_set(step_status, $1, $2, true),
                    updated_at = NOW()
                WHERE email = $3
            """, [step], json.dumps(status), email)
            logger.info(f"[Database] Updated {step} status for {email}")
    
    async def cleanup_old_flows(self, days: int = 30):
        """Clean up flows older than specified days"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM checkout_flows 
                WHERE updated_at < NOW() - INTERVAL '%s days'
            """ % days)
            logger.info(f"[Database] Cleaned up old flows: {result}")
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("[Database] Connection pool closed")
    
    async def check_recent_flow(self, email: str, hours: int = 24) -> bool:
        """Check if user had a flow within the last X hours"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM checkout_flows 
                WHERE email = $1 AND created_at > NOW() - INTERVAL '%s hours'
            """ % hours, email)
            return result > 0
    
    async def get_phone_message_count(self, phone: str, hours: int = 24) -> int:
        """Get message count for a phone number in the last X hours"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM checkout_flows 
                WHERE customer_phone = $1 
                AND created_at > NOW() - INTERVAL '%s hours'
                AND status != 'blocked'
            """ % hours, phone)
            return result or 0

# Global instance
postgres_store = PostgresStore()