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

import json
from dateutil import parser as dateparser

def extract_true_timestamp(article_html: str, url: str) -> datetime | None:
    soup = BeautifulSoup(article_html, "html.parser")
    
    info_div = None

    if "finviz.com" in url:
        info_div = soup.select_one("div.news-publish-info div.grow.self-center")
    if info_div:
        text = info_div.get_text(" ", strip=True)

        m = re.search(r"\|\s*(.+)$", text)
        if m:
            date_str = m.group(1)
        else:
            date_str = text

        try:
            return dateparser.parse(date_str)
        except Exception:
            pass

    meta_time = soup.find("meta", {"property": "article:published_time"})
    if meta_time and meta_time.get("content"):
        return dateparser.parse(meta_time["content"])

    meta_time = soup.find("meta", {"name": "datePublished"})
    if meta_time and meta_time.get("content"):
        return dateparser.parse(meta_time["content"])

    time_tag = soup.find("time", {"datetime": True})
    if time_tag:
        return dateparser.parse(time_tag["datetime"])

    ld_json_blocks = soup.find_all("script", {"type": "application/ld+json"})
    for block in ld_json_blocks:
        try:
            data = json.loads(block.text)
            if isinstance(data, dict):
                if "datePublished" in data:
                    return dateparser.parse(data["datePublished"])
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "datePublished" in item:
                        return dateparser.parse(item["datePublished"])
        except Exception:
            continue

    # Yahoo Finance
    yf = soup.select_one("time[data-test='article-time']")
    if yf and yf.get("datetime"):
        return dateparser.parse(yf["datetime"])

    # MarketWatch
    mw = soup.find("span", {"class": "timestamp__date"})
    if mw:
        try:
            return dateparser.parse(mw.get_text(strip=True))
        except:
            pass

    # BusinessWire / PR Newswire
    bw = soup.find("span", {"class": "bw-release-timestamp"})
    if bw:
        return dateparser.parse(bw.text.strip())

    # If everything fails:
    print(f"WARNING: No timestamp detected for article: {url}")
    return None

def main():
    # Load environment variables
    load_dotenv()

    # Create a database session
    db = SessionLocal()

    print("Tickers table count before insert:", db.query(Ticker).count())

    # Market hours restriction
    #now = datetime.now()
    #if now.weekday() >= 5 or now.hour < 9 or now.hour >= 16:
    #    print(f"Skipped at {now} (outside market hours)")
    #    return

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

        # Extract ALL ticker symbols in the row
        ticker_tags = row.select('a[href*="/quote.ashx?t="]')
        tickers = {t.get_text(strip=True).upper() for t in ticker_tags}

        if not tickers:
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

        # Insert one Article per ticker symbol found
        for ticker_symbol in tickers:

            # Check DB for ticker
            ticker = db.query(Ticker).filter_by(symbol=ticker_symbol).first()

            # If missing, create barebones ticker entry
            if not ticker:
                ticker = Ticker(symbol=ticker_symbol)
                db.add(ticker)
                db.commit()
                db.refresh(ticker)

            # Normalize URL
            article_url = headline_tag["href"]
            if not article_url.startswith("http"):
                article_url = f"https://finviz.com{article_url}"
            article_url = normalize_url(article_url)

            # Prevent duplicates
            if db.query(Article).filter_by(url=article_url, ticker_id=ticker.id).first():
                skipped += 1
                continue

            # Insert article
            article = Article(
                ticker_id=ticker.id,
                title=headline,
                url=article_url,
                published_at=timestamp,
            )

            # Try to fetch the true timestamp from article page
            true_timestamp = None
            try:
                article_html = scraper.get(article_url, timeout=10).text
                true_timestamp = extract_true_timestamp(article_html, article_url)
            except Exception as e:
                print(f"ERROR fetching article page {article_url}: {e}")

            # If real timestamp found, override BEFORE commit
            if true_timestamp:
                article.published_at = true_timestamp

            db.add(article)
            try:
                db.commit()
                inserted += 1
                print(f"[{article.published_at}] [{ticker_symbol}] {headline}")
            except IntegrityError:
                db.rollback()
                skipped += 1


    # Close DB session
    db.close()
    print(f"\nInserted: {inserted} rows")
    print(f"Skipped: {skipped} rows")

if __name__ == "__main__":
    main()