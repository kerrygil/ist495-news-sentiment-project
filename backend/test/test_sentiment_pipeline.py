import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 

import os
import pandas as pd
from data.sentiment_pipeline import run_sentiment_pipeline

def test_sentiment_pipeline(tmp_path):
    # Prepare test files
    input_csv = tmp_path / "articles_features.csv"
    json_dict = tmp_path / "keyword_dict.json"
    csv_dict = tmp_path / "keyword_dict.csv"
    output_csv = tmp_path / "articles_sentiment.csv"

    # Create small test article data
    pd.DataFrame({
        "id": [1, 2, 3],
        "title": ["Company profits surge", "Market crash warning", "Economic forecast stable"]
    }).to_csv(input_csv, index=False)

    # Create test sentiment dictionaries
    json_dict.write_text('{"positive": ["profit", "surge"], "negative": ["crash", "warning"], "neutral": ["forecast"]}')
    csv_dict.write_text("keyword,sentiment,strength\nsurge,positive,1.0\ncrash,negative,1.0\nforecast,neutral,0.0")

    df = run_sentiment_pipeline(str(input_csv), str(json_dict), str(csv_dict), str(output_csv))
    assert os.path.exists(output_csv)

    # Validate columns
    expected_cols = {"title", "keyword_score", "vader_score", "combined_score", "sentiment_label"}
    assert expected_cols.issubset(df.columns)

    # Check output makes sense
    assert df.loc[0, "sentiment_label"] == "positive"
    assert df.loc[1, "sentiment_label"] == "negative"
    assert df.loc[2, "sentiment_label"] in ("neutral", "positive")

