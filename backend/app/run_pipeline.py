import importlib

SCRIPTS = [
    "backend.scrapers.headline_ticker_scraper",
    "backend.scrapers.historical_price_fetch",
    "backend.data.cleaning_pipeline",
    "backend.data.feature_engineering",
    "backend.data.sentiment_pipeline",
    "backend.data.aggregate_sentiment",
]

def run_full_pipeline():
    for module_name in SCRIPTS:
        print(f"Running {module_name}...")
        mod = importlib.import_module(module_name)
        if hasattr(mod, "main"):
            mod.main()
        else:
            raise Exception(f"{module_name} has no main() function.")
