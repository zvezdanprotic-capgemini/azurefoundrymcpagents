
-- Salesforce-like core data model (normalized)
-- Dialect: PostgreSQL-compatible DDL (portable to most RDBMS with minor tweaks)

-- =====================
--  ACCOUNTS & CONTACTS
-- =====================
CREATE TABLE accounts (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    industry     VARCHAR(120),
    billing_address TEXT,
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE contacts (
    id           BIGSERIAL PRIMARY KEY,
    account_id   BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    first_name   VARCHAR(120) NOT NULL,
    last_name    VARCHAR(120) NOT NULL,
    email        VARCHAR(255) UNIQUE,
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_contacts_account_id ON contacts(account_id);

-- =====================
--  OPPORTUNITIES
-- =====================
CREATE TABLE opportunities (
    id           BIGSERIAL PRIMARY KEY,
    account_id   BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    close_date   DATE,
    amount       NUMERIC(18,2),
    stage        VARCHAR(100),
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_opportunities_account_id ON opportunities(account_id);

-- =====================
--  CASES (Support)
-- =====================
CREATE TABLE cases (
    id           BIGSERIAL PRIMARY KEY,
    contact_id   BIGINT REFERENCES contacts(id) ON DELETE SET NULL,
    account_id   BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    subject      VARCHAR(255) NOT NULL,
    status       VARCHAR(60)  NOT NULL,
    priority     VARCHAR(40),
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cases_contact_id ON cases(contact_id);
CREATE INDEX idx_cases_account_id ON cases(account_id);

-- =====================
--  PRODUCTS & CATALOG
-- =====================
CREATE TABLE products (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    list_price   NUMERIC(18,2) NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Junction between Opportunities and Products (line items)
CREATE TABLE opportunity_products (
    opportunity_id BIGINT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    product_id     BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity       NUMERIC(18,4) NOT NULL DEFAULT 1,
    unit_price     NUMERIC(18,2) NOT NULL,
    discount_pct   NUMERIC(5,2)  DEFAULT 0,
    PRIMARY KEY (opportunity_id, product_id)
);

CREATE INDEX idx_opp_products_prod ON opportunity_products(product_id);

-- =====================
--  QUOTES
-- =====================
CREATE TABLE quotes (
    id            BIGSERIAL PRIMARY KEY,
    opportunity_id BIGINT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    quote_number  VARCHAR(50) UNIQUE NOT NULL,
    status        VARCHAR(60),
    total_price   NUMERIC(18,2) DEFAULT 0,
    valid_until   DATE,
    created_at    TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_quotes_opportunity_id ON quotes(opportunity_id);

CREATE TABLE quote_items (
    quote_id     BIGINT NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    product_id   BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity     NUMERIC(18,4) NOT NULL DEFAULT 1,
    unit_price   NUMERIC(18,2) NOT NULL,
    discount_pct NUMERIC(5,2)  DEFAULT 0,
    PRIMARY KEY (quote_id, product_id)
);

CREATE INDEX idx_quote_items_product_id ON quote_items(product_id);

-- =====================
--  ORDERS
-- =====================
CREATE TABLE orders (
    id            BIGSERIAL PRIMARY KEY,
    account_id    BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    quote_id      BIGINT REFERENCES quotes(id) ON DELETE SET NULL,
    order_number  VARCHAR(50) UNIQUE NOT NULL,
    order_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status        VARCHAR(60),
    total_amount  NUMERIC(18,2) DEFAULT 0,
    created_at    TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_orders_account_id ON orders(account_id);
CREATE INDEX idx_orders_quote_id   ON orders(quote_id);

CREATE TABLE order_items (
    order_id     BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity     NUMERIC(18,4) NOT NULL DEFAULT 1,
    unit_price   NUMERIC(18,2) NOT NULL,
    discount_pct NUMERIC(5,2)  DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX idx_order_items_product_id ON order_items(product_id);

-- =====================
--  INVOICES (simple model)
-- =====================
CREATE TABLE invoices (
    id             BIGSERIAL PRIMARY KEY,
    account_id     BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    order_id       BIGINT REFERENCES orders(id) ON DELETE SET NULL,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    status         VARCHAR(60),
    issue_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date       DATE,
    total_amount   NUMERIC(18,2) DEFAULT 0,
    created_at     TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_invoices_account_id ON invoices(account_id);
CREATE INDEX idx_invoices_order_id   ON invoices(order_id);

CREATE TABLE invoice_items (
    invoice_id   BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id   BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity     NUMERIC(18,4) NOT NULL DEFAULT 1,
    unit_price   NUMERIC(18,2) NOT NULL,
    discount_pct NUMERIC(5,2)  DEFAULT 0,
    PRIMARY KEY (invoice_id, product_id)
);

CREATE INDEX idx_invoice_items_product_id ON invoice_items(product_id);

-- =====================
--  DERIVED TOTALS (optional helper views)
-- =====================
CREATE OR REPLACE VIEW v_opportunity_amount AS
SELECT o.id AS opportunity_id,
       COALESCE(SUM(op.quantity * op.unit_price * (1 - COALESCE(op.discount_pct,0)/100)), 0) AS line_total
FROM opportunities o
LEFT JOIN opportunity_products op ON op.opportunity_id = o.id
GROUP BY o.id;

CREATE OR REPLACE VIEW v_quote_total AS
SELECT q.id AS quote_id,
       COALESCE(SUM(qi.quantity * qi.unit_price * (1 - COALESCE(qi.discount_pct,0)/100)), 0) AS line_total
FROM quotes q
LEFT JOIN quote_items qi ON qi.quote_id = q.id
GROUP BY q.id;

CREATE OR REPLACE VIEW v_order_total AS
SELECT o.id AS order_id,
       COALESCE(SUM(oi.quantity * oi.unit_price * (1 - COALESCE(oi.discount_pct,0)/100)), 0) AS line_total
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id;

CREATE OR REPLACE VIEW v_invoice_total AS
SELECT i.id AS invoice_id,
       COALESCE(SUM(ii.quantity * ii.unit_price * (1 - COALESCE(ii.discount_pct,0)/100)), 0) AS line_total
FROM invoices i
LEFT JOIN invoice_items ii ON ii.invoice_id = i.id
GROUP BY i.id;

-- End of schema
