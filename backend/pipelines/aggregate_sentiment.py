import pandas as pd
from typing import Optional
import numpy as np


DEFAULT_INPUT = "backend/data/cleaned_data/articles_sentiment.csv"
DEFAULT_OUTPUT = "backend/data/cleaned_data/features_aggregated.csv"


def aggregate_sentiment(input_csv: str = DEFAULT_INPUT, output_csv: Optional[str] = DEFAULT_OUTPUT) -> pd.DataFrame:
    """Aggregate per-article sentiment and price features."""
    df = pd.read_csv(input_csv)

    # Normalize strings for consistency
    df["sentiment_label"] = df["sentiment_label"].str.lower()
    df["sentiment_price_agreement"] = df["sentiment_price_agreement"].str.lower()

    # Aggregate numeric + categorical fields
    agg_df = df.groupby("id").agg({
        "price": "mean",
        "pct_change": "mean",
        "abs_pct_change": "mean",
        "price_direction": lambda x: x.mode()[0] if not x.mode().empty else 0,
        "relative_volume": "mean",
        "vader_score": "mean",
        "keyword_score": "mean",
        "combined_score": "mean",
        "ticker_id": "first",
        "headline": "first",
        "published_at": "first",
        "sentiment_label": lambda x: x.mode()[0] if not x.mode().empty else "neutral"
    }).reset_index()

    # Count agreement/disagreement per article
    agreement_summary = df.groupby("id")["sentiment_price_agreement"].value_counts().unstack(fill_value=0)

    # Merge agreement counts into aggregated data
    agg_df = agg_df.merge(agreement_summary, on="id", how="left")

    # Fill missing values (if no "agree" or "disagree" entries exist)
    agg_df["agree"] = agg_df.get("agree", 0)
    agg_df["disagree"] = agg_df.get("disagree", 0)

    # Interpret accuracy based on sentiment to price direction agreement
    def assess_agreement(row):
        agree = row["agree"]
        disagree = row["disagree"]
        direction = row["price_direction"]

        # Mostly agreement cases
        if agree > disagree:
            if direction == 1:
                return "accurate"
            elif direction == -1:
                return "inconclusive"
            else:
                return "neutral"

        # Mostly disagreement cases
        elif disagree > agree:
            if direction == -1:
                return "accurate"
            elif direction == 1:
                return "inconclusive"
            else:
                return "neutral"

        # Equal agreement and disagreement
        else:
            return "inconclusive"

    agg_df["sentiment_price_correlation"] = agg_df.apply(assess_agreement, axis=1)

    df = df.replace([np.inf, -np.inf], np.nan)
    df["combined_score"] = pd.to_numeric(df["combined_score"], errors="coerce")
    df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce")
    df["relative_volume"] = pd.to_numeric(df["relative_volume"], errors="coerce")
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    # Save to CSV if an output path was provided
    if output_csv:
        agg_df.to_csv(output_csv, index=False)

    return agg_df


def main():
    """Entry point for running this module as a script."""
    agg_df = aggregate_sentiment()
    print(f"Aggregated features saved to {DEFAULT_OUTPUT}")
    print(agg_df[["id", "headline", "price_direction", "agree", "disagree", "sentiment_price_correlation"]].head())


if __name__ == "__main__":
    main()
