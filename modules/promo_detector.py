import anthropic
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a promo detection classifier for crypto casino competitive intelligence.

Analyze a batch of tweets and classify each one.

Respond ONLY with a JSON array, no other text:
[
  {
    "tweet_id": "id here",
    "is_promo": true/false,
    "promo_type": "race|rakeback|deposit_bonus|free_bet|tournament|referral|other|none",
    "promo_code": "code if found or empty string",
    "sentiment": "positive|negative|neutral",
    "influencer_type": "official_account|influencer|organic_user"
  }
]

is_promo = true if tweet contains: promo codes, bonus offers, race/tournament announcements,
rakeback offers, deposit bonuses, affiliate links, referral codes.
is_promo = false if tweet is just casual mention, news, or general discussion."""

class PromoDetector:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def classify_batch(self, tweets: list, competitor: str) -> list:
        """Классифицируем все твиты одним запросом"""
        if not tweets:
            return []

        # Формируем батч
        batch_text = f"Competitor: {competitor}\n\nTweets to classify:\n"
        for tweet in tweets:
            batch_text += f"""
ID: {tweet.get('id')}
@{tweet.get('author_handle', '')} ({tweet.get('author_followers', 0):,} followers)
Text: "{tweet.get('text', '')}"
Likes: {tweet.get('likes', 0)} | RT: {tweet.get('retweets', 0)}
---"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": batch_text}]
            )

            response_text = message.content[0].text.strip()

            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            results = json.loads(response_text)
            logger.info(f"{competitor}: classified {len(results)} tweets in one API call")
            return results

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in batch classification: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in batch classification: {e}")
            return []

    async def classify(self, tweet: dict, competitor: str) -> tuple[bool, dict]:
        """Одиночная классификация — используется как fallback"""
        results = await self.classify_batch([tweet], competitor)
        if results:
            r = results[0]
            return r.get("is_promo", False), r
        return False, {}
