from sqlalchemy import Column, Integer, Numeric, String, Text, ForeignKey, Float, DateTime, func
from sqlalchemy.orm import relationship
from data.database import Base 

class Ticker(Base):
    __tablename__ = 'tickers'
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False)
    company_name = Column(Text)
    sector = Column(Text)
    industry = Column(Text)
    
    historical_prices = relationship("HistoricalPrice", back_populates="ticker")
    news_articles = relationship("Article", back_populates="ticker")


class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey('tickers.id', ondelete='CASCADE'))
    title = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    published_at = Column(DateTime)
    
    ticker = relationship("Ticker", back_populates="news_articles")
    sentiments = relationship("Sentiment", back_populates="article")
    historical_prices = relationship("HistoricalPrice", back_populates="article")


class HistoricalPrice(Base):
    __tablename__ = "historical_prices"

    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    interval = Column(String(10), nullable=False)
    price = Column(Numeric, nullable=False)
    pct_change = Column(Numeric)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    article = relationship("Article", back_populates="historical_prices")
    ticker = relationship("Ticker", back_populates="historical_prices")

class Sentiment(Base):
    __tablename__ = 'sentiments'

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('articles.id', ondelete='CASCADE'))
    sentiment_label = Column(String(20), nullable=False)
    sentiment_score = Column(Float, nullable=False)

    article = relationship("Article", back_populates="sentiments")