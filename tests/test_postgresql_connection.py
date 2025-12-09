"""
Test PostgreSQL Connection
Tests if the PostgreSQL database is accessible with the provided credentials.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_postgresql():
    print("=" * 60)
    print("Testing PostgreSQL Connection")
    print("=" * 60)
    
    # Check required env vars
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "kyc_crm")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD")
    
    print(f"\nHost: {host}")
    print(f"Port: {port}")
    print(f"Database: {database}")
    print(f"User: {user}")
    print(f"Password: {'*' * len(password) if password else 'NOT SET'}")
    
    if not password:
        print("\n⚠️  WARNING: No password set (may be OK for local dev)")
    
    try:
        import psycopg2
        
        print("\n  Connecting to PostgreSQL...")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        print("✓ Connection established")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        cursor.execute("SELECT current_database(), current_user;")
        db_info = cursor.fetchone()
        
        print(f"\n✅ SUCCESS!")
        print(f"   PostgreSQL Version: {version[:50]}...")
        print(f"   Connected to: {db_info[0]} as {db_info[1]}")
        
        cursor.close()
        conn.close()
        return True
        
    except ImportError:
        print("\n❌ ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_postgresql()
    sys.exit(0 if success else 1)
