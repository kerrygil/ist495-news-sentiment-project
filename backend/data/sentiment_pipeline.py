import os
import pandas as pd
import numpy as np
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
nltk.download("vader_lexicon", quiet=True)
import requests
from bs4 import BeautifulSoup
import re
import string

def load_lm_dictionary(lm_dict_path):
    """Load and simplify the Loughran McDonald financial dictionary."""
    df = pd.read_csv(lm_dict_path)
    # Filter out only words with clear polarity
    df = df[(df["Positive"] > 0) | (df["Negative"] > 0)]
    lm_dict = {
        "positive": set(df.loc[df["Positive"] > 0, "Word"].str.lower()),
        "negative": set(df.loc[df["Negative"] > 0, "Word"].str.lower())
    }
    return lm_dict

def load_custom_dictionary(dict_path):
    """Load custom sentiment dictionary."""
    if dict_path.endswith(".csv"):
        return pd.read_csv(dict_path)
    else:
        raise ValueError("Unsupported dictionary format: must be .csv")
    
def tokenize_clean_title(clean_title: str) -> list[str]:
    """Split an already-cleaned title into individual tokens."""
    if not isinstance(clean_title, str):
        return []
    return [t for t in clean_title.split() if t.strip()]

def keyword_sentiment_score(title_clean, csv_dict, lm_dict):
    tokens = set(tokenize_clean_title(title_clean))
    if not tokens:
        return 0

    csv_score = 0
    lm_score = 0
    count = 0

    # CSV dict
    for _, row in csv_dict.iterrows():
        keyword = str(row.get("keyword", "")).lower()
        if keyword and keyword in tokens:
            sign = 1 if row.get("sentiment") == "positive" else -1
            try:
                strength = float(row.get("strength", 1))
            except ValueError:
                strength = 1
            csv_score += sign * strength
            count += 1

    # LM dictionary
    for word in lm_dict["positive"]:
        if word in tokens:
            lm_score += 1
            count += 1

    for word in lm_dict["negative"]:
        if word in tokens:
            lm_score -= 1
            count += 1

    lm_weight = 0.3
    total = csv_score + lm_weight * lm_score

    return total / count if count else 0

def vader_sentiment(title):
    """Use NLTK VADER to generate compound sentiment score."""
    tokens = set(tokenize_clean_title(title))
    if not tokens:
        return 0
    sia = SentimentIntensityAnalyzer()
    return sia.polarity_scores(str(title))["compound"]

def fetch_article_text(url):
    """Fetch main article text given a URL. Returns '' if invalid or fails."""
    if not isinstance(url, str) or not url.startswith("http"):
        return ""

    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts and styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # Heuristic: paragraphs with decent length
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        text = " ".join([p for p in paragraphs if len(p.split()) > 5])

        # Clean up whitespace and non-text
        text = re.sub(r"\s+", " ", text).strip()

        # Try OpenGraph description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            text = og_desc["content"]
            if len(text.split()) > 5:
                return text

        # Try Twitter summary
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if twitter_desc and twitter_desc.get("content"):
            text = twitter_desc["content"]
            if len(text.split()) > 5:
                return text

        # Try meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            text = meta_desc["content"]
            if len(text.split()) > 5:
                return text

        return text
    except Exception:
        return ""
    
