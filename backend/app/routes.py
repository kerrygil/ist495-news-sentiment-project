from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models import data_models
from data.database import get_db

router = APIRouter()

@router.get("/tickers/")
def read_tickers(db: Session = Depends(get_db)):
    return db.query(data_models.Ticker).all()
