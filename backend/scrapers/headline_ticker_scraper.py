import os
import sys
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from datetime import datetime, timedelta
import re
from sqlalchemy.exc import IntegrityError

import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv

from backend.data.database import SQLALCHEMY_DATABASE_URL, SessionLocal
from backend.models.data_models import Article, Ticker

def normalize_url(url: str) -> str:
    """
    Normalize URLs so the same article doesn't get inserted twice:
    - strip trailing slashes
    - remove accidental whitespace
    - ensure consistent scheme (https)
    """
    if not isinstance(url, str):
        return url

    url = url.strip()

    # Remove trailing slash but not the domain slash
    if url.endswith("/") and len(url) > len("https://x.com/"):
        url = url[:-1]

    return url

def main():
    # Load environment variables
    load_dotenv()

    print("Using DB:", SQLALCHEMY_DATABASE_URL)
    # Create a database session
    db = SessionLocal()

    print("Tickers table count before insert:", db.query(Ticker).count())

    # Market hours restriction
    #now = datetime.now()
    #if now.weekday() >= 5 or now.hour < 9 or now.hour >= 16:
    #    print(f"Skipped at {now} (outside market hours)")
    #    return

    # Load valid tickers
    try:
        finviz_df = pd.read_csv("backend/data/finviz.csv")
        if "Ticker" not in finviz_df.columns:
            raise KeyError("Missing 'Ticker' column in finviz.csv")
        valid_tickers = set(finviz_df["Ticker"].astype(str).str.strip().str.upper())
        print(f"✅ Loaded {len(valid_tickers)} valid tickers.")
    except Exception as e:
        print(f"ERROR loading CSV: {e}")
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
        headline_tag = row.find("a", class_="nn-tab-link")
        if not headline_tag:
            skipped += 1
            continue

        headline = headline_tag.get_text(strip=True)
        if "reverse split" in headline.lower() or "stock split" in headline.lower():
            skipped += 1
            continue

        # Try to find a ticker link within the same row *after* the headline
        ticker_tag = row.find("a", href=re.compile(r"/quote\.ashx\?t="))
        ticker_symbol = None
        if ticker_tag:
            ticker_symbol = ticker_tag.get_text(strip=True).upper()

        if not ticker_symbol or ticker_symbol not in valid_tickers:
            skipped += 1
            continue

        # Parse relative time
        time_tag = row.find("td")
        if not time_tag:
            skipped += 1
            continue

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
            skipped += 1
            continue

        if timestamp.hour < 9:
            skipped += 1
            continue

        # Ensure ticker exists in DB
        ticker = db.query(Ticker).filter_by(symbol=ticker_symbol).first()
        if not ticker:
            finviz_match = finviz_df[finviz_df["Ticker"].str.upper() == ticker_symbol]
            if not finviz_match.empty:
                company_name = finviz_match.iloc[0]["Company"]
                sector = finviz_match.iloc[0]["Sector"]
                industry = finviz_match.iloc[0]["Industry"]
            else:
                company_name, sector, industry = None, None, None

            ticker = Ticker(symbol=ticker_symbol, company_name=company_name, sector=sector, industry=industry)
            db.add(ticker)
            db.commit()
            db.refresh(ticker)

        # Fix article URL (remove double finviz.com)
        href = headline_tag["href"]
        if href.startswith("http"):
            article_url = href
        else:
            article_url = f"https://finviz.com{href}"

        article_url = normalize_url(article_url)

        existing_article = db.query(Article).filter_by(url=article_url).first()
        if existing_article:
            skipped += 1
            continue

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
            print(f"[{timestamp}] [{ticker_symbol}] {headline}")
        except IntegrityError:
            db.rollback()
            skipped += 1
        except Exception as e:
            db.rollback()
            skipped += 1

    # Close DB session
    db.close()
    print(f"\nInserted: {inserted} rows")
    print(f"Skipped: {skipped} rows")

if __name__ == "__main__":
    main()