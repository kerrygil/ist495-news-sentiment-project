import pandas as pd
from sqlalchemy.orm import Session
from backend.data.database import SessionLocal
from backend.models.data_models import Ticker

def update_ticker_metadata():
    # Load the finviz CSV file
    finviz_path = "backend/data/finviz.csv"
    finviz_df = pd.read_csv(finviz_path)
    finviz_df["Ticker"] = finviz_df["Ticker"].str.upper()

    # Create a mapping for quick lookup
    finviz_map = finviz_df.set_index("Ticker")[["Company", "Sector", "Industry"]].to_dict(orient="index")

    db: Session = SessionLocal()

    updated_count = 0
    skipped_count = 0

    tickers = db.query(Ticker).all()

    for ticker in tickers:
        sym = ticker.symbol.upper().strip()

        if sym in finviz_map:
            info = finviz_map[sym]

            # Only update if fields are missing or empty
            needs_update = False
            if not ticker.company_name and info["Company"]:
                ticker.company_name = info["Company"]
                needs_update = True
            if not ticker.sector and info["Sector"]:
                ticker.sector = info["Sector"]
                needs_update = True
            if not ticker.industry and info["Industry"]:
                ticker.industry = info["Industry"]
                needs_update = True

            if needs_update:
                db.add(ticker)
                updated_count += 1
            else:
                skipped_count += 1
        else:
            skipped_count += 1

    db.commit()
    db.close()

    print(f"✅ Updated {updated_count} tickers with metadata.")
    print(f"⚪ Skipped {skipped_count} (already complete or missing in CSV).")

if __name__ == "__main__":
    update_ticker_metadata()
