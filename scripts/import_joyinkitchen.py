"""
匯入窩廚房（joyinkitchen）MySQL dump 至 PostgreSQL。

從 MySQL dump 解析 INSERT 語句，在 PostgreSQL 建立 MCP server 所需的 9 張表並匯入資料。

用法:
    python scripts/import_joyinkitchen.py

環境變數（可選）:
    DATABASE_URL  預設 postgresql://postgres:postgres@127.0.0.1:5432/agentic_rag
"""

import os
import re
import sys
from pathlib import Path

import psycopg2

SQL_DUMP = Path("/home/p10359945/source/repos/joyinkitchen_20260212.sql")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "agentic_rag")

# MCP server 所需的 9 張表
TABLES_DDL = """
-- 商品相關
CREATE TABLE IF NOT EXISTS product_categories (
    id          SERIAL PRIMARY KEY,
    parent_id   INT DEFAULT 0,
    floor       SMALLINT DEFAULT 1,
    name        VARCHAR(150) DEFAULT '',
    is_online   SMALLINT DEFAULT 1,
    sort        INT DEFAULT 9999,
    created_at  BIGINT,
    updated_at  BIGINT
);

CREATE TABLE IF NOT EXISTS products (
    id                  SERIAL PRIMARY KEY,
    product_category_id INT,
    name                VARCHAR(100),
    brand_id            INT,
    description         VARCHAR(200),
    content             TEXT,
    note                VARCHAR(255),
    ship_note           VARCHAR(255),
    ship_description    TEXT,
    return_description  TEXT,
    shopping_notice     TEXT,
    start_at            BIGINT,
    end_at              BIGINT,
    list_price          INT,
    price               INT,
    coin                INT DEFAULT 0,
    media_id            INT,
    ship_type           SMALLINT NOT NULL DEFAULT 1,
    status              SMALLINT NOT NULL DEFAULT 2,
    is_online           SMALLINT NOT NULL DEFAULT 0,
    sort                SMALLINT NOT NULL DEFAULT 0,
    buy_count           INT NOT NULL DEFAULT 0,
    pick_up_type        INT NOT NULL DEFAULT 1,
    created_user        INT,
    created_at          BIGINT,
    updated_at          BIGINT
);

CREATE TABLE IF NOT EXISTS product_product_category (
    product_category_id INT NOT NULL,
    product_id          INT NOT NULL,
    PRIMARY KEY (product_category_id, product_id)
);

-- 課程相關
CREATE TABLE IF NOT EXISTS course_categories (
    id          SERIAL PRIMARY KEY,
    parent_id   INT DEFAULT 0,
    floor       SMALLINT DEFAULT 1,
    name        VARCHAR(150) DEFAULT '',
    color       VARCHAR(20) DEFAULT '#DDDDDD',
    is_online   SMALLINT DEFAULT 1,
    sort        INT DEFAULT 9999,
    created_at  BIGINT,
    updated_at  BIGINT
);

CREATE TABLE IF NOT EXISTS courses (
    id                  SERIAL PRIMARY KEY,
    course_category_id  INT,
    name                VARCHAR(255),
    description         VARCHAR(150),
    content             TEXT,
    cancel_change       TEXT,
    open_number         SMALLINT,
    few_number          SMALLINT,
    onlined_at          BIGINT,
    list_price          INT,
    price               INT,
    coin                INT,
    media_id            INT,
    status              SMALLINT NOT NULL DEFAULT 2,
    is_online           SMALLINT NOT NULL DEFAULT 0,
    sort                SMALLINT NOT NULL DEFAULT 0,
    buy_count           INT NOT NULL DEFAULT 0,
    created_user        INT NOT NULL,
    created_at          BIGINT,
    updated_at          BIGINT
);

CREATE TABLE IF NOT EXISTS course_stocks (
    id              SERIAL PRIMARY KEY,
    course_id       INT NOT NULL,
    open_number     INT NOT NULL,
    start_at        BIGINT NOT NULL,
    end_at          BIGINT NOT NULL,
    deadline_at     BIGINT,
    created_user    INT,
    created_at      BIGINT,
    updated_user    INT,
    updated_at      BIGINT
);

CREATE TABLE IF NOT EXISTS course_stock_records (
    id                  SERIAL PRIMARY KEY,
    order_id            INT,
    course_stock_id     INT NOT NULL,
    buy_number          INT NOT NULL,
    note                VARCHAR(50) NOT NULL DEFAULT '訂單購買',
    created_at          BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS lectors (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    outsite_url     VARCHAR(255),
    description     TEXT,
    content         TEXT,
    content_video   VARCHAR(255),
    img_url         VARCHAR(255),
    fb_share        VARCHAR(255),
    ig_share        VARCHAR(255),
    is_online       SMALLINT NOT NULL DEFAULT 1,
    sort            SMALLINT NOT NULL DEFAULT 0,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE TABLE IF NOT EXISTS course_lector (
    course_id   INT NOT NULL,
    lector_id   INT NOT NULL,
    PRIMARY KEY (course_id, lector_id)
);
"""

