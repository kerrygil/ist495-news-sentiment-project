import importlib

SCRIPTS = [
    "backend.pipelines.headline_ticker_scraper",
    "backend.pipelines.historical_price_fetch",
    "backend.pipelines.cleaning_pipeline",
    "backend.pipelines.feature_engineering",
    "backend.pipelines.sentiment_pipeline",
    "backend.pipelines.aggregate_sentiment",
]

def run_full_pipeline():
    for module_name in SCRIPTS:
        print(f"Running {module_name}...")
        mod = importlib.import_module(module_name)
        if hasattr(mod, "main"):
            mod.main()
        else:
            raise Exception(f"{module_name} has no main() function.")
