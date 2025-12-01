import os
import sys
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from datetime import datetime, timedelta
from typing import Dict, Optional
import time
import pytz
import yfinance as yf
import pandas as pd
import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.data.database import SessionLocal, engine
from backend.models.data_models import Article, Ticker, HistoricalPrice  

EASTERN = pytz.timezone("US/Eastern")
UTC = pytz.UTC

# Constants
INTRADAY_LOOKBACK_DAYS = 2       # how many days of intraday to fetch
INTRADAY_INTERVALS = ["1m", "5m", "15m", "30m", "60m"]
INTRADAY_ACCEPTANCE_WINDOW = pd.Timedelta(minutes=60)  # how far from publish we accept a tick
DAILY_PERIOD = "1y"
REL_VOL_TAIL = 20

from zoneinfo import ZoneInfo

def normalize_timestamp(ts):
    if ts.tzinfo is None:
        # Stored naive → assume US/Eastern
        ts = ts.replace(tzinfo=ZoneInfo("US/Eastern"))
    return ts.astimezone(ZoneInfo("UTC"))

def _ensure_tz_eastern(dt: datetime) -> datetime:
    """Return timezone-aware datetime in US/Eastern (assumes naive -> Eastern)."""
    if dt.tzinfo is None:
        return EASTERN.localize(dt)
    return dt.astimezone(EASTERN)

def _safe_pct(new: Optional[float], base: Optional[float]) -> Optional[float]:
    if base is None or new is None or base == 0:
        return None
    try:
        return float((new - base) / base * 100)
    except Exception:
        return None


def _fetch_daily_df(ticker: str, period: str = DAILY_PERIOD) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        print(f"Daily fetch error for {ticker}: {e}")
        return None

