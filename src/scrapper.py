import asyncio
import json
import re
from pathlib import Path

from pydoll.browser.chromium import Edge
from pydoll.browser.options import ChromiumOptions


BASE_URL = "https://books.toscrape.com/catalogue/page-{}.html"
TARGET_COUNT = 30

# Star rating words used by the site
RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

async def scrape(limit: int = TARGET_COUNT) -> list[dict]:
    options = ChromiumOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    products = []
    page_number = 1

    browser = Edge(options=options)
    tab = await browser.start()

    try:
        while len(products) < limit:
            url = BASE_URL.format(page_number)
            print(f"\n[Page {page_number}] Fetching: {url}")

            await tab.go_to(url)
            await asyncio.sleep(2)

            # Each book is in an <article class="product_pod">
            articles = await tab.find(
                tag_name="article", find_all=True, raise_exc=False
            ) or []

            new_products = 0

            for article in articles:
                if len(products) >= limit:
                    break

                try:
                    # Title is in <h3><a title="...">
                    title_el = await article.query("h3 a", raise_exc=False)
                    name = ""
                    if title_el:
                        name = title_el.get_attribute("title") or ""
                    if not name:
                        continue

                    # Price is in <p class="price_color">
                    price = ""
                    try:
                        price_el = await article.query("p.price_color", raise_exc=False)
                        if price_el:
                            # Use execute_script to get the text content since
                            # get_attribute() only reads HTML attributes, not DOM properties
                            result = await price_el.execute_script(
                                "return this.textContent", return_by_value=True
                            )
                            price = (
                                result.get("result", {})
                                .get("result", {})
                                .get("value", "") or ""
                            ).strip()
                    except Exception:
                        pass

                    # Rating is a word class on <p class="star-rating One/Two/...">
                    rating = None
                    try:
                        rating_el = await article.query("p.star-rating", raise_exc=False)
                        if rating_el:
                            # class_name is the correct pydoll property (pydoll
                            # stores the HTML "class" attribute under "class_name")
                            cls = rating_el.class_name or ""
                            # cls is e.g. "star-rating Three"
                            for word, val in RATING_MAP.items():
                                if word in cls:
                                    rating = val
                                    break
                    except Exception:
                        pass

                    products.append({
                        "name": name,
                        "price": price,
                        "rating": rating,
                    })
                    new_products += 1

                except Exception as e:
                    print(f"  Error on article: {e}")

            print(f"  {new_products} new products (total: {len(products)})")

            if new_products == 0:
                print("  No products found — stopping.")
                break

            page_number += 1

    finally:
        await browser.stop()

    return products[:limit]


async def main():
    print(f"Scraping books.toscrape.com for top {TARGET_COUNT} books...\n")

    products = await scrape(limit=TARGET_COUNT)

    print(f"\n{'='*60}")
    print(f"Collected {len(products)} products.\n")

    output_path = Path(__file__).parent / "products.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {output_path}\n")

    for i, p in enumerate(products, 1):
        print(f"{i:>2}. {p['name'][:55]:<55}  Rating: {p['rating']}/5  Price: {p['price']}")


if __name__ == "__main__":
    asyncio.run(main())
