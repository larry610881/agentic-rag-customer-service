"""Match DM products with Carrefour online store URLs.

Reads product names from DM chunks in DB, searches online.carrefour.com.tw,
and outputs a JSON mapping of product → online URL.
"""

import asyncio
import json
import re
import time
import urllib.parse
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).parent


BASE = "https://online.carrefour.com.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def extract_products_from_chunks(chunks: list[str]) -> list[dict]:
    """Extract structured product info from DM chunks."""
    products = []
    current = {}

    for chunk in chunks:
        for line in chunk.split("\n"):
            line = line.strip()
            if line.startswith("商品："):
                if current.get("name"):
                    products.append(current)
                current = {"name": line[3:].strip()}
            elif line.startswith("品牌："):
                current["brand"] = line[3:].strip()
            elif line.startswith("規格："):
                current["spec"] = line[3:].strip()
            elif line.startswith("原價："):
                current["original_price"] = line[3:].strip()
            elif line.startswith("售價："):
                current["price"] = line[3:].strip()
            elif line.startswith("促銷："):
                current["promotion"] = line[3:].strip()
            elif line.startswith("備註："):
                current["note"] = line[3:].strip()

    if current.get("name"):
        products.append(current)

    return products


def make_search_keyword(product: dict) -> str:
    """Extract best search keyword from product name."""
    name = product["name"]
    brand = product.get("brand", "")

    # Remove generic suffixes and specs
    name = re.sub(r'[（(][^）)]*[）)]', '', name)  # Remove parenthetical
    name = re.sub(r'\d+[gGmMlL克公升毫升包入瓶罐]+.*', '', name)  # Remove size specs
    name = name.strip()

    # Use brand + short name for better matching
    if brand and brand != "不詳" and brand not in name:
        keyword = f"{brand} {name}"
    else:
        keyword = name

    # Limit length
    if len(keyword) > 20:
        keyword = keyword[:20]

    return keyword.strip()


async def search_product(client: httpx.AsyncClient, keyword: str) -> list[dict]:
    """Search Carrefour online store and return product URLs."""
    url = f"{BASE}/zh/search/?q={urllib.parse.quote(keyword)}"
    try:
        resp = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return []

        html = resp.text
        # Extract product page links: /zh/{brand}/{id}.html
        links = re.findall(r'href="(/zh/[^"]+/(\d{5,})\.html)"', html)

        results = []
        seen = set()
        for link_path, product_id in links:
            if product_id in seen:
                continue
            seen.add(product_id)
            full_url = f"{BASE}{link_path}"
            decoded_path = urllib.parse.unquote(link_path)

            # Try to extract title near the link
            escaped = re.escape(link_path)
            context_matches = re.findall(rf'title="([^"]+)"[^>]*href="{escaped}"', html)
            if not context_matches:
                context_matches = re.findall(rf'href="{escaped}"[^>]*title="([^"]+)"', html)

            title = context_matches[0] if context_matches else ""

            results.append({
                "url": full_url,
                "product_id": product_id,
                "title": title,
                "path": decoded_path,
            })

        return results[:5]  # Top 5 matches
    except Exception as e:
        print(f"  Search error: {e}")
        return []


async def main():
    # Read chunks from DB
    import sys
    sys.path.insert(0, ".")

    from src.infrastructure.db.engine import engine
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as session:
        r = await session.execute(
            text("SELECT content FROM chunks WHERE document_id = 'cd4a4dc8-44db-4b54-9705-1bbb53a5fafe'")
        )
        chunks = [row[0] for row in r.fetchall()]

    products = extract_products_from_chunks(chunks)
    print(f"Extracted {len(products)} products from DM")

    # Deduplicate by name
    seen_names = set()
    unique_products = []
    for p in products:
        if p["name"] not in seen_names:
            seen_names.add(p["name"])
            unique_products.append(p)
    print(f"Unique products: {len(unique_products)}")

    # Search in batches
    results = []
    async with httpx.AsyncClient() as client:
        for i, product in enumerate(unique_products):
            keyword = make_search_keyword(product)
            print(f"[{i+1}/{len(unique_products)}] Searching: {keyword}")

            matches = await search_product(client, keyword)

            product_result = {
                **product,
                "search_keyword": keyword,
                "online_matches": matches,
            }
            results.append(product_result)

            # Rate limit: 1 request per 2 seconds
            if i < len(unique_products) - 1:
                await asyncio.sleep(2)

            # Progress save every 50
            if (i + 1) % 50 == 0:
                with open(SCRIPT_DIR / "dm-products-progress.json", "w") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"  Progress saved: {len(results)} products")

    # Final save
    output_path = str(SCRIPT_DIR / "dm-products-with-urls.json")
    with open(output_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    matched = sum(1 for r in results if r["online_matches"])
    print(f"\nDone! {matched}/{len(results)} products matched with online URLs")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
