import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.database import SessionLocal, SQLALCHEMY_DATABASE_URL
from models.data_models import Ticker


def test_insert_ticker_data():
    db = SessionLocal()
    print("📡 Using DB:", SQLALCHEMY_DATABASE_URL)

    # Insert a test ticker
    new_ticker = Ticker(symbol="ZZZZ", company_name="Test Insert Inc")
    db.add(new_ticker)
    db.commit()
    db.refresh(new_ticker)

    assert new_ticker.id is not None
    assert new_ticker.symbol == "ZZZZ"

    print(f"✅ Inserted ticker: {new_ticker.id}, {new_ticker.symbol}")

    # Verify it exists
    count = db.query(Ticker).filter_by(symbol="ZZZZ").count()
    assert count == 1
    print("🔑 Current tickers count:", db.query(Ticker).count())

    # Clean up so it’s re-runnable
    db.delete(new_ticker)
    db.commit()

    # Confirm cleanup
    assert db.query(Ticker).filter_by(symbol="ZZZZ").count() == 0
    db.close()
