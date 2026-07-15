"""
Seed the inventory database with sample products.

Usage:
    python scripts/seed_data.py [--mongo MONGO_URI] [--es ES_URI]
"""
import argparse
import os
import uuid
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from elasticsearch import Elasticsearch

SAMPLE_PRODUCTS = [
    {
        "product_name": "Laptop Pro 15",
        "product_category": "Electronics",
        "price": 1299.99,
        "available_quantity": 45,
        "description": "High-performance laptop with 15-inch display, 16GB RAM, and 512GB SSD for professionals.",
    },
    {
        "product_name": "Wireless Headphones",
        "product_category": "Electronics",
        "price": 199.99,
        "available_quantity": 120,
        "description": "Noise-cancelling wireless headphones with 30-hour battery life and premium sound quality.",
    },
    {
        "product_name": "USB-C Hub 7-in-1",
        "product_category": "Electronics",
        "price": 49.99,
        "available_quantity": 200,
        "description": "Versatile USB-C hub with HDMI, USB 3.0 ports, SD card reader, and 100W power delivery.",
    },
    {
        "product_name": "Men's Running Jacket",
        "product_category": "Clothing",
        "price": 89.99,
        "available_quantity": 75,
        "description": "Lightweight waterproof running jacket with reflective strips, ideal for outdoor exercise.",
    },
    {
        "product_name": "Women's Yoga Pants",
        "product_category": "Clothing",
        "price": 59.99,
        "available_quantity": 150,
        "description": "Stretchy high-waist yoga pants with moisture-wicking fabric and deep pockets.",
    },
    {
        "product_name": "Cotton Crew-Neck T-Shirt",
        "product_category": "Clothing",
        "price": 19.99,
        "available_quantity": 500,
        "description": "Classic unisex cotton t-shirt available in multiple colours, soft and durable.",
    },
    {
        "product_name": "Clean Code",
        "product_category": "Books",
        "price": 34.99,
        "available_quantity": 60,
        "description": "Robert C. Martin's guide to writing clean, maintainable, and professional software code.",
    },
    {
        "product_name": "The Pragmatic Programmer",
        "product_category": "Books",
        "price": 39.99,
        "available_quantity": 40,
        "description": "A timeless guide covering software craftsmanship, career tips, and pragmatic development.",
    },
    {
        "product_name": "Organic Arabica Coffee Beans",
        "product_category": "Food",
        "price": 14.99,
        "available_quantity": 300,
        "description": "Single-origin organic arabica coffee beans, medium roast with notes of chocolate and citrus.",
    },
    {
        "product_name": "Extra Virgin Olive Oil 500ml",
        "product_category": "Food",
        "price": 12.99,
        "available_quantity": 180,
        "description": "Cold-pressed extra virgin olive oil from Spanish olives, ideal for cooking and dressings.",
    },
    {
        "product_name": "Cordless Power Drill",
        "product_category": "Tools",
        "price": 119.99,
        "available_quantity": 55,
        "description": "20V cordless drill with 2-speed settings, 13mm keyless chuck, and two lithium-ion batteries.",
    },
    {
        "product_name": "Adjustable Wrench Set",
        "product_category": "Tools",
        "price": 29.99,
        "available_quantity": 90,
        "description": "Set of three chrome-vanadium adjustable wrenches in 6-inch, 8-inch, and 10-inch sizes.",
    },
    {
        "product_name": "27-inch 4K Monitor",
        "product_category": "Electronics",
        "price": 349.99,
        "available_quantity": 35,
        "description": "27-inch IPS 4K monitor with HDR support and a 99% sRGB color-accurate panel.",
    },
    {
        "product_name": "Mechanical Keyboard",
        "product_category": "Electronics",
        "price": 129.99,
        "available_quantity": 80,
        "description": "TKL mechanical keyboard with hot-swappable switches and per-key RGB lighting.",
    },
    {
        "product_name": "Wireless Mouse",
        "product_category": "Electronics",
        "price": 24.99,
        "available_quantity": 220,
        "description": "Ergonomic wireless mouse with silent clicks and a 2-year battery life.",
    },
    {
        "product_name": "Portable Bluetooth Speaker",
        "product_category": "Electronics",
        "price": 79.99,
        "available_quantity": 140,
        "description": "Waterproof portable speaker with 20 hours of playback and deep bass.",
    },
    {
        "product_name": "Smartwatch Series 5",
        "product_category": "Electronics",
        "price": 249.99,
        "available_quantity": 65,
        "description": "Fitness-focused smartwatch with heart-rate monitoring and 5-day battery life.",
    },
    {
        "product_name": "10000mAh Power Bank",
        "product_category": "Electronics",
        "price": 34.99,
        "available_quantity": 300,
        "description": "Compact power bank with fast charging for phones and tablets.",
    },
    {
        "product_name": "Men's Denim Jeans",
        "product_category": "Clothing",
        "price": 54.99,
        "available_quantity": 180,
        "description": "Classic straight-fit denim jeans made from durable stretch cotton.",
    },
    {
        "product_name": "Women's Wool Sweater",
        "product_category": "Clothing",
        "price": 64.99,
        "available_quantity": 95,
        "description": "Soft merino wool sweater with a relaxed fit, perfect for layering.",
    },
    {
        "product_name": "Unisex Baseball Cap",
        "product_category": "Clothing",
        "price": 17.99,
        "available_quantity": 400,
        "description": "Adjustable cotton twill baseball cap with embroidered eyelets.",
    },
    {
        "product_name": "Waterproof Hiking Boots",
        "product_category": "Clothing",
        "price": 119.99,
        "available_quantity": 70,
        "description": "Rugged waterproof hiking boots with reinforced ankle support and grip soles.",
    },
    {
        "product_name": "Merino Wool Socks (3-pack)",
        "product_category": "Clothing",
        "price": 22.99,
        "available_quantity": 260,
        "description": "Cushioned merino wool socks, moisture-wicking and odor-resistant.",
    },
    {
        "product_name": "Winter Puffer Jacket",
        "product_category": "Clothing",
        "price": 149.99,
        "available_quantity": 55,
        "description": "Insulated puffer jacket rated for sub-zero temperatures with a packable hood.",
    },
    {
        "product_name": "Atomic Habits",
        "product_category": "Books",
        "price": 24.99,
        "available_quantity": 150,
        "description": "James Clear's guide to building good habits and breaking bad ones.",
    },
    {
        "product_name": "Designing Data-Intensive Applications",
        "product_category": "Books",
        "price": 49.99,
        "available_quantity": 45,
        "description": "Martin Kleppmann's deep dive into the architecture of reliable, scalable data systems.",
    },
    {
        "product_name": "The Hobbit",
        "product_category": "Books",
        "price": 14.99,
        "available_quantity": 200,
        "description": "J.R.R. Tolkien's classic tale of Bilbo Baggins' unexpected journey.",
    },
    {
        "product_name": "Sapiens",
        "product_category": "Books",
        "price": 21.99,
        "available_quantity": 120,
        "description": "Yuval Noah Harari's sweeping history of humankind, from foragers to algorithms.",
    },
    {
        "product_name": "Cooking for Beginners",
        "product_category": "Books",
        "price": 27.99,
        "available_quantity": 85,
        "description": "An illustrated cookbook covering essential techniques for the home kitchen.",
    },
    {
        "product_name": "Dark Roast Whole Bean Coffee",
        "product_category": "Food",
        "price": 16.99,
        "available_quantity": 260,
        "description": "Bold dark roast whole bean coffee sourced from Central American farms.",
    },
    {
        "product_name": "Raw Wildflower Honey 16oz",
        "product_category": "Food",
        "price": 11.99,
        "available_quantity": 190,
        "description": "Unfiltered raw honey harvested from wildflower meadows.",
    },
    {
        "product_name": "Himalayan Pink Salt 2lb",
        "product_category": "Food",
        "price": 8.99,
        "available_quantity": 240,
        "description": "Coarse-grain Himalayan pink salt, mineral-rich and unrefined.",
    },
    {
        "product_name": "Dark Chocolate Almonds 12oz",
        "product_category": "Food",
        "price": 9.99,
        "available_quantity": 320,
        "description": "Roasted almonds coated in rich 70% dark chocolate.",
    },
    {
        "product_name": "Organic Green Tea (50 bags)",
        "product_category": "Food",
        "price": 13.99,
        "available_quantity": 210,
        "description": "Organic loose-leaf green tea in individually wrapped bags.",
    },
    {
        "product_name": "Aged Balsamic Vinegar 250ml",
        "product_category": "Food",
        "price": 18.99,
        "available_quantity": 130,
        "description": "Slow-aged balsamic vinegar from Modena with a rich, syrupy finish.",
    },
    {
        "product_name": "18V Impact Driver",
        "product_category": "Tools",
        "price": 89.99,
        "available_quantity": 60,
        "description": "Compact impact driver with brushless motor and 3-speed settings.",
    },
    {
        "product_name": "24-inch Tool Chest",
        "product_category": "Tools",
        "price": 199.99,
        "available_quantity": 30,
        "description": "Rolling steel tool chest with ball-bearing drawer slides and a locking lid.",
    },
    {
        "product_name": "Laser Level",
        "product_category": "Tools",
        "price": 44.99,
        "available_quantity": 75,
        "description": "Self-leveling cross-line laser level with a magnetic mounting bracket.",
    },
    {
        "product_name": "Digital Multimeter",
        "product_category": "Tools",
        "price": 32.99,
        "available_quantity": 110,
        "description": "Auto-ranging digital multimeter for voltage, current, and resistance testing.",
    },
    {
        "product_name": "Safety Glasses (3-pack)",
        "product_category": "Tools",
        "price": 12.99,
        "available_quantity": 300,
        "description": "Anti-fog safety glasses with UV protection, sold as a pack of three.",
    },
    {
        "product_name": "Memory Foam Pillow",
        "product_category": "Home",
        "price": 39.99,
        "available_quantity": 160,
        "description": "Contoured memory foam pillow with a cooling gel-infused cover.",
    },
    {
        "product_name": "Ceramic Non-Stick Cookware Set",
        "product_category": "Home",
        "price": 149.99,
        "available_quantity": 50,
        "description": "10-piece ceramic non-stick cookware set, oven-safe up to 450°F.",
    },
    {
        "product_name": "Scented Soy Candle Trio",
        "product_category": "Home",
        "price": 29.99,
        "available_quantity": 190,
        "description": "Three hand-poured soy candles in vanilla, sandalwood, and citrus scents.",
    },
    {
        "product_name": "Cotton Bath Towel Set",
        "product_category": "Home",
        "price": 44.99,
        "available_quantity": 140,
        "description": "6-piece 100% cotton bath towel set, quick-dry and highly absorbent.",
    },
    {
        "product_name": "Robot Vacuum Cleaner",
        "product_category": "Home",
        "price": 279.99,
        "available_quantity": 40,
        "description": "Smart robot vacuum with mapping navigation and app-based scheduling.",
    },
    {
        "product_name": "Adjustable Desk Lamp",
        "product_category": "Home",
        "price": 34.99,
        "available_quantity": 175,
        "description": "LED desk lamp with adjustable brightness, color temperature, and USB charging port.",
    },
    {
        "product_name": "Yoga Mat",
        "product_category": "Sports",
        "price": 27.99,
        "available_quantity": 210,
        "description": "Extra-thick non-slip yoga mat with a carrying strap.",
    },
    {
        "product_name": "Adjustable Dumbbell Set",
        "product_category": "Sports",
        "price": 189.99,
        "available_quantity": 45,
        "description": "Space-saving adjustable dumbbells, 5 to 52.5 lbs per hand.",
    },
    {
        "product_name": "Insulated Water Bottle 32oz",
        "product_category": "Sports",
        "price": 24.99,
        "available_quantity": 260,
        "description": "Double-wall vacuum-insulated stainless steel bottle, keeps drinks cold 24 hours.",
    },
    {
        "product_name": "Resistance Bands Set",
        "product_category": "Sports",
        "price": 19.99,
        "available_quantity": 230,
        "description": "Five-band resistance set with door anchor and carrying pouch.",
    },
    {
        "product_name": "Trail Running Backpack",
        "product_category": "Sports",
        "price": 69.99,
        "available_quantity": 90,
        "description": "12L hydration-compatible running backpack with reflective trim.",
    },
    {
        "product_name": "Foam Roller",
        "product_category": "Sports",
        "price": 21.99,
        "available_quantity": 170,
        "description": "High-density foam roller for muscle recovery and myofascial release.",
    },
    {
        "product_name": "Building Blocks Set (500pc)",
        "product_category": "Toys",
        "price": 44.99,
        "available_quantity": 130,
        "description": "500-piece interlocking building block set compatible with major brands.",
    },
    {
        "product_name": "Remote Control Car",
        "product_category": "Toys",
        "price": 59.99,
        "available_quantity": 85,
        "description": "All-terrain remote control car with a rechargeable battery and 30-minute runtime.",
    },
    {
        "product_name": "1000-Piece Jigsaw Puzzle",
        "product_category": "Toys",
        "price": 16.99,
        "available_quantity": 190,
        "description": "1000-piece jigsaw puzzle featuring a detailed world map illustration.",
    },
    {
        "product_name": "Plush Teddy Bear",
        "product_category": "Toys",
        "price": 19.99,
        "available_quantity": 220,
        "description": "Soft plush teddy bear, 18 inches tall, machine washable.",
    },
    {
        "product_name": "Board Game Night Bundle",
        "product_category": "Toys",
        "price": 54.99,
        "available_quantity": 70,
        "description": "Bundle of three family board games for game night.",
    },
    {
        "product_name": "Hydrating Face Serum",
        "product_category": "Beauty",
        "price": 32.99,
        "available_quantity": 150,
        "description": "Hyaluronic acid face serum for deep hydration and a smoother complexion.",
    },
    {
        "product_name": "Electric Toothbrush",
        "product_category": "Beauty",
        "price": 49.99,
        "available_quantity": 120,
        "description": "Rechargeable electric toothbrush with three cleaning modes and a travel case.",
    },
    {
        "product_name": "Bamboo Hair Brush",
        "product_category": "Beauty",
        "price": 13.99,
        "available_quantity": 260,
        "description": "Eco-friendly bamboo hair brush with soft boar bristles.",
    },
    {
        "product_name": "SPF 50 Sunscreen Lotion",
        "product_category": "Beauty",
        "price": 15.99,
        "available_quantity": 300,
        "description": "Broad-spectrum SPF 50 sunscreen lotion, lightweight and non-greasy.",
    },
    {
        "product_name": "Ergonomic Office Chair",
        "product_category": "Office",
        "price": 229.99,
        "available_quantity": 55,
        "description": "Mesh-back ergonomic office chair with adjustable lumbar support and armrests.",
    },
    {
        "product_name": "Standing Desk Converter",
        "product_category": "Office",
        "price": 159.99,
        "available_quantity": 65,
        "description": "Height-adjustable standing desk converter that fits over an existing desk.",
    },
    {
        "product_name": "Wireless Charging Pad",
        "product_category": "Office",
        "price": 22.99,
        "available_quantity": 240,
        "description": "10W fast wireless charging pad compatible with most phone cases.",
    },
    {
        "product_name": "Noise-Cancelling Desk Fan",
        "product_category": "Office",
        "price": 39.99,
        "available_quantity": 130,
        "description": "Whisper-quiet desk fan with three speed settings and USB power.",
    },
]


