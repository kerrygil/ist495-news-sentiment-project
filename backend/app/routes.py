from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import data_models
from data.database import get_db
import pandas as pd
import os


router = APIRouter()

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

@router.get("/articles_features")
def get_feature_engineered_articles():
    import os
    import pandas as pd

    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(base_dir, "..", "data", "cleaned_data", "articles_features.csv"))

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Feature-engineered file not found. Run feature_engineering.py first.")

    df = pd.read_csv(csv_path)
    return {"articles_features": df.head(10).to_dict(orient="records")}


