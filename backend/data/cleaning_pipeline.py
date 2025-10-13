import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import re

print("Using Python:", sys.executable)

# Load environment variables
load_dotenv()

def load_articles():
    """Load articles from PostgreSQL into a pandas DataFrame."""
    db_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )

    engine = create_engine(db_url)
    print("Connecting to database...")
    df = pd.read_sql("SELECT * FROM articles", con=engine)
    print(f"Loaded {len(df)} rows.")
    return df

def clean_articles(df):
    """Clean the article titles by lowercasing and removing special characters."""
    if "title" not in df.columns:
        raise ValueError("Missing 'title' column in DataFrame.")

    df["title"] = (
        df["title"]
        .astype(str)
        .str.lower()
        .apply(lambda x: re.sub(r"[^a-zA-Z0-9 ]", "", x))
    )
    return df

if __name__ == "__main__":
    articles_df = load_articles()
    cleaned_df = clean_articles(articles_df)

    print("Sample cleaned data:")
    print(cleaned_df.head(10))

    os.makedirs("backend/data/cleaned_data", exist_ok=True)
    cleaned_df.to_csv("backend/data/cleaned_data/articles_cleaned.csv", index=False)
    print("Cleaned data saved to backend/data/cleaned_data/articles_cleaned.csv")

