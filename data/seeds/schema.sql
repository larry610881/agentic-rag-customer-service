-- Olist E-Commerce Schema for Agentic RAG Customer Service

CREATE TABLE IF NOT EXISTS olist_customers (
    customer_id VARCHAR(64) PRIMARY KEY,
    customer_unique_id VARCHAR(64),
    customer_zip_code_prefix VARCHAR(10),
    customer_city VARCHAR(128),
    customer_state VARCHAR(4)
);

CREATE TABLE IF NOT EXISTS olist_orders (
    order_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) REFERENCES olist_customers(customer_id),
    order_status VARCHAR(32),
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS olist_products (
    product_id VARCHAR(64) PRIMARY KEY,
    product_category_name VARCHAR(128),
    product_name_length INTEGER,
    product_description_length INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);

CREATE TABLE IF NOT EXISTS olist_order_items (
    order_id VARCHAR(64) REFERENCES olist_orders(order_id),
    order_item_id INTEGER,
    product_id VARCHAR(64) REFERENCES olist_products(product_id),
    seller_id VARCHAR(64),
    shipping_limit_date TIMESTAMP,
    price DECIMAL(10, 2),
    freight_value DECIMAL(10, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS olist_order_reviews (
    review_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) REFERENCES olist_orders(order_id),
    review_score INTEGER,
    review_comment_title VARCHAR(256),
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_category_translation (
    product_category_name VARCHAR(128) PRIMARY KEY,
    product_category_name_english VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    order_id VARCHAR(64) NOT NULL DEFAULT '',
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_support_tickets_tenant_id ON support_tickets(tenant_id);
