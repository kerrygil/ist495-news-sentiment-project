import pandas as pd
import numpy as np

def create_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Generate basic temporal context features."""
    df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')

    # Time difference between article and recorded price
    df['minutes_to_price'] = (df['created_at'] - df['published_at']).dt.total_seconds() / 60

    # Basic time context
    df['day_of_week'] = df['published_at'].dt.dayofweek  # Monday = 0
    df['hour_of_day'] = df['published_at'].dt.hour

    # Market context flags
    is_weekday = (df['day_of_week'] < 5)
    df['is_market_hours'] = (
        is_weekday &
        (df['published_at'].dt.time >= pd.to_datetime('09:30').time()) &
        (df['published_at'].dt.time <= pd.to_datetime('16:00').time())
    ).astype(int)

    df['is_aftermarket'] = (
        is_weekday &
        (df['published_at'].dt.time > pd.to_datetime('16:00').time()) &
        (df['published_at'].dt.time <= pd.to_datetime('20:00').time())
    ).astype(int)

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

    # Drop redundant columns
    merged_df.drop(columns=[col for col in ['id_y', 'article_id'] if col in merged_df.columns], inplace=True)
    merged_df.rename(columns={'id_x': 'id'}, inplace=True)

    # Add engineered features
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
        'is_market_hours', 'is_aftermarket'
    ]

    merged_df = merged_df[keep_cols]

    # Save result
    merged_df.to_csv(output_path, index=False)
    print(f"Feature-engineered data saved to: {output_path}")
    print(f"Final shape: {merged_df.shape}")


if __name__ == "__main__":
    feature_engineering(
        "backend/data/cleaned_data/articles_cleaned.csv",
        "backend/scrapers/prices.csv",
        "backend/data/cleaned_data/articles_features.csv"
    )


