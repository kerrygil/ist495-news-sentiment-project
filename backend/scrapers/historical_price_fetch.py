import yfinance as yf
from datetime import timedelta
import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime
from models.data_models import HistoricalPrice, Article, Ticker
from data.database import SessionLocal

def fetch_price_changes(ticker: str, published_datetime):
    """
    Fetch price changes for a ticker around the article's published_datetime.
    Returns a dict with interval, price, and percent change.
    """
    outs = {}

    # Try intraday (1m) data for last 7 days
    try:
        df = yf.download(
            ticker, 
            period="7d", 
            interval="1m", 
            progress=False, 
            auto_adjust=True
        )

        if df.empty:
            raise ValueError("No intraday data found")

        # Ensure UTC timezone
        if df.index.tz is None:
            df = df.tz_localize('UTC')
        else:
            df = df.tz_convert('UTC')

        # Find closest price at publish time
        idx = df.index.searchsorted(published_datetime)
        if idx >= len(df):
            raise ValueError("Publish datetime outside available intraday range")

        base_price = df.iloc[idx]["Close"]

        # Define time intervals
        deltas = {
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1w": timedelta(days=7),
        }

        for label, delta in deltas.items():
            t = published_datetime + delta
            pos = df.index.searchsorted(t)
            if pos >= len(df):
                pos = -1  # fallback to last available
            price = df.iloc[pos]["Close"]
            pct_change = (price - base_price) / base_price * 100
            outs[label] = {"price": float(price), "pct_change": float(pct_change)}

        # End-of-day (same date close)
        day = published_datetime.strftime("%Y-%m-%d")
        day_close = df[df.index.strftime("%Y-%m-%d") == day]["Close"]
        if not day_close.empty:
            eod_price = day_close.iloc[-1]
            eod_pct = (eod_price - base_price) / base_price * 100
            outs["EOD"] = {"price": float(eod_price), "pct_change": float(eod_pct)}

        return outs

    except Exception as e:
        print(f"⚠️ Intraday fetch failed ({e}), falling back to daily data")

        # Fallback to daily
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return {}

        # Align on daily date
        pub_date = published_datetime.date()
        if pub_date not in df.index.date:
            return {}

        base_price = df.loc[df.index.date == pub_date]["Close"].iloc[0]

        # Grab next day, 7 days later, etc.
        intervals = {
            "1d": 1,
            "1w": 7
        }
        for label, days in intervals.items():
            target_date = pub_date + timedelta(days=days)
            if target_date in df.index.date:
                price = df.loc[df.index.date == target_date]["Close"].iloc[0]
                pct_change = (price - base_price) / base_price * 100
                outs[label] = {"price": float(price), "pct_change": float(pct_change)}

        return outs

def insert_price_data(db: Session, ticker_id: int, article_id: int, price_data: dict):
    """
    Insert price data (interval, price, pct_change) into historical_prices.
    """
    inserted, skipped = 0, 0
    for interval, values in price_data.items():
        try:
            hp = HistoricalPrice(
                ticker_id=ticker_id,
                article_id=article_id,
                interval=interval,
                price=values["price"],
                pct_change=values["pct_change"]
            )
            db.add(hp)
            # db.commit()
            inserted += 1
            print(f"Inserting interval={interval}, values={values}")
        except IntegrityError:
            db.rollback()
            skipped += 1
        except Exception as e:
            db.rollback()
            skipped += 1
            print(f"⚠️ Error inserting {interval} for article {article_id}: {e}")

    return inserted, skipped

def process_articles():
    db = SessionLocal()
    articles = db.query(Article).all()
    for article in articles:
        ticker = db.query(Ticker).get(article.ticker_id)
        if not ticker:
            continue

        print(f"🔎 Fetching prices for {ticker.symbol} around {article.published_at}")
        price_data = fetch_price_changes(ticker.symbol, article.published_at)

        if price_data:
            inserted, skipped = insert_price_data(db, ticker.id, article.id, price_data)
            print(f"✅ Inserted {inserted}, Skipped {skipped} for {ticker.symbol}/{article.id}")
        else:
            print(f"⚠️ No price data found for {ticker.symbol} at {article.published_at}")
