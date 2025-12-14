from datetime import datetime
from typing import Optional
from unittest import result
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from backend.models import data_models
from backend.models.data_models import HistoricalPrice, Ticker, Article
from backend.data.database import get_db
from backend.app.utils import sanitize_floats, try_float
import pandas as pd
import os
import importlib
from decimal import Decimal
import numpy as np
import subprocess
import sys

router = APIRouter()

@router.get("/test")
def read_root():
    return {"message": "Backend is running!"}

@router.get("/test-db-connection")
def test_db_connection(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        return {"status": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/tickers/")
def read_tickers(db: Session = Depends(get_db)):
    return db.query(data_models.Ticker).all()


@router.get("/cleaned_articles")
def get_cleaned_articles():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "..", "data", "cleaned_data", "articles_cleaned.csv")

    csv_path = os.path.normpath(csv_path)

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"File not found: {csv_path}")

    df = pd.read_csv(csv_path)

    data = df.head(10).to_dict(orient="records")
    return {"cleaned_articles": data}

@router.get("/aggregated_features")
def get_aggregated_features(db: Session = Depends(get_db)):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "features_aggregated.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Aggregated file not found. Run aggregate_sentiments.py first.")

    df = pd.read_csv(csv_path)

    # get ticker IDs and symbols
    tickers = db.query(Ticker.id, Ticker.symbol, Ticker.company_name).all()
    ticker_df = pd.DataFrame(tickers, columns=["ticker_id", "ticker", "company_name"])

    # get accurate article counts from the database
    article_counts = (
        db.query(Article.ticker_id, func.count(Article.id).label("article_count"))
        .group_by(Article.ticker_id)
        .all()
    )
    article_count_df = pd.DataFrame(article_counts, columns=["ticker_id", "article_count"])

    # merge everything
    df = df.merge(ticker_df, on="ticker_id", how="left")
    df = df.merge(article_count_df, on="ticker_id", how="left")

    # rename for consistency with frontend expectations
    df = df.rename(columns={
        "combined_score": "avg_combined_score"
    })

    # fill NaNs (in case some tickers have 0 articles)
    df["article_count"] = df["article_count"].fillna(0).astype(int)

    return {
        "records": df.to_dict(orient="records"),
        "summary": {
            "total_articles": int(df["article_count"].sum()),
            "accurate": int((df["sentiment_price_correlation"] == "accurate").sum()),
            "inconclusive": int((df["sentiment_price_correlation"] == "inconclusive").sum()),
            "neutral": int((df["sentiment_price_correlation"] == "neutral").sum()),
        }
    }

