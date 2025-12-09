"""
Seed example CRM data into PostgreSQL.

Creates a sample account, contact, products, opportunity, quote, order, and invoice
using the schema in `datamodel/salesforce_core_schema.sql`.

Environment variables required (loaded via .env):
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD

Usage:
  source venv/bin/activate
  python seed_crm_data.py
"""

import asyncio
import os
from datetime import date, timedelta
from typing import Optional

import asyncpg
from dotenv import load_dotenv


load_dotenv()


async def get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "kyc_crm"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


async def ensure_tables_exist(conn: asyncpg.Connection) -> None:
    # Basic existence check for core tables
    required = [
        "accounts", "contacts", "opportunities", "products",
        "opportunity_products", "quotes", "quote_items",
        "orders", "order_items", "invoices", "invoice_items",
    ]
    missing = []
    for t in required:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_name = $1
            )
            """,
            t,
        )
        if not exists:
            missing.append(t)

    if missing:
        raise RuntimeError(
            f"Missing tables: {', '.join(missing)}. Run migrations before seeding."
        )


async def get_or_create_account(conn: asyncpg.Connection, name: str, industry: str, billing_address: Optional[str]) -> int:
    existing = await conn.fetchrow("SELECT id FROM accounts WHERE name = $1", name)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO accounts (name, industry, billing_address)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        name, industry, billing_address,
    )
    return row["id"]


async def get_or_create_contact(conn: asyncpg.Connection, account_id: int, first_name: str, last_name: str, email: str) -> int:
    existing = await conn.fetchrow("SELECT id FROM contacts WHERE email = $1", email)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO contacts (account_id, first_name, last_name, email)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        account_id, first_name, last_name, email,
    )
    return row["id"]


async def get_or_create_product(conn: asyncpg.Connection, name: str, description: str, list_price: float) -> int:
    existing = await conn.fetchrow("SELECT id FROM products WHERE name = $1", name)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO products (name, description, list_price)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        name, description, list_price,
    )
    return row["id"]


async def create_opportunity(conn: asyncpg.Connection, account_id: int, name: str, amount: float, stage: str) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO opportunities (account_id, name, amount, stage, close_date)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        account_id, name, amount, stage, date.today() + timedelta(days=30),
    )
    return row["id"]


async def add_opportunity_product(conn: asyncpg.Connection, opportunity_id: int, product_id: int, quantity: float, unit_price: float, discount_pct: float = 0.0) -> None:
    await conn.execute(
        """
        INSERT INTO opportunity_products (opportunity_id, product_id, quantity, unit_price, discount_pct)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (opportunity_id, product_id) DO UPDATE SET
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price,
          discount_pct = EXCLUDED.discount_pct
        """,
        opportunity_id, product_id, quantity, unit_price, discount_pct,
    )


async def create_quote(conn: asyncpg.Connection, opportunity_id: int, quote_number: str, status: str, valid_until: date) -> int:
    existing = await conn.fetchrow("SELECT id FROM quotes WHERE quote_number = $1", quote_number)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO quotes (opportunity_id, quote_number, status, valid_until)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        opportunity_id, quote_number, status, valid_until,
    )
    return row["id"]


async def add_quote_item(conn: asyncpg.Connection, quote_id: int, product_id: int, quantity: float, unit_price: float, discount_pct: float = 0.0) -> None:
    await conn.execute(
        """
        INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, discount_pct)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (quote_id, product_id) DO UPDATE SET
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price,
          discount_pct = EXCLUDED.discount_pct
        """,
        quote_id, product_id, quantity, unit_price, discount_pct,
    )


async def create_order(conn: asyncpg.Connection, account_id: int, quote_id: Optional[int], order_number: str, status: str, order_date: date) -> int:
    existing = await conn.fetchrow("SELECT id FROM orders WHERE order_number = $1", order_number)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO orders (account_id, quote_id, order_number, status, order_date)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        account_id, quote_id, order_number, status, order_date,
    )
    return row["id"]


async def add_order_item(conn: asyncpg.Connection, order_id: int, product_id: int, quantity: float, unit_price: float, discount_pct: float = 0.0) -> None:
    await conn.execute(
        """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (order_id, product_id) DO UPDATE SET
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price,
          discount_pct = EXCLUDED.discount_pct
        """,
        order_id, product_id, quantity, unit_price, discount_pct,
    )


async def create_invoice(conn: asyncpg.Connection, account_id: int, order_id: Optional[int], invoice_number: str, status: str, issue_date: date, due_date: date) -> int:
    existing = await conn.fetchrow("SELECT id FROM invoices WHERE invoice_number = $1", invoice_number)
    if existing:
        return existing["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO invoices (account_id, order_id, invoice_number, status, issue_date, due_date)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        account_id, order_id, invoice_number, status, issue_date, due_date,
    )
    return row["id"]


async def add_invoice_item(conn: asyncpg.Connection, invoice_id: int, product_id: int, quantity: float, unit_price: float, discount_pct: float = 0.0) -> None:
    await conn.execute(
        """
        INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price, discount_pct)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (invoice_id, product_id) DO UPDATE SET
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price,
          discount_pct = EXCLUDED.discount_pct
        """,
        invoice_id, product_id, quantity, unit_price, discount_pct,
    )


async def seed():
    conn = await get_conn()
    try:
        await ensure_tables_exist(conn)

        # 1) Account + Contact
        account_id = await get_or_create_account(
            conn,
            name="Acme Insurance Ltd",
            industry="Insurance",
            billing_address="100 Market St, Sovereign City",
        )
        contact_id = await get_or_create_contact(
            conn,
            account_id=account_id,
            first_name="Alice",
            last_name="Johnson",
            email="alice@example.com",
        )

        # 2) Products
        auto_prod = await get_or_create_product(conn, "Auto Insurance Policy", "Comprehensive auto coverage", 1200.00)
        home_prod = await get_or_create_product(conn, "Home Insurance Policy", "Home & contents coverage", 950.00)

        # 3) Opportunity
        opp_id = await create_opportunity(conn, account_id, "Alice - Insurance Policies", amount=2150.0, stage="Qualification")
        await add_opportunity_product(conn, opp_id, auto_prod, quantity=1, unit_price=1200.00)
        await add_opportunity_product(conn, opp_id, home_prod, quantity=1, unit_price=950.00, discount_pct=5.0)

        # 4) Quote + items
        quote_id = await create_quote(
            conn,
            opp_id,
            quote_number="Q-10001",
            status="Draft",
            valid_until=date.today() + timedelta(days=30),
        )
        await add_quote_item(conn, quote_id, auto_prod, quantity=1, unit_price=1200.00)
        await add_quote_item(conn, quote_id, home_prod, quantity=1, unit_price=950.00, discount_pct=5.0)

        # 5) Order + items
        order_id = await create_order(
            conn,
            account_id=account_id,
            quote_id=quote_id,
            order_number="O-50001",
            status="Processing",
            order_date=date.today(),
        )
        await add_order_item(conn, order_id, auto_prod, quantity=1, unit_price=1200.00)
        await add_order_item(conn, order_id, home_prod, quantity=1, unit_price=950.00, discount_pct=5.0)

        # 6) Invoice + items
        invoice_id = await create_invoice(
            conn,
            account_id=account_id,
            order_id=order_id,
            invoice_number="INV-90001",
            status="Issued",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        await add_invoice_item(conn, invoice_id, auto_prod, quantity=1, unit_price=1200.00)
        await add_invoice_item(conn, invoice_id, home_prod, quantity=1, unit_price=950.00, discount_pct=5.0)

        print("Seed complete:")
        print(f"  account_id={account_id}")
        print(f"  contact_id={contact_id} (alice@example.com)")
        print(f"  opportunity_id={opp_id}")
        print(f"  quote_id={quote_id}")
        print(f"  order_id={order_id}")
        print(f"  invoice_id={invoice_id}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
