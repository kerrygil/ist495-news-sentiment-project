import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 

import os
import pandas as pd
import pytest
from data.feature_engineering import feature_engineering

# --- Setup test paths ---
CLEANED_PATH = "test_data/articles_cleaned_test.csv"
PRICES_PATH = "test_data/prices_test.csv"
OUTPUT_PATH = "test_data/articles_features_test.csv"

@pytest.fixture(scope="module", autouse=True)
def setup_test_data(tmp_path_factory):
    """Create small sample CSVs for testing."""
    test_dir = tmp_path_factory.mktemp("test_data")

    articles_data = pd.DataFrame({
        "id": [1, 2],
        "title": ["Test Title 1", "Test Title 2"],
        "url": ["testurl1", "testurl2"],
        "published_at": ["2025-10-01", "2025-10-02"],
        "ticker_id": [1, 2]
    })
    prices_data = pd.DataFrame({
        "ticker_id": [1, 2],
        "date": ["2025-10-02", "2025-10-03"],
        "close_price": [100.0, 110.0],
        "volume": [5000, 6000]
    })

    articles_data.to_csv(test_dir / "articles_cleaned_test.csv", index=False)
    prices_data.to_csv(test_dir / "prices_test.csv", index=False)

    global CLEANED_PATH, PRICES_PATH, OUTPUT_PATH
    CLEANED_PATH = test_dir / "articles_cleaned_test.csv"
    PRICES_PATH = test_dir / "prices_test.csv"
    OUTPUT_PATH = test_dir / "articles_features_test.csv"

    yield

def test_feature_engineering_runs_successfully():
    """Ensure feature engineering function executes and saves a CSV."""
    feature_engineering(CLEANED_PATH, PRICES_PATH, OUTPUT_PATH)
    assert os.path.exists(OUTPUT_PATH), "Output CSV should be created"

def test_feature_columns_exist():
    """Verify new engineered features exist in output CSV."""
    df = pd.read_csv(OUTPUT_PATH)
    expected_cols = {"days_to_next_close", "price_change_next_day", "published_at_utc", "ticker_label"}
    assert expected_cols.issubset(df.columns), f"Missing expected columns: {expected_cols - set(df.columns)}"

def test_feature_values_reasonable():
    """Ensure the new columns have reasonable data."""
    df = pd.read_csv(OUTPUT_PATH)
    assert df["days_to_next_close"].notna().all(), "days_to_next_close should not be null"
    assert df["price_change_next_day"].dtype == float, "price_change_next_day should be numeric"
