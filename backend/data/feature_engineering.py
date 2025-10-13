import pandas as pd
from datetime import datetime

def feature_engineering(articles_path, prices_path, output_path):
    # Load datasets
    articles = pd.read_csv(articles_path, parse_dates=["published_at"])
    prices = pd.read_csv(prices_path, parse_dates=["date"])

    # Merge based on ticker ID
    df = pd.merge(articles, prices, left_on="ticker_id", right_on="ticker_id", how="left")

    # Example feature: time difference between publish date and next market close
    df["days_to_next_close"] = (df["date"] - df["published_at"]).dt.days

    # Example feature: percentage change in stock price day after article
    df["price_change_next_day"] = df["close_price"].pct_change()

    # Example feature: time zone normalization
    df["published_at_utc"] = pd.to_datetime(df["published_at"], utc=True)

    # Optional: encode categorical features
    df["ticker_label"] = df["ticker_id"].astype("category").cat.codes

    # Drop duplicates or irrelevant columns
    df.drop_duplicates(subset=["id"], inplace=True)

    # Save engineered dataset
    df.to_csv(output_path, index=False)
    print(f"✅ Feature-engineered data saved to: {output_path}")

if __name__ == "__main__":
    feature_engineering(
        "backend/data/cleaned_data/articles_cleaned.csv",
        "backend/data/prices.csv",
        "backend/data/cleaned_data/articles_features.csv"
    )