def _fetch_intraday_window(ticker: str, publish_utc: datetime, interval: str, lookback_days=2) -> Optional[pd.DataFrame]:
    try:
        start_dt = publish_utc - timedelta(days=lookback_days)
        end_dt = publish_utc + timedelta(days=1)

        # ensure tz-aware UTC datetimes
        if start_dt.tzinfo is None:
            start_dt = UTC.localize(start_dt)
        if end_dt.tzinfo is None:
            end_dt = UTC.localize(end_dt)

        df = yf.download(
            ticker,
            start=start_dt,
            end=end_dt,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return None

        # normalize index to UTC tz
        try:
            if df.index.tz is None:
                df.index = df.index.tz_localize(UTC)
            else:
                df.index = df.index.tz_convert(UTC)
        except Exception:
            df.index = pd.to_datetime(df.index).tz_localize(UTC)

        return df
    except Exception as e:
        print(f"Intraday fetch error for {ticker} interval={interval}: {e}")
        return None

def _find_price_near_timestamp(df: pd.DataFrame, target_utc: datetime, acceptance: pd.Timedelta) -> Optional[float]:
    """Return Close price for nearest index point within acceptance window, else None."""
    if df is None or df.empty:
        return None

    # Ensure df.index is UTC-aware
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    else:
        df = df.tz_convert("UTC")

    # Ensure target is UTC-aware
    if target_utc.tzinfo is None:
        target_utc = target_utc.replace(tzinfo=pytz.timezone("UTC"))
    else:
        target_utc = target_utc.astimezone(pytz.timezone("UTC"))

    # Compute distances
    diffs = (df.index - target_utc)
    # diffs is a TimedeltaIndex; take absolute values robustly
    try:
        diffs = pd.to_timedelta(diffs).to_series().abs()
    except Exception:
        diffs = pd.to_timedelta(diffs).abs()

    # Find the closest timestamp (robust positional argmin)
    if len(diffs) == 0:
        return None
    pos = int(diffs.argmin())
    best_ts = df.index[pos]
    best_diff = diffs[pos]

    if best_diff <= acceptance:
        # handle possible multiple rows for the same timestamp
        val = df.loc[best_ts, "Close"]
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        elif isinstance(val, np.ndarray) or isinstance(val, list):
            val = val[-1]
        return float(val)
    return None

def _compute_relative_volume_from_daily(daily_df: pd.DataFrame, chosen_date: datetime.date) -> Optional[float]:
    """Compute relative volume for chosen_date (date object) using 20-day average."""
    if daily_df is None or daily_df.empty or "Volume" not in daily_df.columns:
        return None
    vols = daily_df["Volume"].dropna()
    if vols.empty:
        return None
    # find rows for chosen_date (if not available, pick next trading date >= chosen_date else previous)
    dates = [d.date() for d in daily_df.index]
    if chosen_date in dates:
        vols_on = daily_df.loc[[i for i in daily_df.index if i.date() == chosen_date], "Volume"]
        recent_vol = float(vols_on.iloc[0]) if not vols_on.empty else None
    else:
        future = [d for d in dates if d >= chosen_date]
        past = [d for d in dates if d <= chosen_date]
        pick = None
        if future:
            pick = future[0]
        elif past:
            pick = past[-1]
        else:
            pick = None
        if pick is None:
            return None
        vols_on = daily_df.loc[[i for i in daily_df.index if i.date() == pick], "Volume"]
        if not vols_on.empty:
            recent_val = vols_on.iloc[0]
            recent_vol = float(recent_val) if np.isscalar(recent_val) else float(recent_val.item())
        else:
            recent_vol = None

    tail = vols.tail(REL_VOL_TAIL)
    avg_val = tail.mean() if not tail.empty else None
    if avg_val is None:
        avg_vol = None
    else:
        # mean() can be scalar or 0-d ndarray / Series depending on pandas version
        if np.isscalar(avg_val):
            avg_vol = float(avg_val)
        else:
            # try common extraction methods
            try:
                avg_vol = float(avg_val.iloc[0])
            except Exception:
                try:
                    avg_vol = float(np.asarray(avg_val).item())
                except Exception:
                    avg_vol = None
    if recent_vol is None or avg_vol is None or avg_vol == 0:
        return None
    return float(recent_vol / avg_vol)


def fetch_price_changes(ticker: str, published_datetime: datetime) -> Dict[str, Dict]:
    """
    Return dict mapping intervals to {"price": float, "pct_change": float, "relative_volume": float|None}
    Always returns 'since_open' when possible (pct change from market open to price at publish).
    Also attempts to compute 1h/4h/1d/1w/EOD when possible (intraday/daily fallback).
    """
    outs: Dict[str, Dict] = {}

    # Normalize times
    pub_eastern = _ensure_tz_eastern(published_datetime)
    pub_utc = normalize_timestamp(published_datetime)
    pub_date = pub_eastern.date()
    in_market_hours = (pub_eastern.weekday() < 5 and pub_eastern.time() >= datetime(pub_eastern.year, pub_eastern.month, pub_eastern.day, 9, 30).time() and pub_eastern.time() <= datetime(pub_eastern.year, pub_eastern.month, pub_eastern.day, 16, 0).time())

    # 1) Fetch daily data (required)
    daily_df = _fetch_daily_df(ticker)
    if daily_df is None:
        print(f"[{ticker}] no daily data available → aborting fetch_price_changes")
        return {}

    # compute relative_volume using daily logic (choose vol_date sensibly)
    try:
        if in_market_hours and any(d.date() == pub_date for d in daily_df.index):
            vol_date = pub_date
        else:
            # prefer the next trading day >= pub_date (market will produce volume then), else last available
            dates = sorted({d.date() for d in daily_df.index})
            future = [d for d in dates if d >= pub_date]
            vol_date = future[0] if future else (dates[-1] if dates else None)

        relative_volume = _compute_relative_volume_from_daily(daily_df, vol_date) if vol_date else None
    except Exception as e:
        print(f"[{ticker}] relative volume calc failed: {e}")
        relative_volume = None

    # 2) Determine market-open price for pub_date (baseline)
    open_price = None
    try:
        # prefer Open of same calendar date if available. If not present, pick closest trading day <= pub_date else next.
        available_dates = sorted({d.date() for d in daily_df.index})
        if pub_date in available_dates:
            rows = daily_df.loc[daily_df.index.date == pub_date, "Open"]
            if not rows.empty:
                open_price = float(rows.iloc[0])
        else:
            prev = [d for d in available_dates if d <= pub_date]
            nxt = [d for d in available_dates if d >= pub_date]
            chosen = prev[-1] if prev else (nxt[0] if nxt else None)
            if chosen:
                rows = daily_df.loc[daily_df.index.date == chosen, "Open"]
                if not rows.empty:
                    open_price = float(rows.iloc[0])
    except Exception as e:
        print(f"[{ticker}] open_price failed: {e}")
        open_price = None

    # If we don't have an open_price we cannot compute since_open; bail early
    if open_price is None:
        print(f"[{ticker}] no open price for {pub_date}, aborting")
        return {}

    # 3) Try to get price_at_publish by probing intraday intervals
    price_at_publish = None
    intraday_df_for_short_intervals = None
    for intrv in INTRADAY_INTERVALS:
        intr = _fetch_intraday_window(ticker, pub_utc, intrv)
        if intr is None:
            continue
        # find a tick close to pub_utc
        p = _find_price_near_timestamp(intr, pub_utc, INTRADAY_ACCEPTANCE_WINDOW)
        if p is not None:
            price_at_publish = p
            intraday_df_for_short_intervals = intr
            break
        # if none found, keep the last fetched as possible resource for forward intervals
        if intraday_df_for_short_intervals is None:
            intraday_df_for_short_intervals = intr

    # fallback if no intraday price: use same-day daily close if available
    if price_at_publish is None:
        try:
            # use same-day close if exists, else closest available trading date close
            if any(d.date() == pub_date for d in daily_df.index):
                close_rows = daily_df.loc[daily_df.index.date == pub_date, "Close"]
                if not close_rows.empty:
                    price_at_publish = float(close_rows.iloc[0])
            else:
                # pick nearest trading date
                dates = sorted({d.date() for d in daily_df.index})
                # prefer prev day
                prev = [d for d in dates if d <= pub_date]
                nxt = [d for d in dates if d >= pub_date]
                chosen = prev[-1] if prev else (nxt[0] if nxt else None)
                if chosen:
                    close_rows = daily_df.loc[daily_df.index.date == chosen, "Close"]
                    if not close_rows.empty:
                        price_at_publish = float(close_rows.iloc[0])
        except Exception:
            price_at_publish = None

    # Now compute since_open
    since_open_pct = _safe_pct(price_at_publish, open_price) if price_at_publish is not None else None
    if price_at_publish is not None:
        outs["since_open"] = {
            "price": float(price_at_publish),
            "pct_change": since_open_pct,
            "relative_volume": relative_volume,
            "note": "baseline=open_of_day"
        }

    # 4) Short term intervals (1h, 4h) from intraday if present
    if intraday_df_for_short_intervals is not None:
        df = intraday_df_for_short_intervals
        # best effort: compute 1h & 4h using the intraday index (find forward index points)
        for label, td in (("1h", timedelta(hours=1)), ("4h", timedelta(hours=4))):
            target = pub_utc + td
            # prefer first index >= target else last index
            fwd = df.index[df.index >= target]
            if len(fwd) > 0:
                pos = fwd[0]
            else:
                pos = df.index[-1]
            try:
                price = float(df.loc[pos, "Close"])
                outs[label] = {"price": price, "pct_change": _safe_pct(price, price_at_publish or open_price), "relative_volume": relative_volume}
            except Exception:
                pass

    # 5) Longer term intervals (1d, 1w, EOD) from daily_df
    try:
        daily_dates = sorted({d.date() for d in daily_df.index})
        # EOD: use same date close if available else nearest
        eod_date = None
        if pub_date in daily_dates:
            eod_date = pub_date
        else:
            future = [d for d in daily_dates if d >= pub_date]
            past = [d for d in daily_dates if d <= pub_date]
            eod_date = future[0] if future else (past[-1] if past else None)

        if eod_date:
            rows = daily_df.loc[daily_df.index.date == eod_date, "Close"]
            if not rows.empty:
                eod_price = float(rows.iloc[0])
                outs["EOD"] = {"price": eod_price, "pct_change": _safe_pct(eod_price, price_at_publish or open_price), "relative_volume": relative_volume}
        # 1d and 1w: next trading date >= pub_date + days
        def find_trading_on_or_after(target_date):
            future = [d for d in daily_dates if d >= target_date]
            return future[0] if future else None

        for label, days in (("1d", 1), ("1w", 7)):
            target_date = pub_date + timedelta(days=days)
            trade_date = find_trading_on_or_after(target_date)
            if trade_date:
                rows = daily_df.loc[daily_df.index.date == trade_date, "Close"]
                if not rows.empty:
                    price = float(rows.iloc[0])
                    outs[label] = {"price": price, "pct_change": _safe_pct(price, price_at_publish or open_price), "relative_volume": relative_volume}
    except Exception as e:
        print(f"{ticker} daily intervals failed: {e}")

    # finalize numeric types and return
    for k, v in list(outs.items()):
        if "price" in v and v["price"] is not None:
            v["price"] = float(v["price"])
        if "pct_change" in v and v["pct_change"] is not None:
            v["pct_change"] = float(v["pct_change"])
        if "relative_volume" in v and v["relative_volume"] is not None:
            v["relative_volume"] = float(v["relative_volume"])
    return outs

def insert_price_data(db: Session, ticker_id: int, article_id: int, price_data: Dict[str, Dict]):
    """
    Insert price rows into HistoricalPrice table. Only inserts intervals that do not exist.
    If an interval exists and relative_volume is None while new data has it, update that field.
    """
    inserted, updated, skipped = 0, 0, 0
    for interval, values in price_data.items():
        if "price" not in values and "pct_change" not in values:
            continue
        existing = db.query(HistoricalPrice).filter_by(
            ticker_id=ticker_id,
            article_id=article_id,
            interval=interval
        ).first()
        if existing:
            # update relative_volume if missing
            if (existing.relative_volume is None) and ("relative_volume" in values):
                existing.relative_volume = values.get("relative_volume")
                db.add(existing)
                updated += 1
            else:
                skipped += 1
            continue
        try:
            hp = HistoricalPrice(
                ticker_id=ticker_id,
                article_id=article_id,
                interval=interval,
                price=values.get("price"),
                pct_change=values.get("pct_change"),
                relative_volume=values.get("relative_volume"),
            )
            db.add(hp)
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1
        except Exception as e:
            db.rollback()
            print(f"Insertion error for {ticker_id}/{article_id}/{interval}: {e}")
            skipped += 1
    db.commit()
    return inserted, updated, skipped


def process_articles(batch_limit: Optional[int] = None):
    db = SessionLocal()
    articles = db.query(Article).order_by(Article.published_at.desc()).all()
    count = 0
    for article in articles:
        # skip articles already with enough price rows (optional)
        existing_count = db.query(HistoricalPrice).filter(HistoricalPrice.article_id == article.id).count()
        if existing_count > 0 and article.published_at is not None:
            # If you want to re-run incomplete ones only:
            missing_relvol = db.query(HistoricalPrice).filter(HistoricalPrice.article_id == article.id, HistoricalPrice.relative_volume.is_(None)).count()
            if missing_relvol == 0:
                continue

        ticker = db.query(Ticker).get(article.ticker_id)
        if not ticker:
            continue

        print(f"Fetching prices for {ticker.symbol} around {article.published_at} (id={article.id})")
        price_data = fetch_price_changes(ticker.symbol, article.published_at)
        if price_data:
            ins, upd, skip = insert_price_data(db, ticker.id, article.id, price_data)
            print(f"Inserted={ins}, Updated={upd}, Skipped={skip} for {ticker.symbol}/{article.id}")
        else:
            print(f"No price data for {ticker.symbol}/{article.id}")
        count += 1
        if batch_limit and count >= batch_limit:
            break
        # small delay to avoid yfinance throttling
        time.sleep(0.5)
    db.close()

def export_prices_to_csv(): 
    df = pd.read_sql("SELECT * FROM historical_prices", engine) 
    csv_path = os.path.join(os.path.dirname(__file__), "prices.csv") 
    df.to_csv(csv_path, index=False) 
    print(f"Exported prices to {csv_path}") 
    
def main(): 
    process_articles() 
    export_prices_to_csv()
