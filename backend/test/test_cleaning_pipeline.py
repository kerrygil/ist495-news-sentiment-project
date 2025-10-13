import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from data.cleaning_pipeline import clean_articles

from fastapi.testclient import TestClient 
from app import main

client = TestClient(main.app)

def test_clean_articles():
    data = {
        "id": [1, 2],
        "ticker": ["AAPL", "MSFT"],
        "title": ["Apple Launches iPhone 16!!", "Microsoft@Build: New AI tools!"]
    }
    df = pd.DataFrame(data)

    cleaned_df = clean_articles(df)
    cleaned_titles = cleaned_df["title"].tolist()

    assert cleaned_titles == ["apple launches iphone 16", "microsoftbuild new ai tools"]

def test_get_cleaned_articles():
    response = client.get("/cleaned_articles")
    print("🔎 Response JSON:", response.json())
    assert response.status_code == 200
    data = response.json()
    assert "cleaned_articles" in data, f"Endpoint returned error: {data}"

