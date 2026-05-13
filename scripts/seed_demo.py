#!/usr/bin/env python3
"""
scripts/seed_demo.py
Seeds a Neon database with demo e-commerce tables + sample data.
Run: python scripts/seed_demo.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PRODUCTS = [
    ("Wireless Headphones", "Electronics", 79.99),
    ("Bluetooth Speaker", "Electronics", 49.99),
    ("Running Shoes", "Footwear", 119.99),
    ("Yoga Mat", "Fitness", 29.99),
    ("Coffee Maker", "Appliances", 89.99),
    ("Desk Lamp", "Home", 34.99),
    ("Backpack", "Accessories", 59.99),
    ("Water Bottle", "Fitness", 24.99),
    ("Sunglasses", "Accessories", 44.99),
    ("Smart Watch", "Electronics", 199.99),
]

REGIONS = ["North", "South", "East", "West", "Central"]
STATUSES = ["completed", "completed", "completed", "refunded", "pending"]


def seed():
    db_url = os.environ["NEON_DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Drop + recreate demo tables
    cur.execute("DROP TABLE IF EXISTS order_items, orders, customers, products CASCADE")

    cur.execute("""
        CREATE TABLE products (
            product_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_price NUMERIC(10,2) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE customers (
            customer_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            region TEXT NOT NULL,
            joined_date DATE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            order_id SERIAL PRIMARY KEY,
            customer_id INT REFERENCES customers(customer_id),
            order_date DATE NOT NULL,
            status TEXT NOT NULL,
            total_amount NUMERIC(10,2) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE order_items (
            item_id SERIAL PRIMARY KEY,
            order_id INT REFERENCES orders(order_id),
            product_id INT REFERENCES products(product_id),
            quantity INT NOT NULL,
            unit_price NUMERIC(10,2) NOT NULL
        )
    """)

    # Seed products
    for name, category, price in PRODUCTS:
        cur.execute(
            "INSERT INTO products (name, category, unit_price) VALUES (%s, %s, %s)",
            (name, category, price),
        )

    # Seed customers
    for i in range(1, 201):
        joined = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))
        cur.execute(
            "INSERT INTO customers (name, email, region, joined_date) VALUES (%s, %s, %s, %s)",
            (
                f"Customer {i}",
                f"customer{i}@example.com",
                random.choice(REGIONS),
                joined.date(),
            ),
        )

    # Seed orders + items
    base_date = datetime(2023, 1, 1)
    for i in range(1, 501):
        customer_id = random.randint(1, 200)
        order_date = base_date + timedelta(days=random.randint(0, 730))
        status = random.choice(STATUSES)
        n_items = random.randint(1, 4)
        total = 0.0

        cur.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES (%s, %s, %s, 0) RETURNING order_id",
            (customer_id, order_date.date(), status),
        )
        order_id = cur.fetchone()[0]

        for _ in range(n_items):
            product_id = random.randint(1, len(PRODUCTS))
            qty = random.randint(1, 3)
            price = PRODUCTS[product_id - 1][2]
            total += qty * price
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, qty, price),
            )

        cur.execute(
            "UPDATE orders SET total_amount = %s WHERE order_id = %s",
            (round(total, 2), order_id),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Demo data seeded: 10 products, 200 customers, 500 orders")


if __name__ == "__main__":
    seed()
