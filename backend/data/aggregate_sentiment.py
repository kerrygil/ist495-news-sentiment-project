import pandas as pd

df = pd.read_csv("backend/data/cleaned_data/articles_sentiment.csv")

# Aggregate numeric columns (mean of all price records per article)
agg_df = df.groupby("id").agg({
    "price": "mean",
    "pct_change": "mean",
    "vader_score": "mean",
    "keyword_score": "mean",
    "combined_score": "mean",
    "sentiment_label": "first" 
}).reset_index()

agg_df.to_csv("backend/data/cleaned_data/features_aggregated.csv", index=False)
