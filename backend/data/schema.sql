-- Drop tables if they already exist (for clean re-runs)
DROP TABLE IF EXISTS sentiments CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS tickers CASCADE;

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
    url TEXT,
    published_at TIMESTAMPTZ NOT NULL
);

-- ================================
-- Table: sentiments
-- ================================
CREATE TABLE sentiments (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    sentiment_score NUMERIC(5,2),  -- example: -1.00 to +1.00
    sentiment_label VARCHAR(20),   -- e.g., 'positive', 'neutral', 'negative'
    model_version TEXT,            -- which ML model generated it
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================
-- Table: historical prices
-- ================================
CREATE TABLE public.historical_prices (
    id serial,
    ticker_id integer NOT NULL,
    article_id integer NOT NULL,
    "interval" character varying(10)[] NOT NULL,
    price numeric NOT NULL,
    pct_change numeric,
    created_at timestamp with time zone DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT article_id FOREIGN KEY (article_id)
        REFERENCES public.articles (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
        NOT VALID,
    CONSTRAINT ticker_id FOREIGN KEY (ticker_id)
        REFERENCES public.tickers (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
        NOT VALID
);
