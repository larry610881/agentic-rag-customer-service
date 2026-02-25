"""Generate synthetic product names/descriptions/stock/price for Olist products.

Reads olist_products + product_category_translation + olist_order_items,
generates rule-based name, template-based description, random stock, and avg price.

Usage:
    cd apps/backend
    uv run python ../../data/seeds/generate_synthetic_products.py
"""

import asyncio
import os
import random
from typing import Any

import asyncpg

# Seed for reproducibility
random.seed(42)

# Category → candidate product names (English)
CATEGORY_PRODUCT_NAMES: dict[str, list[str]] = {
    "computers_accessories": [
        "Wireless Mouse", "USB Hub", "Laptop Stand", "Keyboard Cover",
        "Cable Organizer", "Monitor Riser", "Mouse Pad", "Webcam Cover",
        "USB Flash Drive", "Laptop Sleeve",
    ],
    "telephony": [
        "Phone Case", "Screen Protector", "Charging Cable", "Car Mount",
        "Phone Stand", "SIM Card Adapter", "Earphone Jack Plug",
        "Phone Lanyard", "Ring Holder", "Cable Clip",
    ],
    "electronics": [
        "Bluetooth Speaker", "Power Bank", "LED Desk Lamp",
        "Digital Thermometer", "Smart Plug", "USB Charger",
        "Portable Fan", "Night Light", "Timer Switch", "Voltage Converter",
    ],
    "audio": [
        "Wireless Earbuds", "Headphone Stand", "Audio Cable",
        "Microphone Pop Filter", "Sound Card", "Speaker Cable",
        "Earphone Case", "Audio Splitter", "Clip Microphone",
    ],
    "tablets_printing_image": [
        "Tablet Case", "Stylus Pen", "Screen Film", "Tablet Stand",
        "Drawing Glove", "Pen Nib Set", "Tablet Sleeve",
    ],
    "watches_gifts": [
        "Analog Watch", "Digital Watch", "Watch Band", "Watch Box",
        "Gift Card Holder", "Jewelry Box", "Watch Stand",
    ],
    "cool_stuff": [
        "Fidget Spinner", "Desk Toy", "Novelty Mug", "LED Keychain",
        "Puzzle Cube", "Stress Ball", "Mini Figure",
    ],
    "consoles_games": [
        "Game Controller", "Console Stand", "Headset Hanger",
        "Controller Grip", "Charging Dock", "Game Card Case",
    ],
    "sports_leisure": [
        "Yoga Mat", "Resistance Band", "Jump Rope", "Water Bottle",
        "Sweatband", "Fitness Gloves", "Exercise Ball",
    ],
    "health_beauty": [
        "Face Mask", "Hair Brush", "Nail Clipper Set", "Makeup Mirror",
        "Essential Oil", "Hand Cream", "Facial Roller",
    ],
    "housewares": [
        "Kitchen Timer", "Measuring Cups", "Food Container",
        "Cutting Board", "Dish Rack", "Spice Jar Set",
    ],
    "furniture_decor": [
        "Photo Frame", "Wall Hook", "Shelf Bracket", "Candle Holder",
        "Desk Organizer", "Plant Pot", "Door Stopper",
    ],
    "bed_bath_table": [
        "Towel Set", "Pillow Case", "Bed Sheet", "Bath Mat",
        "Table Runner", "Napkin Set", "Shower Curtain",
    ],
    "garden_tools": [
        "Pruning Shears", "Garden Gloves", "Plant Label", "Watering Can",
        "Seed Starter Kit", "Garden Kneeler", "Hose Nozzle",
    ],
    "toys": [
        "Building Blocks", "Plush Toy", "Board Game", "Toy Car",
        "Puzzle Set", "Art Supply Kit", "Play Dough Set",
    ],
    "baby": [
        "Baby Bib", "Teething Toy", "Baby Bottle", "Pacifier Clip",
        "Baby Blanket", "Diaper Bag", "Baby Spoon Set",
    ],
    "stationery": [
        "Notebook", "Pen Set", "Sticky Notes", "Pencil Case",
        "Ruler Set", "Highlighter Pack", "Bookmark Set",
    ],
    "fashion_bags_accessories": [
        "Tote Bag", "Wallet", "Belt", "Sunglasses Case",
        "Key Chain", "Scarf", "Hair Accessory",
    ],
    "fashion_shoes": [
        "Sneakers", "Sandals", "Slippers", "Shoe Insert",
        "Shoe Brush", "Boot Laces", "Shoe Bag",
    ],
    "fashion_male_clothing": [
        "T-Shirt", "Polo Shirt", "Casual Shorts", "Hoodie",
        "Jacket", "Denim Jeans", "Sweatpants",
    ],
    "fashion_female_clothing": [
        "Blouse", "Skirt", "Dress", "Leggings",
        "Cardigan", "Tank Top", "Scarf Wrap",
    ],
    "fashion_underwear_beach": [
        "Beach Towel", "Swim Goggles", "Board Shorts",
        "Bikini Set", "Rash Guard", "Flip Flops",
    ],
    "fashion_childrens_clothes": [
        "Kids T-Shirt", "Kids Shorts", "Kids Dress",
        "Kids Jacket", "Kids Socks Set", "Kids Hat",
    ],
    "food": [
        "Snack Box", "Coffee Beans", "Tea Sampler",
        "Chocolate Bar", "Granola Pack", "Honey Jar",
    ],
    "food_drink": [
        "Juice Pack", "Energy Bar", "Protein Shake",
        "Dried Fruit Mix", "Nut Butter", "Sparkling Water",
    ],
    "drinks": [
        "Green Tea", "Herbal Tea", "Coffee Capsule",
        "Juice Bottle", "Mineral Water", "Coconut Water",
    ],
    "books_general_interest": [
        "Novel", "Self-Help Book", "Cookbook",
        "Travel Guide", "Art Book", "Children's Book",
    ],
    "books_technical": [
        "Programming Book", "Data Science Manual",
        "Engineering Textbook", "Tech Reference Guide",
    ],
    "books_imported": [
        "Imported Novel", "Foreign Language Book",
        "International Bestseller", "Translated Classic",
    ],
    "cds_dvds_musicals": [
        "Music CD", "Movie DVD", "Concert DVD",
        "Music Box Set", "Vinyl Record",
    ],
    "musical_instruments": [
        "Guitar Picks", "Drumsticks", "Tuner",
        "Capo", "Sheet Music Stand", "Harmonica",
    ],
    "pet_shop": [
        "Pet Bowl", "Dog Toy", "Cat Scratcher",
        "Pet Collar", "Pet Bed", "Leash",
    ],
    "auto": [
        "Car Phone Mount", "Seat Cushion", "Sun Shade",
        "Air Freshener", "Car Charger", "Trunk Organizer",
    ],
    "perfumery": [
        "Eau de Toilette", "Body Mist", "Perfume Sample Set",
        "Scented Candle", "Aroma Diffuser",
    ],
    "diapers_hygiene": [
        "Baby Wipes", "Diaper Pack", "Changing Pad",
        "Hand Sanitizer", "Tissue Pack",
    ],
    "construction_tools_safety": [
        "Safety Goggles", "Work Gloves", "Tape Measure",
        "Utility Knife", "Drill Bit Set", "Hard Hat",
    ],
    "construction_tools_construction": [
        "Screwdriver Set", "Wrench Set", "Pliers",
        "Hammer", "Level Tool", "Socket Set",
    ],
    "construction_tools_lights": [
        "LED Bulb", "Work Light", "Flashlight",
        "Strip Light", "Lamp Holder", "Motion Sensor Light",
    ],
    "construction_tools_garden": [
        "Shovel", "Rake", "Garden Hose", "Wheelbarrow",
        "Lawn Sprinkler", "Hedge Trimmer",
    ],
    "agro_industry_and_commerce": [
        "Seed Pack", "Fertilizer", "Irrigation Kit",
        "Soil Tester", "Crop Netting",
    ],
    "office_furniture": [
        "Office Chair", "Desk Pad", "Monitor Arm",
        "Filing Cabinet", "Desk Drawer Unit",
    ],
    "industry_commerce_and_business": [
        "Business Card Holder", "Invoice Book",
        "Label Printer", "Cash Register", "Receipt Paper",
    ],
    "fixed_telephony": [
        "Corded Phone", "Phone Splitter", "Extension Cord",
        "Phone Stand", "Wall Mount Bracket",
    ],
    "signaling_and_security": [
        "Security Camera", "Door Lock", "Alarm Sensor",
        "Safety Sign", "Fire Extinguisher",
    ],
    "air_conditioning": [
        "Fan Filter", "AC Remote", "Duct Tape",
        "Thermostat", "Window Seal",
    ],
    "small_appliances": [
        "Blender", "Toaster", "Electric Kettle",
        "Iron", "Coffee Maker", "Hand Mixer",
    ],
    "small_appliances_home_oven_and_coffee": [
        "Mini Oven", "Coffee Grinder", "Waffle Maker",
        "Rice Cooker", "Egg Boiler",
    ],
    "home_appliances": [
        "Vacuum Cleaner", "Air Purifier", "Humidifier",
        "Robot Vacuum", "Electric Heater",
    ],
    "home_appliances_2": [
        "Clothes Steamer", "Portable Washer",
        "Dehumidifier", "Water Purifier",
    ],
    "portable_kitchen_food_processors": [
        "Food Processor", "Portable Blender",
        "Chopper", "Juicer", "Spiralizer",
    ],
    "kitchen_dining_laundry_garden_furniture": [
        "Outdoor Table", "Garden Chair", "Drying Rack",
        "Laundry Basket", "Dish Drying Mat",
    ],
    "furniture_living_room": [
        "Throw Pillow", "Floor Lamp", "Side Table",
        "Bookshelf", "TV Stand",
    ],
    "furniture_bedroom": [
        "Bedside Lamp", "Wardrobe Organizer",
        "Mattress Topper", "Bed Frame Support",
    ],
    "furniture_mattress_and_upholstery": [
        "Memory Foam Pillow", "Mattress Protector",
        "Cushion Cover", "Seat Pad",
    ],
    "christmas_supplies": [
        "Christmas Lights", "Ornament Set",
        "Wreath", "Gift Wrap Roll", "Stocking",
    ],
    "costumes": [
        "Party Mask", "Cape", "Face Paint",
        "Wig", "Costume Accessory",
    ],
    "flowers": [
        "Flower Bouquet", "Potted Plant",
        "Artificial Flowers", "Flower Vase",
    ],
    "arts_and_craftmanship": [
        "Paint Set", "Canvas Board", "Yarn Ball",
        "Craft Scissors", "Sewing Kit", "Glue Gun",
    ],
    "party_supplies": [
        "Balloon Pack", "Paper Plate Set",
        "Party Banner", "Confetti", "Streamer Roll",
    ],
    "market_place": [
        "Gift Card", "Voucher", "Mystery Box",
        "Sample Pack", "Clearance Item",
    ],
    "luggage_accessories": [
        "Luggage Tag", "Travel Pillow", "Packing Cube Set",
        "Passport Holder", "Luggage Lock",
    ],
    "cine_photo": [
        "Camera Strap", "Lens Cap", "Tripod",
        "Memory Card", "Camera Bag",
    ],
    "home_comfort_2": [
        "Scented Sachet", "Room Spray",
        "Essential Oil Set", "Humidifier Pad",
    ],
    "home_confort": [
        "Throw Blanket", "Foot Rest",
        "Back Support Cushion", "Heating Pad",
    ],
    "computers": [
        "Laptop Bag", "Cooling Pad", "Privacy Screen",
        "Keyboard Cleaner", "Cable Management Kit",
    ],
    "la_cuisine": [
        "Chef Knife", "Cutting Mat", "Apron",
        "Oven Mitt", "Spice Rack",
    ],
}

