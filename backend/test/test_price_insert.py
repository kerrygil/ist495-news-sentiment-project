import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import sys
from pathlib import Path 
# Add the backend folder to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.database import SessionLocal, engine, Base
from models.data_models import Ticker, Article, HistoricalPrice
from scrapers.historical_price_fetch import insert_price_data


@pytest.fixture(scope="function")
def db_session():
    """Provide a new database session per test, rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session  # run the test

    session.close()
    transaction.rollback()
    connection.close()


def test_insert_price_data(db_session: Session):
    # Setup: create ticker + article with FK
    ticker = Ticker(symbol="TEST")
    db_session.add(ticker)
    db_session.commit()  # flush so ticker.id is available

    article = Article(
        ticker_id=ticker.id,
        url="http://example.com",
        title="Test Article"
    )
    db_session.add(article)
    db_session.commit()

    # Insert historical price data
    price_data = {
        "1h": {"price": 100.0, "pct_change": 0.0},
        "EOD": {"price": 102.0, "pct_change": 2.0}
    }

    inserted, skipped = insert_price_data(
        db_session, ticker_id=ticker.id, article_id=article.id, price_data=price_data
    )

    assert inserted == 2
    assert skipped == 0
