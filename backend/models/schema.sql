-- Drop tables if they already exist (for clean re-runs)
DROP TABLE IF EXISTS sentiments CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS tickers CASCADE;
DROP TABLE IF EXISTS historical_prices CASCADE;

-- ================================
-- Table: tickers
-- ================================
CREATE TABLE tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    company_name TEXT,
    sector TEXT,
    industry TEXT
);

-- ================================
-- Table: articles
-- ================================
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    ticker_id INT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_articles_ticker_id ON articles(ticker_id);
CREATE INDEX idx_articles_published_at ON articles(published_at);

-- ================================
-- Table: sentiments
-- ================================
CREATE TABLE sentiments (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    sentiment_score NUMERIC(5,2),  -- -1.00 to +1.00
    sentiment_label VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sentiments_article_id ON sentiments(article_id);

-- ================================
-- Table: historical_prices
-- ================================
CREATE TABLE historical_prices (
    id SERIAL PRIMARY KEY,
    ticker_id INT NOT NULL,
    article_id INT NOT NULL,
    interval VARCHAR(10) NOT NULL, -- e.g. '1h', '1d'
    price NUMERIC NOT NULL,
    pct_change NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT fk_historical_prices_article FOREIGN KEY (article_id)
        REFERENCES articles (id) ON DELETE CASCADE,
    CONSTRAINT fk_historical_prices_ticker FOREIGN KEY (ticker_id)
        REFERENCES tickers (id) ON DELETE CASCADE
);

CREATE INDEX idx_historical_prices_ticker_interval ON historical_prices(ticker_id, interval);
CREATE INDEX idx_historical_prices_article_id ON historical_prices(article_id);

