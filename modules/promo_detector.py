import anthropic
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a promo detection classifier for crypto casino competitive intelligence.

Analyze tweets and determine if they contain promotional content for crypto casinos.

Respond ONLY with a JSON object, no other text:
{
  "is_promo": true/false,
  "promo_type": "race|rakeback|deposit_bonus|free_bet|tournament|referral|other|none",
  "promo_code": "code if found or empty string",
  "sentiment": "positive|negative|neutral",
  "influencer_type": "official_account|influencer|organic_user",
  "summary": "one line summary in English"
}

is_promo = true if tweet contains: promo codes, bonus offers, race/tournament announcements, 
rakeback offers, deposit bonuses, affiliate links, referral codes.
is_promo = false if tweet is just casual mention, news, or general discussion."""

class PromoDetector:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def classify(self, tweet: dict, competitor: str) -> tuple[bool, dict]:
        try:
            prompt = f"""Competitor: {competitor}
Tweet from @{tweet.get('author_handle', '')} ({tweet.get('author_followers', 0):,} followers):
"{tweet.get('text', '')}"
Likes: {tweet.get('likes', 0)} | Retweets: {tweet.get('retweets', 0)} | Replies: {tweet.get('replies', 0)}"""

            message = self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            data = json.loads(response_text)
            return data.get("is_promo", False), data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in promo detection: {e}")
            return False, {}
        except Exception as e:
            logger.error(f"Error in promo detection: {e}")
            return False, {}