# 每張表對應的欄位數（從 MySQL dump 的 INSERT 語句推斷）
TABLE_COLUMNS = {
    "product_categories": 8,
    "products": 26,
    "product_product_category": 2,
    "course_categories": 9,
    "courses": 20,
    "course_stocks": 10,
    "course_stock_records": 6,
    "lectors": 13,
    "course_lector": 2,
}


def parse_sql_values(sql_line: str) -> list[tuple]:
    """解析 INSERT INTO `table` VALUES (...),(...); 語句。"""
    match = re.search(r"VALUES\s+", sql_line, re.IGNORECASE)
    if not match:
        return []

    data = sql_line[match.end() :]
    data = data.rstrip().rstrip(";")

    rows = []
    i = 0
    n = len(data)

    while i < n:
        while i < n and data[i] != "(":
            i += 1
        if i >= n:
            break
        i += 1

        fields = []
        while i < n:
            while i < n and data[i] in (" ", "\t"):
                i += 1
            if i >= n:
                break

            if data[i] == ")":
                i += 1
                break

            if data[i] == ",":
                i += 1
                continue

            if data[i] == "'":
                i += 1
                parts = []
                while i < n:
                    if data[i] == "\\" and i + 1 < n:
                        next_char = data[i + 1]
                        escape_map = {
                            "'": "'",
                            "\\": "\\",
                            "n": "\n",
                            "r": "\r",
                            "t": "\t",
                            "0": "\0",
                        }
                        parts.append(escape_map.get(next_char, next_char))
                        i += 2
                    elif data[i] == "'":
                        i += 1
                        break
                    else:
                        parts.append(data[i])
                        i += 1
                fields.append("".join(parts))

            elif data[i : i + 4] == "NULL":
                fields.append(None)
                i += 4

            else:
                start = i
                while i < n and data[i] not in (",", ")"):
                    i += 1
                val = data[start:i].strip()
                if "." in val:
                    fields.append(float(val))
                else:
                    try:
                        fields.append(int(val))
                    except ValueError:
                        fields.append(val)

        rows.append(tuple(fields))

    return rows


def read_insert_for_table(sql_text: str, table_name: str) -> list[tuple]:
    """從 SQL dump 中找到指定 table 的所有 INSERT 語句並解析。"""
    pattern = re.compile(
        rf"^INSERT INTO `{re.escape(table_name)}` VALUES ",
        re.MULTILINE,
    )

    all_rows = []
    for match in pattern.finditer(sql_text):
        line_start = match.start()
        line_end = sql_text.index("\n", line_start)
        line = sql_text[line_start:line_end]
        all_rows.extend(parse_sql_values(line))

    print(f"  {table_name}: {len(all_rows)} rows")
    return all_rows


def import_table(
    cur, table_name: str, rows: list[tuple], num_columns: int
) -> None:
    """將資料插入 PostgreSQL 表。"""
    if not rows:
        return

    # 過濾欄位數不匹配的行
    valid_rows = [r for r in rows if len(r) == num_columns]
    if len(valid_rows) != len(rows):
        print(
            f"    [WARN] {table_name}: 跳過 {len(rows) - len(valid_rows)} 筆欄位數不匹配的資料"
        )

    if not valid_rows:
        return

    placeholders = ", ".join(["%s"] * num_columns)
    sql = f"INSERT INTO {table_name} VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    # 批次插入
    batch_size = 500
    for i in range(0, len(valid_rows), batch_size):
        batch = valid_rows[i : i + batch_size]
        cur.executemany(sql, batch)

    print(f"    -> 匯入 {len(valid_rows)} 筆")


def main():
    if not SQL_DUMP.exists():
        print(f"ERROR: SQL dump 不存在: {SQL_DUMP}")
        sys.exit(1)

    print(f"讀取 SQL dump: {SQL_DUMP}")
    sql_text = SQL_DUMP.read_text(encoding="utf-8")
    print(f"  檔案大小: {len(sql_text):,} bytes\n")

    if DATABASE_URL:
        print(f"連線 PostgreSQL: {DATABASE_URL}\n")
        conn = psycopg2.connect(DATABASE_URL)
    else:
        print(f"連線 PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}\n")
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
        )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 建表
        print("=== 建立資料表 ===")
        cur.execute(TABLES_DDL)
        conn.commit()
        print("  完成\n")

        # 匯入順序：先主表，後關聯表
        import_order = [
            "product_categories",
            "products",
            "product_product_category",
            "course_categories",
            "courses",
            "course_stocks",
            "course_stock_records",
            "lectors",
            "course_lector",
        ]

        print("=== 解析 & 匯入資料 ===")
        for table_name in import_order:
            rows = read_insert_for_table(sql_text, table_name)
            num_cols = TABLE_COLUMNS[table_name]
            import_table(cur, table_name, rows, num_cols)
            conn.commit()

        # 重設 serial sequences
        print("\n=== 重設 sequences ===")
        serial_tables = [
            "product_categories",
            "products",
            "course_categories",
            "courses",
            "course_stocks",
            "course_stock_records",
            "lectors",
        ]
        for t in serial_tables:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                f"COALESCE(MAX(id), 1)) FROM {t}"
            )
        conn.commit()
        print("  完成")

        # 驗證
        print("\n=== 驗證 ===")
        for table_name in import_order:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"  {table_name}: {count} rows")

        print("\n匯入完成！")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
