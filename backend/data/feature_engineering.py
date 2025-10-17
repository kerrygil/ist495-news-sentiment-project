import pandas as pd
import numpy as np

def create_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create time-related features from publication and price timestamps."""
    df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')

    # Time delta between article and corresponding price record
    df['minutes_to_price'] = (df['created_at'] - df['published_at']).dt.total_seconds() / 60

    # Day/time context of the article
    df['day_of_week'] = df['published_at'].dt.dayofweek  # Monday = 0
    df['hour_of_day'] = df['published_at'].dt.hour

    # Market context flags
    is_weekday = (df['day_of_week'] < 5)
    df['is_market_hours'] = (
        is_weekday &
        (df['published_at'].dt.time >= pd.to_datetime('09:30').time()) &
        (df['published_at'].dt.time <= pd.to_datetime('16:00').time())
    ).astype(int)

    df['is_premarket'] = (
        is_weekday &
        (df['published_at'].dt.time >= pd.to_datetime('04:00').time()) &
        (df['published_at'].dt.time < pd.to_datetime('09:30').time())
    ).astype(int)

    df['is_aftermarket'] = (
        is_weekday &
        (df['published_at'].dt.time > pd.to_datetime('16:00').time()) &
        (df['published_at'].dt.time <= pd.to_datetime('20:00').time())
    ).astype(int)

    # Cyclical encoding for hour of day (helps ML)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)

    return df


def feature_engineering(articles_path, prices_path, output_path):
    """Merge article and price data and generate engineered features."""
    print("Loading input data...")

    articles_df = pd.read_csv(articles_path)
    prices_df = pd.read_csv(prices_path)

    print(f"Articles: {len(articles_df)} rows")
    print(f"Prices: {len(prices_df)} rows")

    # Merge article and price data on ticker/article relationship
    merged_df = pd.merge(
        articles_df,
        prices_df,
        how='left',
        left_on=['id', 'ticker_id'],
        right_on=['article_id', 'ticker_id']
    )

    # Remove duplicates if they exist (based on article_id)
    if 'article_id' in merged_df.columns:
        merged_df = merged_df.drop_duplicates(subset=['article_id'])

    # Generate engineered features
    merged_df = create_time_features(merged_df)

    # Example numeric transformations
    merged_df['abs_pct_change'] = merged_df['pct_change'].abs()
    merged_df['log_price'] = np.log1p(merged_df['price'])

    # Save result
    merged_df.to_csv(output_path, index=False)
    print(f"Feature-engineered data saved to: {output_path}")
    print(f"Final shape: {merged_df.shape}")

if __name__ == "__main__":
    feature_engineering(
        "backend/data/cleaned_data/test_articles_cleaned.csv",
        "backend/scrapers/prices.csv",
        "backend/data/cleaned_data/test_articles_features.csv"
    )

