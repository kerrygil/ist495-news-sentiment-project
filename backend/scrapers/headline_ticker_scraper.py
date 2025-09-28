import os
from datetime import datetime, timedelta
import re
from sqlalchemy.exc import IntegrityError

import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv

from data.database import SessionLocal
from models.data_models import Article, Ticker

# Load environment variables
load_dotenv()

# Create a database session
db = SessionLocal()

# Market hours restriction
now = datetime.now()
if now.weekday() >= 5 or now.hour < 9 or now.hour >= 16:
    print(f"⏱️ Skipped at {now} (outside market hours)")
    exit()

# Load valid tickers (update path to your local finviz.csv)
try:
    valid_tickers = set(pd.read_csv("data/test_finviz.csv")["Ticker"])
except Exception as e:
    print(f"❌ ERROR loading CSV: {e}")
    valid_tickers = set()

# Create scraper
scraper = cloudscraper.create_scraper()
url = "https://finviz.com/news.ashx?v=3"
response = scraper.get(url)
soup = BeautifulSoup(response.content, "html.parser")

rows = soup.find_all("tr")
print(f"Found {len(rows)} rows!")

inserted, skipped = 0, 0

for row in rows:
    ticker_tag = row.select_one('a[href^="/quote.ashx?t="]')
    headline_tag = row.find("a", class_="nn-tab-link")

    if not ticker_tag or not headline_tag:
        skipped += 1
        continue

    ticker_symbol = ticker_tag.get_text(strip=True)

    if ticker_symbol not in valid_tickers:
        skipped += 1
        continue

    headline = headline_tag.get_text(strip=True)

    if "reverse split" in headline.lower() or "stock split" in headline.lower():
        skipped += 1
        continue

    # Parse relative time
    time_tag = row.find("td")
    if time_tag:
        time_str = time_tag.get_text(strip=True).lower()
        try:
            if "min" in time_str:
                minutes = int(re.search(r"(\d+)", time_str).group(1))
                timestamp = datetime.now() - timedelta(minutes=minutes)
            elif "hour" in time_str:
                hours = int(re.search(r"(\d+)", time_str).group(1))
                timestamp = datetime.now() - timedelta(hours=hours)
            else:
                timestamp = datetime.now()
        except Exception as e:
            print(f"❌ Failed to parse time: '{time_str}' — {e}")
            skipped += 1
            continue
    else:
        skipped += 1
        continue

    if timestamp.hour < 9:
        skipped += 1
        continue

    # Ensure ticker exists in DB (create if missing)
    ticker = db.query(Ticker).filter_by(symbol=ticker_symbol).first()
    if not ticker:
        ticker = Ticker(symbol=ticker_symbol, company_name=None)
        db.add(ticker)
        db.commit()
        db.refresh(ticker)

    # Check if article already exists by URL
    article_url = f"https://finviz.com{headline_tag['href']}"
    existing_article = db.query(Article).filter_by(url=article_url).first()

    if existing_article:
        skipped += 1
        continue

    # Insert new article
    article = Article(
        ticker_id=ticker.id,
        title=headline,
        url=article_url,
        published_at=timestamp,
    )

    db.add(article)
    try:
        db.commit()
        inserted += 1
        print(f"✅ [{timestamp}] [{ticker_symbol}] {headline}")
    except IntegrityError:
        db.rollback()
        skipped += 1
        print(f"⚠️ Skipped duplicate insert for {headline}")
    except Exception as e:
        db.rollback()
        skipped += 1
        print(f"⚠️ Skipped insert due to error: {e}")

# Close DB session
db.close()
print(f"\nInserted: {inserted} rows")
print(f"Skipped: {skipped} rows")