@router.get("/sentiment_articles")
def get_sentiment_articles():
    """Return article-level sentiment analysis results before aggregation."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "articles_sentiment.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Sentiment file not found. Run sentiment_pipeline.py first.")

    df = pd.read_csv(csv_path)
    summary = (
        df["sentiment_price_agreement"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
        .to_dict()
    )

    return {
        "records": df.head(20).to_dict(orient="records"),
        "agreement_summary": summary,
    }

@router.get("/tickers_summary")
def get_tickers_summary():
    """Return sentiment accuracy grouped by ticker."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "features_aggregated.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Aggregated file not found.")

    df = pd.read_csv(csv_path)

    summary = (
        df.groupby("ticker_id")["sentiment_price_correlation"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )

    return {"ticker_summary": summary.to_dict(orient="records")}

@router.post("/refresh_data")
def refresh_data():
    scripts = [
        "backend.scrapers.headline_ticker_scraper",
        "backend.scrapers.historical_price_fetch",
        "backend.data.cleaning_pipeline",
        "backend.data.feature_engineering",
        "backend.data.sentiment_pipeline",
        "backend.data.aggregate_sentiment",
    ]

    for module_name in scripts:
        print(f"Running {module_name}...")
        mod = importlib.import_module(module_name)
        if hasattr(mod, "main"):
            mod.main()
        else:
            raise Exception(f"{module_name} has no main() function.")
    return {"status": "success", "message": "Pipeline re-run successfully."}

@router.get("/tickers/search")
def search_ticker_full(
    q: str = Query(..., description="Search by ticker symbol or company name"),
    db: Session = Depends(get_db),
):
    """
    Search a ticker and return:
      - summary metrics (article count, averages)
      - full per-article sentiment breakdown (from aggregated CSV)
      - headline/url/published_at from DB
    """

    import pandas as pd
    import os

    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "features_aggregated.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Aggregated features file not found")

    df = pd.read_csv(csv_path)

    # Load ticker metadata
    tickers = db.query(data_models.Ticker).all()
    ticker_map = {t.id: t.symbol for t in tickers}
    name_map = {t.id: t.company_name for t in tickers}

    df["ticker_symbol"] = df["ticker_id"].map(ticker_map)
    df["ticker_name"] = df["ticker_id"].map(name_map)

    # Validate query
    q_trim = str(q).strip()
    if not q_trim:
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty")

    q_up = q_trim.upper()
    sym_col = df["ticker_symbol"].fillna("").astype(str)
    name_col = df["ticker_name"].fillna("").astype(str)

    symbol_exact = sym_col.str.upper() == q_up
    symbol_prefix = sym_col.str.upper().str.startswith(q_up)
    # Use regex=False to avoid interpreting regex meta-characters in 'q'
    name_contains = name_col.str.contains(q_trim, case=False, regex=False, na=False)

    # Prefer symbol matches (exact or prefix). Only fallback to name search when
    # there are no symbol matches. This prevents queries like "MET" matching a
    # company with "metal" in the name.
    symbol_mask = symbol_exact | symbol_prefix
    if symbol_mask.any():
        filtered = df[symbol_mask]
    else:
        filtered = df[name_contains]

    if filtered.empty:
        raise HTTPException(status_code=404, detail=f"No sentiment data found for '{q}'")

    ticker_id = int(filtered["ticker_id"].iloc[0])
    symbol = filtered["ticker_symbol"].iloc[0]
    name = filtered["ticker_name"].iloc[0]

    sentiment_summary = {
        "article_count": int(filtered["id"].nunique()) if "id" in filtered.columns else len(filtered),
        "avg_pct_change": round(float(filtered["pct_change"].mean()), 4)
            if "pct_change" in filtered.columns else None,
        "avg_relative_volume": round(float(filtered["relative_volume"].mean()), 4)
            if "relative_volume" in filtered.columns else None,
        "avg_combined_score": round(float(filtered["combined_score"].mean()), 4)
            if "combined_score" in filtered.columns else None,
        "agreement_rate": round(
            (filtered["sentiment_price_agreement"].eq("accurate").sum() / len(filtered)) * 100, 2
        ) if "sentiment_price_agreement" in filtered.columns else None,
    }

    # 1. Pull DB metadata for articles belonging to this ticker
    db_articles = (
        db.query(data_models.Article)
        .filter(data_models.Article.ticker_id == ticker_id)
        .all()
    )

    # Map article_id → DB fields
    db_map = {
        a.id: {
            "headline": a.title,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "url": a.url,
        }
        for a in db_articles
    }

    # 2. Filter CSV rows belonging to this ticker
    per_article_rows = filtered.sort_values("published_at", ascending=False)

    # 3. Merge CSV sentiment rows with DB fields
    articles = []
    for _, row in per_article_rows.iterrows():
        aid = int(row["id"]) if "id" in row else None

        # DB metadata lookup
        meta = db_map.get(aid, {"headline": None, "published_at": None, "url": None})

        articles.append({
            "article_id": aid,
            "headline": meta["headline"],
            "url": meta["url"],
            "published_at": meta["published_at"],
            "combined_score": float(row["combined_score"]) if "combined_score" in row else None,
            "pct_change": float(row["pct_change"]) if "pct_change" in row else None,
            "relative_volume": float(row["relative_volume"]) if "relative_volume" in row else None,
            "sentiment_price_agreement": row.get("sentiment_price_agreement", None),
        })

    return {
        "symbol": symbol,
        "company_name": name,
        "summary": sentiment_summary,
        "articles": articles,
    }

