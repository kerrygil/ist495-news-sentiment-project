# News Sentiment Analytics Dashboard
A full-stack news-sentiment analysis system that scrapes recent financial headlines, computes dictionary-based sentiment scores, aggregates ticker-level performance features, and visualizes stock performance in an interactive 3D dashboard.

This project was built for IST 495 and includes:
- **Automated scraping pipeline** (headlines, tickers, historical prices)
- **Custom sentiment dictionary & scoring engine**
- **Feature aggregation + data cleaning routines**
- **FastAPI backend** for serving recent articles & 3D analytics data
- **Next.js frontend** for a real-time dashboard with 3D visualization (Three.js)

---

## Features

### Backend (Python / FastAPI)
- Scrapes headlines and tickers from financial news sources  
- Cleans and normalizes data (deduplication, text cleaning, timestamp parsing)  
- Applies custom dictionary-based sentiment scoring  
- Computes aggregate sentiment + ticker performance metrics  
- Provides REST API endpoints:
  - `/tickers/search`
  - `/recent_articles`
  - `/analytics/ticker-performance-3d`
- Automatic scheduled scraping using APScheduler  
- Persistent PostgreSQL/SQLite database

### Frontend (Next.js)
- Displays recent news articles with pagination, sorting, and filtering  
- Plots each ticker in 3D using Three.js and SpriteText labels  
- Tooltip system for sentiment, price change, and relative volume  
- Responsive UI

---

## Project Structure

```
backend/
  app/
  data/
  models/
  pipelines/
  scrapers/
  ...

frontend/
  app/
  public/
  package.json
  next.config.ts
  ...

README.md            <- main documentation (this file)
frontend/README.md   <- frontend-specific instructions
```

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd IST495_News_Sentiment_Project
```

---

## Backend Setup

### Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Initialize the database
If using SQLite, nothing required.  
If using PostgreSQL, create your DB and update `.env`.

### Run backend
```bash
uvicorn backend.main:app --reload
```

Backend will run at:
```
http://127.0.0.1:8000
```

Scheduled scraping begins automatically on startup.

---

## Frontend Setup (Next.js)

See the **frontend/README.md** for detailed instructions.

Basic quickstart:
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:
```
http://localhost:3000
```

---

## API Endpoints (Summary)

| Endpoint                              | Description                           |
|---------------------------------------|---------------------------------------|
| `/recent_articles`                    | Paginated list of cleaned articles    |
| `/tickers/search`                     | Search tickers by symbol/name         |
| `/analytics/ticker-performance-3d`    | Aggregated 3D cluster data            |

---

## Sentiment Methodology

Sentiment is computed using:
- A weighted keyword dictionary (`data/weighted-keyword-dict.csv`)
- Normalized scoring algorithm
- Fallback scoring using NLTK VADER if needed
- Title cleaning, deduplication, normalization

---

## Visualization (3D Dashboard)

- Uses **Three.js** for rendering  
- Uses **SpriteText** to display ticker labels  
- Uses **OrbitControls** for camera navigation  
- Each point is positioned based on:
  - X = % Price Change
  - Y = Sentiment Score
  - Z = Relative Volume

