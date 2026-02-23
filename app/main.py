from fastapi import FastAPI
from app.api.routes import documents, interaction
from app.api_exception_handlers import register_exception_handlers
from app.db.session import Base, engine
from app.db.models import Document, Revision, Draft  # noqa: F401
from app.config import configure_logging
import logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

# Create all tables on startup
logger.info("Creating database tables...")
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

register_exception_handlers(app)

app.include_router(documents.router)
app.include_router(interaction.router)


@app.get("/")
def root():
    return {"status": "Drafter API running"}