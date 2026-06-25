# app/web_scraper/init_db.py

from app.web_scraper.db import init_db

if __name__ == "__main__":
    init_db()
    print("✅ Database tables created successfully.")