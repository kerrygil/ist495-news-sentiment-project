import os
import pandas as pd
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import csv

# Ensure NLTK resources exist
import nltk
nltk.download("vader_lexicon", quiet=True)

def load_custom_dictionary(dict_path):
    """Load custom sentiment dictionary (either JSON or CSV)."""
    if dict_path.endswith(".json"):
        import json
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif dict_path.endswith(".csv"):
        df = pd.read_csv(dict_path)
        return df
    else:
        raise ValueError("Unsupported dictionary format: must be .json or .csv")


def keyword_sentiment_score(title, json_dict, csv_dict):
    """Return sentiment label from keyword match."""
    title_lower = title.lower()
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
        if str(row["keyword"]).lower() in title_lower:
            sign = 1 if row["sentiment"] == "positive" else -1
            score += sign * float(row["strength"])
            count += 1

    if count == 0:
        return 0  # neutral if no match
    return score / count


def vader_sentiment(title):
    """Use NLTK VADER sentiment."""
    sia = SentimentIntensityAnalyzer()
    return sia.polarity_scores(title)["compound"]


def classify_sentiment(value):
    """Convert numeric score into label."""
    if value > 0.05:
        return "positive"
    elif value < -0.05:
        return "negative"
    else:
        return "neutral"


def run_sentiment_pipeline(input_path, json_dict_path, csv_dict_path, output_path):
    """Main sentiment analysis entry point."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Missing file: {input_path}")

    df = pd.read_csv(input_path)
    json_dict = load_custom_dictionary(json_dict_path)
    csv_dict = load_custom_dictionary(csv_dict_path)

    df["keyword_score"] = df["title"].apply(lambda x: keyword_sentiment_score(x, json_dict, csv_dict))
    df["vader_score"] = df["title"].apply(vader_sentiment)

    # Combine both sources
    df["combined_score"] = df[["keyword_score", "vader_score"]].mean(axis=1)
    df["sentiment_label"] = df["combined_score"].apply(classify_sentiment)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"✅ Sentiment data saved to {output_path}")
    return df


if __name__ == "__main__":
    run_sentiment_pipeline(
        input_path="backend/data/cleaned_data/test_articles_features.csv",
        json_dict_path="backend/data/keyword_dict.json",
        csv_dict_path="backend/data/keyword_dict.csv",
        output_path="backend/data/cleaned_data/test_articles_sentiment.csv"
    )
