from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import data_models
from data.database import get_db

router = APIRouter()

@router.get("/test-db-connection")
def test_db_connection(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        return {"status": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/tickers/")
def read_tickers(db: Session = Depends(get_db)):
    return db.query(data_models.Ticker).all()
