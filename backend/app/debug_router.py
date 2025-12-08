from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
import pandas as pd
import os
import nltk
nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.sentiment.vader import VaderConstants
import re

router = APIRouter(prefix="/debug", tags=["debug"])

sid = SentimentIntensityAnalyzer()

def vader_breakdown(text: str):
    """
    Returns a detailed breakdown of how VADER computed a sentiment score.
    """


    # Tokenize the same way VADER does
    words = text.split()
    lexicon = sid.lexicon  # raw VADER word → score dictionary

    breakdown = []
    for i, word in enumerate(words):
        w = word.lower()
        entry = {
            "token": word,
            "base_valence": 0.0,
            "is_in_lexicon": False,
            "is_negated": False,
            "scalar": 1.0,
        }

        # 1. Base lexicon score
        if w in lexicon:
            entry["is_in_lexicon"] = True
            entry["base_valence"] = lexicon[w]

            # 2. Check for negation
            if any(neg in words[max(i-3,0):i] for neg in VaderConstants.NEGATE):
                entry["is_negated"] = True
                entry["base_valence"] *= -0.74

            # 3. Check for ALL CAPS emphasis
            if word.isupper() and len(word) > 1:
                entry["scalar"] += 0.733

        breakdown.append(entry)

    final = sid.polarity_scores(text)

    return {
        "text": text,
        "tokens": breakdown,
        "final_vader_score": final,
    }

# --- reuse or re-implement your dictionary loader ---
def load_custom_dictionary(dict_path):
    if dict_path.endswith(".csv"):
        return pd.read_csv(dict_path)
    else:
        raise ValueError("Unsupported dictionary format: must be .csv")

# --- compute keyword breakdown for one title ---
def keyword_breakdown_tokens(clean_title, csv_dict):
    """Token-based keyword scoring + full debug breakdown."""
    tokens = set(clean_title.split())  # title is already cleaned by your pipeline

    matches = []
    score = 0
    count = 0

    # CSV dict (keyword, sentiment, strength)
    for _, row in csv_dict.iterrows():
        kw = str(row["keyword"]).lower()
        if kw in tokens:
            sign = +1 if row["sentiment"] == "positive" else -1
            try:
                strength = float(row["strength"])
            except:
                strength = 1
            matches.append({
                "word": kw,
                "source": "csv",
                "sign": sign,
                "strength": strength,
                "contribution": sign * strength
            })
            score += sign * strength
            count += 1

    return (score / count) if count else 0, matches

# --- Debug route: examine top N articles or a single article_id ---
@router.get("/keyword_influence")
def debug_keyword_influence(
    article_id: Optional[int] = Query(None, description="Optional single article id to inspect"),
    limit: int = Query(20, ge=1, le=500),
    export_csv: bool = Query(False, description="If true save a CSV to disk (backend/data/debug_keyword_breakdown.csv)"),
):
    # paths - adjust to your project
    agg_csv = os.path.join(os.path.dirname(__file__), "..", "data", "cleaned_data", "articles_features.csv")
    csv_dict_path = os.path.join(os.path.dirname(__file__), "..", "data", "weighted-keyword-dict.csv")

    # load data
    if not os.path.exists(agg_csv):
        raise HTTPException(status_code=404, detail=f"Features CSV not found: {agg_csv}")
    df = pd.read_csv(agg_csv, dtype=str)  # read strings so we don't fail on mixed dtypes

    # pick records
    if article_id is not None:
        df = df[df["id"].astype(int) == int(article_id)]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Article id {article_id} not found")
    else:
        # sort by published_at if exists else by id
        if "published_at" in df.columns:
            df["published_at_parsed"] = pd.to_datetime(df["published_at"], errors="coerce")
            df = df.sort_values(by="published_at_parsed", ascending=False).head(limit)
        else:
            df = df.head(limit)

    # load dictionaries
    csv_dict = load_custom_dictionary(csv_dict_path) if os.path.exists(csv_dict_path) else pd.DataFrame(columns=["keyword","sentiment","strength"])
    if isinstance(csv_dict, pd.DataFrame) and "keyword" not in csv_dict.columns:
        # defensive: try to guess column names
        csv_dict.columns = [c.strip() for c in csv_dict.columns]

    out_rows = []
    for _, row in df.iterrows():
        tokens = row["headline"].split()

        kscore, kmatches = keyword_breakdown_tokens(row["headline"], csv_dict)

        hit_words = [m["word"] for m in kmatches]

        out = {
            "id": int(row.get("id")) if row.get("id") not in (None, "", "nan") else None,
            "title": row["headline"],
            "tokens": tokens,
            "hits": hit_words,
            "matches_verbose": kmatches,
            "keyword_score": kscore,
        }

        out_rows.append(out)

    # optional CSV export (flatten matches into columns)
    if export_csv and out_rows:
        csv_out_path = os.path.join(os.path.dirname(__file__), "..", "data", "debug_keyword_breakdown.csv")
        rows_for_csv = []
        for r in out_rows:
            base = {"id": r["id"], "title": r["title"], "keyword_score": r["keyword_score"], "vader_score": r["vader_score"]}
            # make N match columns (you can decide max matches to write)
            for i, m in enumerate(r["matches"][:10], start=1):
                base[f"match_{i}_word"] = m["word"]
                base[f"match_{i}_source"] = m["source"]
                base[f"match_{i}_sign"] = m["sign"]
                base[f"match_{i}_strength"] = m["strength"]
                base[f"match_{i}_contrib"] = m["contribution"]
            rows_for_csv.append(base)
        pd.DataFrame(rows_for_csv).to_csv(csv_out_path, index=False)
    else:
        csv_out_path = None

    return {"count": len(out_rows), "csv": csv_out_path, "results": out_rows}

@router.get("/debug/routes")
def debug_routes():
    return [{"path": r.path, "name": r.name} for r in router.routes]