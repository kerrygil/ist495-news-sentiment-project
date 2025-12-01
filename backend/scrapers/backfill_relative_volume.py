import pytz
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import yfinance as yf
import pandas as pd

from backend.data.database import SessionLocal
from backend.models.data_models import Ticker, HistoricalPrice, Article


EASTERN = pytz.timezone("US/Eastern")


def get_effective_trading_date(published_dt_local: datetime, available_dates):
    """
    Returns the correct date to use for relative volume:
    - Same day if article is published during market hours
    - Previous trading day if after-hours or weekend
    """
    pub_date = published_dt_local.date()
    weekday = published_dt_local.weekday()
    is_weekend = weekday >= 5
    after_hours = published_dt_local.hour >= 16

    if not is_weekend and not after_hours:
        # Market is open → use today if available
        if pub_date in available_dates:
            return pub_date

    # Otherwise: pick most recent trading day <= pub_date
    prior_dates = [d for d in available_dates if d <= pub_date]
    if prior_dates:
        return prior_dates[-1]

    # Fallback: earliest available date
    return available_dates[0]


def recompute_price_changes(symbol: str, published: datetime):
    """
    Recomputes pct changes for 1h / 4h / 1d / 1w and EOD,
    using robust logic that works for weekends, after-hours,
    and missing intraday timestamps.
    """

    try:
        intraday = yf.download(
            symbol,
            period="7d",
            interval="1m",
            auto_adjust=True,
            progress=False
        )
        if intraday.empty:
            return None

        # Always use UTC for consistency
        if intraday.index.tz is None:
            intraday.index = intraday.index.tz_localize("UTC")
        else:
            intraday.index = intraday.index.tz_convert("UTC")

        pub_utc = published.astimezone(pytz.UTC)

        # Find closest baseline price
        diffs = abs(intraday.index - pub_utc)
        base_price = float(intraday.iloc[diffs.argmin()]["Close"])

        deltas = {
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(days=7)
        }

        results = {}

        for label, delta in deltas.items():
            target = pub_utc + delta

            diffs = abs(intraday.index - target)
            price = float(intraday.iloc[diffs.argmin()]["Close"])

            pct = (price - base_price) / base_price * 100
            results[label] = pct

        # EOD processing
        pub_local = published.astimezone(EASTERN)
        day_str = pub_local.strftime("%Y-%m-%d")
        day_rows = intraday[intraday.index.tz_convert(EASTERN).strftime("%Y-%m-%d") == day_str]

        if not day_rows.empty:
            eod_price = float(day_rows.iloc[-1]["Close"])
            results["EOD"] = (eod_price - base_price) / base_price * 100

        return results

    except Exception as e:
        print(f"Error recomputing changes for {symbol}: {e}")
        return None


def recompute_relative_volume(symbol: str, published: datetime):
    """Recomputes relative volume with weekend/after-hours logic."""
    try:
        hist = yf.Ticker(symbol).history(period="1mo", interval="1d")

        if hist.empty or "Volume" not in hist.columns:
            return None

        # Convert index to normalized dates
        hist.index = pd.to_datetime(hist.index)
        available_dates = [d.date() for d in hist.index]

        published_et = published.astimezone(EASTERN)
        effective_date = get_effective_trading_date(published_et, available_dates)

        # Select correct day's volume
        vols = hist.loc[hist.index.date == effective_date, "Volume"]
        if vols.empty:
            return None

        recent_vol = vols.iloc[-1]
        avg_vol = hist["Volume"].tail(20).mean()

        if avg_vol and avg_vol > 0:
            return float(recent_vol / avg_vol)

        return None

    except Exception as e:
        print(f"Relative volume error for {symbol}: {e}")
        return None


def backfill_all():
    db: Session = SessionLocal()

    rows = db.query(HistoricalPrice).all()
    print(f"Backfilling {len(rows)} HistoricalPrice entries...")

    for row in rows:
        ticker = db.query(Ticker).filter(Ticker.id == row.ticker_id).first()
        if not ticker:
            continue

        article = db.get(Article, row.article_id)
        if not article:
            continue
        published = article.published_at

        pct_changes = recompute_price_changes(ticker.symbol, published)
        if pct_changes:
            for key, pct in pct_changes.items():
                setattr(row, f"pct_change_{key}", pct)

        rvol = recompute_relative_volume(ticker.symbol, published)
        row.relative_volume = rvol

        db.commit()

        print(f"[{ticker.symbol}] updated pct changes + rvol={rvol}")

    db.close()
    print("Backfill complete.")


if __name__ == "__main__":
    backfill_all()
