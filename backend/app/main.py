from fastapi import FastAPI
from app import routes
from data.database import Base, engine
import models.data_models

app = FastAPI()
app.include_router(routes.router)

# Create all tables in the database
Base.metadata.create_all(bind=engine)