# Counters per category for unique naming
_category_counters: dict[str, int] = {}


def _get_product_name(category_en: str | None, category_pt: str | None) -> str:
    """Generate a product name from category, with incrementing suffix."""
    key = category_en or category_pt or "unknown"
    candidates = CATEGORY_PRODUCT_NAMES.get(key, [])

    if key not in _category_counters:
        _category_counters[key] = 0

    idx = _category_counters[key]
    _category_counters[key] += 1

    if candidates:
        base_name = candidates[idx % len(candidates)]
        seq = idx // len(candidates) + 1
        return f"{base_name} #{seq}" if seq > 1 else base_name
    else:
        # Fallback: use Portuguese category name
        return f"{category_pt or 'Item'} #{idx + 1}"


def _build_description(
    name: str,
    category_en: str | None,
    weight_g: int | None,
    length_cm: int | None,
    width_cm: int | None,
    height_cm: int | None,
    avg_price: float | None,
) -> str:
    """Generate a template-based product description."""
    parts = [f"{name} — {category_en or 'general'} category product."]

    dims: list[str] = []
    if weight_g:
        dims.append(f"Weight: {weight_g}g")
    if length_cm and width_cm and height_cm:
        dims.append(f"Dimensions: {length_cm}x{width_cm}x{height_cm}cm")
    if dims:
        parts.append(" | ".join(dims) + ".")

    if avg_price is not None:
        parts.append(f"Average price: R${avg_price:.2f}.")

    parts.append("Suitable for daily use, quality guaranteed.")
    return " ".join(parts)


