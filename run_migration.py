
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_migration():
    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "kyc_crm"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "")
        )
        
        print("Connected. Reading migration script...")
        with open("datamodel/migration_add_rag_columns.sql", "r") as f:
            sql = f.read()
            
        print("Executing migration...")
        await conn.execute(sql)
        print("Migration successful!")
        
        await conn.close()
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(run_migration())
