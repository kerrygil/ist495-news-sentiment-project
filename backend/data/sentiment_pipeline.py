import os
import pandas as pd
import numpy as np
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
nltk.download("vader_lexicon", quiet=True)

def load_custom_dictionary(dict_path):
    """Load custom sentiment dictionary (either JSON or CSV)."""
    if dict_path.endswith(".json"):
        import json
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif dict_path.endswith(".csv"):
        return pd.read_csv(dict_path)
    else:
        raise ValueError("Unsupported dictionary format: must be .json or .csv")


def keyword_sentiment_score(title, json_dict, csv_dict):
    """Return average sentiment score from keyword matches."""
    title_lower = str(title).lower()
    score = 0
    count = 0

    # JSON-style dictionary
    for word in json_dict.get("positive", []):
        if word in title_lower:
            score += 1
            count += 1
    for word in json_dict.get("negative", []):
        if word in title_lower:
            score -= 1
            count += 1

    # CSV dictionary
    for _, row in csv_dict.iterrows():
        keyword = str(row.get("keyword", "")).lower()
        if keyword and keyword in title_lower:
            sign = 1 if row.get("sentiment") == "positive" else -1
            try:
                strength = float(row.get("strength", 1))
            except ValueError:
                strength = 1
            score += sign * strength
            count += 1

    return score / count if count > 0 else 0


def vader_sentiment(title):
    """Use NLTK VADER to generate compound sentiment score."""
    sia = SentimentIntensityAnalyzer()
    return sia.polarity_scores(str(title))["compound"]


def classify_sentiment(value):
    """Convert numeric sentiment into categorical label."""
    if value > 0.05:
        return "positive"
    elif value < -0.05:
        return "negative"
    else:
        return "neutral"


def analyze_sentiment_price_correlation(df):
    """Compute correlation and summarize sentiment vs price direction."""
    corr = df["combined_score"].corr(df["pct_change"])
    print(f"\nCorrelation between sentiment score and price change: {corr:.3f}")

    # Basic sentiment vs movement summary
    summary = pd.crosstab(df["sentiment_label"], np.sign(df["pct_change"]),
                          rownames=["Sentiment"], colnames=["Price Direction"])
    print("\nSentiment vs Price Direction:")
    print(summary)

    return corr, summary

def label_agreement(row):
    if row["sentiment_label"] == "neutral":
        return "neutral"
    elif row["sentiment_label"] == "positive" and row["pct_change"] > 0:
        return "agree"
    elif row["sentiment_label"] == "negative" and row["pct_change"] < 0:
        return "agree"
    else:
        return "disagree"

def run_sentiment_pipeline(input_path, json_dict_path, csv_dict_path, output_path):
    """Perform sentiment analysis and correlate with price movement."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Missing file: {input_path}")

    print(f"Loading engineered features from {input_path}...")
    df = pd.read_csv(input_path)

    json_dict = load_custom_dictionary(json_dict_path)
    csv_dict = load_custom_dictionary(csv_dict_path)

    print("Running sentiment analysis...")
    df["keyword_score"] = df["title"].apply(lambda x: keyword_sentiment_score(x, json_dict, csv_dict))
    df["vader_score"] = df["title"].apply(vader_sentiment)
    df["combined_score"] = df[["keyword_score", "vader_score"]].mean(axis=1)
    df["sentiment_label"] = df["combined_score"].apply(classify_sentiment)
    df["sentiment_price_agreement"] = df.apply(label_agreement, axis=1)

    print("Analyzing correlation with price movement...")
    corr, summary = analyze_sentiment_price_correlation(df)

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\nSentiment-annotated data saved to {output_path}")
    print(f"Final shape: {df.shape}")
    return df


if __name__ == "__main__":
    run_sentiment_pipeline(
        input_path="backend/data/cleaned_data/articles_features.csv",
        json_dict_path="backend/data/keyword_dict.json",
        csv_dict_path="backend/data/keyword_dict.csv",
        output_path="backend/data/cleaned_data/articles_sentiment.csv"
    )