def seed(mongo_uri, es_uri, mongo_username=None, mongo_password=None):
    # --- MongoDB ---
    kwargs = {}
    if mongo_username and mongo_password:
        kwargs = {"username": mongo_username, "password": mongo_password, "authSource": "admin"}
    client = MongoClient(mongo_uri, **kwargs)
    db = client.get_default_database()
    col = db["products"]

    col.drop()  # clear existing data
    print("Cleared existing products from MongoDB.")

    # Mirrors app.services.mongo_service.ensure_indexes(): this script runs
    # against a real MongoClient directly (no Flask app context), so it
    # can't call that function, but a fresh collection from col.drop()
    # needs the same indexes recreated here for a seeded deployment to get
    # the same query performance/uniqueness guarantees the app relies on.
    col.create_index("product_id", unique=True)
    col.create_index("product_name")
    col.create_index("product_category")
    col.create_index("price")
    col.create_index("available_quantity")
    col.create_index("created_at")
    col.create_index("updated_at")
    col.create_index([("product_category", 1), ("price", 1)])
    db["price_history"].create_index([("product_id", 1), ("changed_at", -1)])
    print("Created indexes on products and price_history.")

    now = datetime.now(timezone.utc).isoformat()
    products = []
    for p in SAMPLE_PRODUCTS:
        p["product_id"] = str(uuid.uuid4())
        p["created_at"] = now
        p["updated_at"] = now
        products.append(p)

    col.insert_many(products)
    print(f"Inserted {len(products)} products into MongoDB.")

    # --- Elasticsearch ---
    es = Elasticsearch(es_uri)

    # Recreate index
    if es.indices.exists(index="products"):
        es.indices.delete(index="products")

    es.indices.create(
        index="products",
        mappings={
            "properties": {
                "product_id": {"type": "keyword"},
                "product_name": {"type": "text"},
                "product_category": {"type": "keyword"},
                "description": {"type": "text"},
                "price": {"type": "float"},
            }
        },
    )

    for p in products:
        es.index(
            index="products",
            id=p["product_id"],
            document={
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "product_category": p["product_category"],
                "description": p["description"],
                "price": p["price"],
            },
        )

    es.indices.refresh(index="products")
    print(f"Indexed {len(products)} products into Elasticsearch.")
    print("Seeding complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mongo", default=os.getenv("MONGO_URI", "mongodb://localhost:27017/inventory"))
    parser.add_argument("--es", default=os.getenv("ES_URI", "http://localhost:9200"))
    parser.add_argument("--mongo-username", default=os.getenv("MONGO_USERNAME"))
    parser.add_argument("--mongo-password", default=os.getenv("MONGO_PASSWORD"))
    args = parser.parse_args()

    try:
        seed(args.mongo, args.es, mongo_username=args.mongo_username, mongo_password=args.mongo_password)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
