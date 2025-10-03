from data.database import SessionLocal, SQLALCHEMY_DATABASE_URL
from models.data_models import Ticker


db = SessionLocal()
print("📡 Using DB:", SQLALCHEMY_DATABASE_URL)

new_ticker = Ticker(symbol="ZZZZ", company_name="Test Insert Inc")
db.add(new_ticker)
db.commit()
db.refresh(new_ticker)

print("✅ Inserted ticker:", new_ticker.id, new_ticker.symbol)
print("🔑 Current tickers count:", db.query(Ticker).count())

db.close()
