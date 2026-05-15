import httpx
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class TwitterMonitor:
    def __init__(self, bearer_token: str):
        self.api_key = bearer_token
        self.base_url = "https://api.socialdata.tools/twitter"
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json"
        }

    async def search_promo_tweets(self, keywords: list, competitor: str) -> list:
        # SocialData использует стандартные Twitter search операторы
        query = " OR ".join([f'"{kw}"' for kw in keywords])
        query += " -is:retweet lang:en"

        params = {
            "query": query,
            "type": "Latest"
        }

        results = []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning(f"Rate limit hit for {competitor}")
                return []

            if response.status_code != 200:
                logger.error(f"SocialData API error {response.status_code}: {response.text}")
                return []

            data = response.json()
            tweets = data.get("tweets", [])

            for tweet in tweets:
                user = tweet.get("user", {})
                results.append({
                    "id": str(tweet.get("id_str", "")),
                    "text": tweet.get("full_text", ""),
                    "created_at": tweet.get("tweet_created_at", ""),
                    "author_handle": user.get("screen_name", ""),
                    "author_followers": user.get("followers_count", 0),
                    "likes": tweet.get("favorite_count", 0),
                    "retweets": tweet.get("retweet_count", 0),
                    "replies": tweet.get("reply_count", 0),
                    "url": f"https://twitter.com/{user.get('screen_name', '')}/status/{tweet.get('id_str', '')}"
                })

        logger.info(f"Found {len(results)} tweets for {competitor}")
        return results
