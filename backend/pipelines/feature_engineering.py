import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def create_time_features(df: pd.DataFrame) -> pd.DataFrame:
    # At this point, we assume published_at and created_at are naive
    # local timestamps in America/New_York

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    # Minutes from article publish to price snapshot
    df["minutes_to_price"] = (df["created_at"] - df["published_at"]).dt.total_seconds() / 60

    # Calendar features based on local time
    df["day_of_week"] = df["published_at"].dt.dayofweek
    df["hour_of_day"] = df["published_at"].dt.hour

    pub_times = df["published_at"].dt.time

    market_open = pd.to_datetime("09:30").time()
    market_close = pd.to_datetime("16:00").time()
    aftermarket_close = pd.to_datetime("20:00").time()

    # Regular market hours (Mon–Fri, 9:30–16:00 ET)
    df["is_market_hours"] = (
        (df["day_of_week"] < 5)
        & (pub_times >= market_open)
        & (pub_times <= market_close)
    ).astype(int).fillna(0)

    # Aftermarket (Mon–Fri, 16:00–20:00 ET)
    df["is_aftermarket"] = (
        (df["day_of_week"] < 5)
        & (pub_times > market_close)
        & (pub_times <= aftermarket_close)
    ).astype(int).fillna(0)

    return df

import re

def normalize_timestamp_string(s: str) -> str:
    if not isinstance(s, str):
        return s

    s = s.strip()

    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+00:00$", s):
        s = s.replace("+00:00", ".000000+00:00")

    return s


def feature_engineering(articles_path, prices_path, output_path):
    print("Loading input data...")
    articles_df = pd.read_csv(articles_path, dtype=str)
    prices_df = pd.read_csv(prices_path, dtype=str)

    print(f"Raw Articles rows: {len(articles_df)}")
    print(f"Raw Prices rows:   {len(prices_df)}")

    articles_df["published_at"] = (
        articles_df["published_at"]
            .astype(str)
            .map(normalize_timestamp_string)
    )

    articles_df["published_at"] = pd.to_datetime(
        articles_df["published_at"], errors="coerce", utc=True
    ).dt.tz_convert("America/New_York").dt.tz_localize(None)

    prices_df["created_at"] = pd.to_datetime(
        prices_df["created_at"], errors="coerce", utc=True
    ).dt.tz_convert("America/New_York").dt.tz_localize(None)

    cutoff_date = datetime.now() - timedelta(days=2)
    articles_df = articles_df[articles_df["published_at"] >= cutoff_date]
    prices_df = prices_df[prices_df["created_at"] >= cutoff_date]

    print(
        f"\nFiltered to only include data from {cutoff_date:%Y-%m-%d %H:%M} "
        f"onwards (America/New_York local time)"
    )
    print(f"Remaining Articles: {len(articles_df)}, Prices: {len(prices_df)}\n")

    for col in ["id", "ticker_id", "published_at"]:
        if col not in articles_df.columns:
            raise RuntimeError(f"Articles CSV missing column: {col}")

    for col in ["article_id", "ticker_id", "created_at", "price", "pct_change", "relative_volume"]:
        if col not in prices_df.columns:
            print(f"Warning: Prices CSV missing column: {col} (this may be expected for some runs)")

    articles_df["id"] = pd.to_numeric(articles_df["id"], errors="coerce").astype("Int64")
    articles_df["ticker_id"] = pd.to_numeric(articles_df["ticker_id"], errors="coerce").astype("Int64")

    prices_df["article_id"] = pd.to_numeric(prices_df["article_id"], errors="coerce").astype("Int64")
    prices_df["ticker_id"] = pd.to_numeric(prices_df["ticker_id"], errors="coerce").astype("Int64")

    # numeric columns in prices
    for numcol in ["price", "pct_change", "relative_volume"]:
        if numcol in prices_df.columns:
            prices_df[numcol] = pd.to_numeric(prices_df[numcol], errors="coerce")

    # Merge with indicator to see unmatched rows
    merged_df = pd.merge(
        articles_df,
        prices_df,
        how='left',
        left_on=['id', 'ticker_id'],
        right_on=['article_id', 'ticker_id'],
        indicator=True,
    )

    # Diagnostics
    total_left = len(merged_df)
    matched = (merged_df["_merge"] == "both").sum()
    left_only = (merged_df["_merge"] == "left_only").sum()
    right_only = (merged_df["_merge"] == "right_only").sum()  # should be 0 because left join

    print(f"Merged rows: {total_left} (matched={matched}, left_only={left_only}, right_only={right_only})")

    if left_only > 0:
        # Save a sample of unmatched articles so you can inspect why
        unmatched = merged_df[merged_df["_merge"] == "left_only"].copy()
        diagnostic_path = os.path.join(os.path.dirname(output_path), "merge_unmatched.csv")
        # Keep helpful columns for debugging
        cols_to_save = [c for c in ["id", "title", "ticker_id", "published_at", "url", "article_id", "created_at"] if c in unmatched.columns]
        unmatched[cols_to_save].to_csv(diagnostic_path, index=False)
        print(f"Saved {len(unmatched)} left-only rows to {diagnostic_path} for inspection")

    # Drop merge indicator and handle ids properly
    if "_merge" in merged_df.columns:
        merged_df.drop(columns=["_merge"], inplace=True)

    # If duplicate id_x or article_id columns exist, tidy them
    if "id_x" in merged_df.columns:
        merged_df.rename(columns={"id_x": "id"}, inplace=True)
    if "id_y" in merged_df.columns:
        # id_y likely came from prices - remove it to avoid confusion
        merged_df.drop(columns=["id_y"], inplace=True)
    if "article_id" in merged_df.columns and "article_id" not in merged_df.columns:
        pass

    # Ensure required fields exist so create_time_features doesn't crash
    if "created_at" not in merged_df.columns:
        merged_df["created_at"] = pd.NaT

    # Convert numeric columns for feature calc
    for numcol in ["pct_change", "price", "relative_volume"]:
        if numcol in merged_df.columns:
            merged_df[numcol] = pd.to_numeric(merged_df[numcol], errors="coerce")

    # Now add engineered features
    merged_df = create_time_features(merged_df)

    # Price movement and direction
    merged_df['abs_pct_change'] = merged_df['pct_change'].abs()
    merged_df['price_direction'] = np.where(merged_df['pct_change'] > 0, 1,
                                            np.where(merged_df['pct_change'] < 0, -1, 0))

    # Keep relevant columns only (simplifies future sentiment merge)
    keep_cols = [
        'id', 'title', 'ticker_id', 'published_at', 'price', 'pct_change',
        'abs_pct_change', 'price_direction',
        'minutes_to_price', 'day_of_week', 'hour_of_day',
        'relative_volume', 'is_market_hours', 'is_aftermarket', 'headline'
    ]
    keep_cols = [c for c in keep_cols if c in merged_df.columns]  # be defensive

    final_df = merged_df[keep_cols].copy()

    # Save result
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final_df.to_csv(output_path, index=False)
    print(f"Feature-engineered data saved to: {output_path}")
    print(f"Final shape: {final_df.shape}")

def main():
    feature_engineering(
        "backend/data/cleaned_data/articles_cleaned.csv",
        "backend/data/prices.csv",
        "backend/data/cleaned_data/articles_features.csv"
    )

if __name__ == "__main__":
    main()