async def generate(database_url: str | None = None) -> int:
    """Generate synthetic product catalog from Olist data.

    Returns the number of products inserted.
    """
    dsn = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentic_rag",
    )
    conn = await asyncpg.connect(dsn)
    try:
        # Ensure product_catalog table exists
        schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_file):
            await conn.execute(open(schema_file).read())

        # Check if already populated
        existing = await conn.fetchval("SELECT COUNT(*) FROM product_catalog")
        if existing > 0:
            print(f"product_catalog already has {existing} rows, skipping.")
            return 0

        # Query products with translation and avg price
        rows = await conn.fetch("""
            SELECT
                p.product_id,
                p.product_category_name,
                t.product_category_name_english,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                avg_prices.avg_price
            FROM olist_products p
            LEFT JOIN product_category_translation t
                ON p.product_category_name = t.product_category_name
            LEFT JOIN (
                SELECT product_id, AVG(price) AS avg_price
                FROM olist_order_items
                GROUP BY product_id
            ) avg_prices ON p.product_id = avg_prices.product_id
            ORDER BY t.product_category_name_english, p.product_id
        """)

        if not rows:
            print("No products found in olist_products. Run seed first.")
            return 0

        # Reset counters
        _category_counters.clear()

        records: list[tuple[Any, ...]] = []
        for row in rows:
            cat_en = row["product_category_name_english"]
            cat_pt = row["product_category_name"]
            name = _get_product_name(cat_en, cat_pt)
            desc = _build_description(
                name=name,
                category_en=cat_en,
                weight_g=row["product_weight_g"],
                length_cm=row["product_length_cm"],
                width_cm=row["product_width_cm"],
                height_cm=row["product_height_cm"],
                avg_price=float(row["avg_price"]) if row["avg_price"] else None,
            )
            stock = random.randint(10, 500)
            price = round(float(row["avg_price"]), 2) if row["avg_price"] else None

            records.append((
                row["product_id"],
                name,
                desc,
                stock,
                price,
                cat_en,
            ))

        # Batch insert
        await conn.executemany(
            """
            INSERT INTO product_catalog (product_id, product_name, description, stock, price, category_en)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            """,
            records,
        )

        print(f"Generated {len(records)} synthetic products in product_catalog.")
        return len(records)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(generate())
