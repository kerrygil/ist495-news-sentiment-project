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
- Persistent PostgreSQL database

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

### 1. Python Version

This project was developed and tested using **Python 3.13**, you must have it installed **both**:

1. On your system (global install) - so that the virtual environment can be created
2. Inside your virtual environment (venv) - where the backend actually rns

If you do not already have Python 3.13 installed, download it from: https://www.python.org/downloads/

After installation, verify:
```bash
python3 --version 
# or with Windows:
python --version
```

### 2. Clone the Repository
```bash
git clone https://github.com/kerrygil/ist495-news-sentiment-project.git
cd IST495-News-Sentiment-Project
```

### 3. PostgreSQL Version

This project was developed using **PostgreSQL 17.x**.

You may install **any 17-series version**, including the most recent **17.7**, which is fully compatible and recommended due to security patches and bug fixes.

If you do not already have PostgreSQL 17, download it from: https://www.postgresql.org/download/

(Do *not* install PostgreSQL 18.x unless you want to run your own upgraded environment; the project does not require any PostgreSQL 18 features.)

---

## Backend Setup

### Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### Install dependencies
```bash
cd backend
pip install -r requirements.txt
cd ..
```

### Creating the PostgreSQL database
If the database does not exist, create it manually:

```bash
psql -U postgres
CREATE DATABASE sentiment_dev;
\q
```

### Initialize the database
In PostgreSQL, create your DB and update `.env`. The schema will automatically be applied when upon the first run of the application.

### Environment Variables (`.env`)

The backend requires a `.env` file in the **project root** to configure the database connection.  
This file is intentionally excluded from version control via `.gitignore`, so you must create it manually.

Create a new file named **`.env`** in the project root and include the following:

```
# Path to your Python interpreter (optional, used for development tools)
PYTHON_PATH=<path-to-python>

# PostgreSQL database configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>
POSTGRES_DB=sentiment_dev
```

### Notes:
- `POSTGRES_PASSWORD` must be replaced with **your personal PostgreSQL password**.  
- Ensure your database is running before starting the backend.
- `POSTGRES_DB` can be anything but must match your database name.

### Example (Windows)
```
PYTHON_PATH=C:\Users\<yourname>\AppData\Local\Programs\Python\Python313\python.exe
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourPasswordHere
POSTGRES_DB=sentiment_dev
```

### Run backend
```bash
uvicorn backend.app.main:app --reload
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

Uvicorn must be running at the same time, in a separate PowerShell window, in order for the frontend to load.

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

