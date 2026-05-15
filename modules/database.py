import os
import json
import aiosqlite
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "agent.db")

class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    competitor TEXT,
                    author_handle TEXT,
                    author_followers INTEGER,
                    tweet_text TEXT,
                    tweet_url TEXT,
                    likes INTEGER,
                    retweets INTEGER,
                    replies INTEGER,
                    promo_type TEXT,
                    promo_code TEXT,
                    sentiment TEXT,
                    collected_at TEXT,
                    tweet_created_at TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS influencers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handle TEXT UNIQUE,
                    followers INTEGER,
                    competitor TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    total_promos INTEGER DEFAULT 1
                )
            """)
            await db.commit()
        logger.info("Database initialized")

    async def save_promo(self, tweet: dict, promo_data: dict, competitor: str):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO promos 
                    (tweet_id, competitor, author_handle, author_followers, tweet_text, 
                     tweet_url, likes, retweets, replies, promo_type, promo_code, 
                     sentiment, collected_at, tweet_created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tweet["id"],
                    competitor,
                    tweet.get("author_handle", ""),
                    tweet.get("author_followers", 0),
                    tweet.get("text", ""),
                    tweet.get("url", ""),
                    tweet.get("likes", 0),
                    tweet.get("retweets", 0),
                    tweet.get("replies", 0),
                    promo_data.get("promo_type", "unknown"),
                    promo_data.get("promo_code", ""),
                    promo_data.get("sentiment", "neutral"),
                    datetime.now(timezone.utc).isoformat(),
                    tweet.get("created_at", "")
                ))

                # Обновляем таблицу инфлюенсеров
                handle = tweet.get("author_handle", "")
                if handle:
                    await db.execute("""
                        INSERT INTO influencers (handle, followers, competitor, first_seen, last_seen)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(handle) DO UPDATE SET
                            followers = excluded.followers,
                            last_seen = excluded.last_seen,
                            total_promos = total_promos + 1
                    """, (
                        handle,
                        tweet.get("author_followers", 0),
                        competitor,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    ))

                await db.commit()
            except Exception as e:
                logger.error(f"Error saving promo: {e}")

    async def get_promos_last_24h(self) -> list:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM promos 
                WHERE collected_at > ?
                ORDER BY likes + retweets DESC
            """, (since,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_top_influencers(self, limit=10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT handle, followers, competitor, total_promos, last_seen
                FROM influencers
                ORDER BY total_promos DESC, followers DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
