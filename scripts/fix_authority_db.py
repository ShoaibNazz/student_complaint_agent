"""Create higher_authorities table in MySQL if not already existing."""
import logging
from app.database.database import Base, engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_db")

def main():
    logger.info("Initializing schema tables against: %s", engine.url)
    init_db(engine)
    logger.info("Database schema initialized successfully.")

if __name__ == "__main__":
    main()
