import httpx
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class TwitterMonitor:
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
        self.headers = {"Authorization": f"Bearer {bearer_token}"}

    async def search_promo_tweets(self, keywords: list, competitor: str) -> list:
        query = " OR ".join([f'"{kw}"' for kw in keywords])
        query += " -is:retweet lang:en"

        # Последние 24 часа
        start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "query": query,
            "start_time": start_time,
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,author_id,text",
            "expansions": "author_id",
            "user.fields": "username,public_metrics"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tweets/search/recent",
                headers=self.headers,
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning(f"Rate limit hit for {competitor}")
                return []

            if response.status_code != 200:
                logger.error(f"Twitter API error {response.status_code}: {response.text}")
                return []

            data = response.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            results = []
            for tweet in tweets:
                author = users.get(tweet.get("author_id", ""), {})
                metrics = tweet.get("public_metrics", {})
                results.append({
                    "id": tweet["id"],
                    "text": tweet["text"],
                    "created_at": tweet.get("created_at", ""),
                    "author_handle": author.get("username", ""),
                    "author_followers": author.get("public_metrics", {}).get("followers_count", 0),
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "url": f"https://twitter.com/{author.get('username', '')}/status/{tweet['id']}"
                })

            logger.info(f"Found {len(results)} tweets for {competitor}")
            return results