@router.get("/recent_articles")
def get_recent_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=100),
    ticker: Optional[str] = Query(None, description="Optional ticker symbol filter, e.g. NVDA"),
    sort_by: Optional[str] = Query("published_at", description="Field to sort by: 'published_at' or 'combined_score'"),
    order: Optional[str] = Query("desc", description="Sort order: 'asc' or 'desc'"),
    db: Session = Depends(get_db),
):
    """
    Return recent article-level sentiment rows (joined with ticker symbol/company_name).
    Supports sorting and pagination.
    """
    import numpy as np

    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "articles_sentiment.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"Article sentiment file not found: {csv_path}")

    try:
        df = pd.read_csv(
            csv_path,
            converters={
                "price": lambda x: try_float(x),
                "pct_change": lambda x: try_float(x),
                "abs_pct_change": lambda x: try_float(x),
                "minutes_to_price": lambda x: try_float(x),
                "relative_volume": lambda x: try_float(x),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read CSV: {e}")

    # Ensure key columns
    if "ticker_id" not in df.columns or "headline" not in df.columns:
        raise HTTPException(status_code=500, detail="CSV missing required columns: 'ticker_id' or 'headline'")

    # Parse timestamps
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    else:
        df["published_at"] = pd.NaT

    # Join with ticker info
    tickers = db.query(Ticker.id, Ticker.symbol, Ticker.company_name).all()
    ticker_df = pd.DataFrame(tickers, columns=["ticker_id", "symbol", "company_name"])
    df = df.merge(ticker_df, on="ticker_id", how="left")

    # --- ALWAYS collapse multiple rows per article down to 1 row ---
    if "id" in df.columns and "published_at" in df.columns:

        # pick the row closest to the actual published time
        idx = df.groupby("id")["published_at"].idxmax()   # or idxmin if needed

        df = df.loc[idx].copy()

    # Filter by ticker
    if ticker:
        t_up = ticker.strip().upper()
        df = df[df["symbol"].astype(str).str.upper() == t_up]

    # Sorting logic (AFTER dedupe)
    ascending = order.lower() == "asc"
    valid_sort_cols = ["published_at", "combined_score", "pct_change", "relative_volume"]

    if sort_by not in valid_sort_cols:
        sort_by = "published_at"

    if sort_by in ["combined_score", "pct_change", "relative_volume"]:
        df[sort_by] = pd.to_numeric(df[sort_by], errors="coerce").fillna(0)
        df = df.sort_values(by=sort_by, ascending=ascending, na_position="last")
    else:
        df = df.sort_values(by="published_at", ascending=ascending, na_position="last")

    # Pagination
    total = len(df)
    start = (page - 1) * limit
    end = start + limit
    page_df = df.iloc[start:end]

    # Convert rows for JSON
    def recordify(row):
        r = row.to_dict()

        # Send datetime as local EST string
        pub = r.get("published_at")
        if isinstance(pub, (pd.Timestamp, datetime)):
            r["published_at"] = pub.strftime("%Y-%m-%d %H:%M:%S")  # local ET
        else:
            r["published_at"] = None

        # Convert ALL numeric types safely
        for k, v in r.items():
            # None stays None
            if v is None:
                continue

            # numpy numbers
            if isinstance(v, (np.integer, np.floating)):
                r[k] = None if pd.isna(v) else float(v)
                continue

            # Decimal (SQLAlchemy often returns these!)
            if isinstance(v, Decimal):
                r[k] = float(v)
                continue

            # strings that should be floats
            if isinstance(v, str):
                try:
                    cleaned = v.replace("%", "").replace(",", "")
                    r[k] = float(cleaned)
                except:
                    pass

        return r


    response = {
        "page": page,
        "limit": limit,
        "total_records": total,
        "records": [recordify(r) for _, r in page_df.iterrows()],
    }

    # Clean NaN / Inf / -Inf values before sending JSON
    return sanitize_floats(response)



@router.get("/analytics/ticker-performance-3d")
def get_ticker_performance_3d(limit: int = 20, db: Session = Depends(get_db)):

    CSV_PATH = "backend/data/cleaned_data/features_aggregated.csv"
    df = pd.read_csv(CSV_PATH)

    # Safety: ensure combined_score exists
    if "combined_score" not in df.columns or "ticker_id" not in df.columns:
        return {"error": "CSV missing required columns combined_score or ticker_id"}

    # Compute average sentiment per ticker_id
    sentiment_map = (
        df.groupby("ticker_id")["combined_score"]
        .mean()
        .fillna(0)
        .to_dict()
    )

    price_stats = (
        db.query(
            HistoricalPrice.ticker_id,
            func.avg(HistoricalPrice.pct_change).label("avg_pct_change"),
            func.avg(HistoricalPrice.relative_volume).label("avg_relative_volume")
        )
        .group_by(HistoricalPrice.ticker_id)
        .order_by(func.avg(HistoricalPrice.relative_volume).desc())
        
        .limit(limit)
        .all()
    )

    results = []

    for row in price_stats:
        tid = row.ticker_id
        symbol = db.query(Ticker.symbol).filter(Ticker.id == tid).scalar()

        results.append({
            "ticker_id": tid,
            "symbol": symbol,
            "pct_change": float(row.avg_pct_change or 0),
            "relative_volume": float(row.avg_relative_volume or 0),
            "sentiment": float(sentiment_map.get(tid, 0)),
        })

    return {
        "count": len(results),
        "data": results
    }