def preprocess_financial_text(text: str) -> str:
    """Basic cleanup for financial news text before sentiment analysis."""
    if not isinstance(text, str) or not text.strip():
        return ""

    text = text.lower()

    # Remove tickers and symbols like (nasdaq:amd) or $aapl
    text = re.sub(r"\(.*?:.*?\)", " ", text)
    text = re.sub(r"\$[a-z]{1,5}\b", " ", text)

    # Remove URLs
    text = re.sub(r"http\S+|www\S+", " ", text)

    # Remove numbers, excessive punctuation, and whitespace
    text = re.sub(r"[\d]+", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()

    return text

def get_text_sentiment(text: str, csv_dict, lm_dict) -> float:
    """
    Compute combined dictionary-based sentiment for any text.
    Uses both CSV keyword dictionaries.
    """
    text_lower = str(text).lower()
    score = 0.0
    count = 0
    csv_score = 0.0
    lm_score = 0.0

    tokens = re.findall(r"\b\w+\b", text_lower)
    tokens_set = set(tokens)

    # CSV dictionary
    for _, row in csv_dict.iterrows():
        keyword = str(row.get("keyword", "")).lower()
        if keyword and keyword in tokens_set:
            sign = 1 if row.get("sentiment") == "positive" else -1
            try:
                strength = float(row.get("strength", 1))
            except ValueError:
                strength = 1
            csv_score += sign * strength
            count += 1

    # Loughran–McDonald dict
    for word in lm_dict["positive"]:
        if word in tokens_set:
            lm_score += 1
            count += 1
    for word in lm_dict["negative"]:
        if word in tokens_set:
            lm_score -= 1
            count += 1

    lm_weight = 0.3
    score = csv_score + lm_weight * lm_score
    return score / count if count > 0 else 0.0

def get_combined_sentiment(row, csv_dict, lm_dict):
    url = row.get("url", "")
    title_raw = row.get("title", "")
    title = preprocess_financial_text(title_raw)

    # --- Fetch body text ---
    article_text = fetch_article_text(url)
    article_text_clean = preprocess_financial_text(article_text)

    # --- Compute headline sentiment ---
    headline_score = get_text_sentiment(title, csv_dict, lm_dict)
    vader_score = vader_sentiment(title)
    keyword_score = keyword_sentiment_score(title, csv_dict, lm_dict)

    # --- Compute body sentiment if available ---
    body_score = None
    body_len = len(article_text_clean.split()) if article_text_clean else 0
    has_body = body_len > 5

    if has_body:
        body_score = get_text_sentiment(article_text_clean, csv_dict, lm_dict)

    if has_body and body_len > 40:
        # Full article available
        combined = (
            0.40 * body_score +
            0.30 * headline_score +
            0.20 * vader_score +
            0.10 * keyword_score
        )
    elif has_body and body_len > 10:
        # Partial but useful body text
        combined = (
            0.25 * body_score +
            0.40 * headline_score +
            0.25 * vader_score +
            0.10 * keyword_score
        )
    else:
        # No body text → rely on headline only
        combined = (
            0.50 * headline_score +
            0.35 * vader_score +
            0.15 * keyword_score
        )

    if not has_body:
        combined *= 0.75     # Confidence penalty

    return combined

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

def run_sentiment_pipeline(input_path, csv_dict_path, lm_dict_path, output_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Missing file: {input_path}")

    print(f"Loading engineered features from {input_path}...")
    df = pd.read_csv(input_path)

    csv_dict = load_custom_dictionary(csv_dict_path)
    lm_dict = load_lm_dictionary(lm_dict_path)

    print("Running sentiment analysis with extended dictionaries...")
    df["keyword_score"] = df["title"].apply(lambda x: keyword_sentiment_score(x, csv_dict, lm_dict))
    df["vader_score"] = df["title"].apply(vader_sentiment)
    df["combined_score"] = df.apply(
    lambda row: get_combined_sentiment(row, csv_dict, lm_dict), axis=1
    )
    df["sentiment_label"] = df["combined_score"].apply(classify_sentiment)
    df["sentiment_price_agreement"] = df.apply(label_agreement, axis=1)

    print("Analyzing correlation with price movement...")
    corr, summary = analyze_sentiment_price_correlation(df)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\nSentiment-annotated data saved to {output_path}")
    print(f"Final shape: {df.shape}")
    return df

def main():
    """Entry point for running this module as a script."""
    run_sentiment_pipeline(
        lm_dict_path="backend/data/Loughran-McDonald_MasterDictionary_1993-2024.csv",
        input_path="backend/data/cleaned_data/articles_features.csv",
        csv_dict_path="backend/data/weighted-keyword-dict.csv",
        output_path="backend/data/cleaned_data/articles_sentiment.csv"
    )

if __name__ == "__main__":
    main()


