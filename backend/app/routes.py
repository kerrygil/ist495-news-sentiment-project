from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models import data_models
from backend.models.data_models import Ticker
from backend.data.database import get_db
import pandas as pd
import os
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
def get_aggregated_features():
    """Return aggregated sentiment–price correlation data."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "features_aggregated.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Aggregated file not found. Run aggregate_sentiments.py first.")

    df = pd.read_csv(csv_path)

    return {
        "records": df.to_dict(orient="records"),
        "summary": {
            "total_articles": len(df),
            "accurate": int((df["sentiment_price_correlation"] == "accurate").sum()),
            "inconclusive": int((df["sentiment_price_correlation"] == "inconclusive").sum()),
            "neutral": int((df["sentiment_price_correlation"] == "neutral").sum())
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
    """Run the full data pipeline in order."""
    try:
        scripts = [
            "backend.scrapers.headline_ticker_scraper",
            "backend.scrapers.historical_price_fetch",
            "backend.data.cleaning_pipeline",
            "backend.data.feature_engineering",
            "backend.data.sentiment_pipeline",
            "backend.data.aggregate_sentiment",
        ]
        for script in scripts:
            print(f"Running {script} ...")
            subprocess.run(
                [sys.executable, "-m", script],
                check=True,
                capture_output=True,
                text=True
            )
        return {"status": "success", "message": "Pipeline re-run successfully."}
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed while running {script}: {e.stderr or e}"
        )
    
@router.get("/tickers/search")
def search_tickers_with_sentiment(
    q: str = Query(..., description="Search query (e.g., AAPL or Apple)"),
    db: Session = Depends(get_db),
):
    """
    Search tickers by symbol or name and return aggregated sentiment metrics.
    Combines CSV sentiment data with DB ticker info.
    """

    import pandas as pd
    import os

    # Load aggregated CSV
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "features_aggregated.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Aggregated features file not found. Run pipeline first.")

    df = pd.read_csv(csv_path)

    # Load ticker mappings from the database
    tickers = db.query(data_models.Ticker).all()
    ticker_map = {t.id: t.symbol for t in tickers}
    name_map = {t.id: t.company_name for t in tickers}

    # Add symbol and name columns to the DataFrame
    df["ticker_symbol"] = df["ticker_id"].map(ticker_map)
    df["ticker_name"] = df["ticker_id"].map(name_map)

    # Filter by symbol or name (case-insensitive)
    filtered = df[
        df["ticker_symbol"].str.contains(q, case=False, na=False)
        | df["ticker_name"].str.contains(q, case=False, na=False)
    ]

    if filtered.empty:
        raise HTTPException(status_code=404, detail=f"No sentiment data found for '{q}'")

    # Aggregate sentiment metrics
    sentiment_summary = {
        "ticker": filtered["ticker_symbol"].iloc[0],
        "name": filtered["ticker_name"].iloc[0],
        "article_count": int(filtered["id"].nunique()) if "id" in filtered.columns else len(filtered),
        "avg_combined_score": round(filtered["combined_score"].mean(), 4)
        if "combined_score" in filtered.columns
        else None,
        "agreement_rate": round(
            (filtered["sentiment_price_agreement"].eq("accurate").sum() / len(filtered)) * 100, 2
        )
        if "sentiment_price_agreement" in filtered.columns
        else None,
    }

    return {
        "summary": sentiment_summary,
        "records": filtered.head(15).to_dict(orient="records"),
    }