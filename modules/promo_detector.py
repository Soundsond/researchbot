import anthropic
import json
import logging

logger = logging.getLogger(__name__)

# Фильтр до Claude — только твиты с этими словами идут на классификацию
PROMO_KEYWORDS = [
    "promo", "code", "bonus", "race", "rakeback", "deposit", "free bet",
    "giveaway", "win", "cashback", "tournament", "reward", "offer",
    "claim", "exclusive", "deal", "referral", "affiliate"
]

SYSTEM_PROMPT = """You are a promo detection classifier for crypto casino competitive intelligence.

Analyze a batch of tweets and classify each one IN ORDER.

Respond ONLY with a JSON array with exactly the same number of items as tweets provided, no other text:
[
  {
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

    def _prefilter(self, tweets: list) -> tuple[list, list]:
        """Фильтруем твиты до Claude — только вероятные промо"""
        likely_promos = []
        skipped = []
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            if any(kw in text for kw in PROMO_KEYWORDS):
                likely_promos.append(tweet)
            else:
                skipped.append(tweet)
        logger.info(f"Pre-filter: {len(likely_promos)} likely promos, {len(skipped)} skipped")
        return likely_promos, skipped

    async def classify_batch(self, tweets: list, competitor: str) -> list:
        if not tweets:
            return []

        # Фильтруем до Claude
        filtered, skipped = self._prefilter(tweets)

        results = []

        # Пропущенные твиты — сразу помечаем как не промо
        for tweet in skipped:
            results.append({
                "tweet_id": tweet["id"],
                "is_promo": False,
                "promo_type": "none",
                "promo_code": "",
                "sentiment": "neutral",
                "influencer_type": "organic_user"
            })

        if not filtered:
            return results

        # Только отфильтрованные идут в Claude
        batch_text = f"Competitor: {competitor}\n\nTweets to classify (in order):\n"
        for i, tweet in enumerate(filtered):
            batch_text += f"""
#{i+1}
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

            classified = json.loads(response_text)

            for i, result in enumerate(classified):
                if i < len(filtered):
                    result["tweet_id"] = filtered[i]["id"]
                    results.append(result)

            logger.info(f"{competitor}: {len(filtered)} tweets sent to Claude, {sum(1 for r in classified if r.get('is_promo'))} promos found")
            return results

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in batch classification: {e}")
            return results
        except Exception as e:
            logger.error(f"Error in batch classification: {e}")
            return results
