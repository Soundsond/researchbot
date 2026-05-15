import anthropic
import logging
from datetime import datetime, timezone
from modules.database import Database

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def generate(self, db: Database) -> str:
        promos = await db.get_promos_last_24h()
        influencers = await db.get_top_influencers(limit=5)

        if not promos:
            return self._empty_report()

        by_competitor = {}
        for p in promos:
            c = p["competitor"]
            if c not in by_competitor:
                by_competitor[c] = []
            by_competitor[c].append(p)

        ai_recommendation = await self._get_recommendation(by_competitor, influencers)

        return self._build_report(by_competitor, influencers, ai_recommendation)

    async def _get_recommendation(self, by_competitor: dict, influencers: list) -> str:
        summary = "Competitor promo activity:\n"
        for competitor, promos in by_competitor.items():
            top = sorted(promos, key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)[:2]
            for p in top:
                summary += f"- {competitor}: @{p['author_handle']} ({p['author_followers']:,} followers), "
                summary += f"{p['likes']} likes, {p['retweets']} RT, type: {p['promo_type']}, sentiment: {p['sentiment']}\n"

        message = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system="You are a crypto casino marketing analyst. Based on competitor promo data, give ONE concise recommendation in Russian (2-3 sentences max) on where to place ads. Be specific about which influencer or community to target and why.",
            messages=[{"role": "user", "content": summary}]
        )
        return message.content[0].text.strip()

    def _build_report(self, by_competitor: dict, influencers: list, recommendation: str) -> str:
        date = datetime.now(timezone.utc).strftime("%d %b %Y")

        lines = [
            f"📊 DISCORD INTEL REPORT — {date}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]

        # Новые промо за 24 часа
        lines.append("🔴 НОВЫЕ ПРОМО ЗА 24 ЧАСА")
        for competitor, promos in by_competitor.items():
            top_promos = sorted(promos, key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)[:2]
            for p in top_promos:
                lines.append(f"\n• {competitor.capitalize()} — {p['promo_type'].replace('_', ' ').title()}")
                lines.append(f"  Инфлюенсер: @{p['author_handle']} ({p['author_followers']:,} followers)")
                lines.append(f"  {p['likes']} ❤️  {p['retweets']} 🔄  {p['replies']} 💬")
                if p.get("promo_code"):
                    lines.append(f"  Промокод: {p['promo_code']}")
                lines.append(f"  Тональность: {p['sentiment']}")
                lines.append(f"  🔗 {p['url']}")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Рейтинг инфлюенсеров
        if influencers:
            lines.append("📈 ТОП ИНФЛЮЕНСЕРЫ КОНКУРЕНТОВ")
            for i, inf in enumerate(influencers, 1):
                lines.append(f"{i}. @{inf['handle']} — {inf['followers']:,} fol | "
                            f"{inf['total_promos']} промо | {inf['competitor']}")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Рекомендация
        lines.append("💡 РЕКОМЕНДАЦИЯ")
        lines.append(recommendation)

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Статистика
        total = sum(len(v) for v in by_competitor.items())
        lines.append(f"📉 ИТОГО ЗА 24Ч")
        for competitor, promos in by_competitor.items():
            eng = sum(p["likes"] + p["retweets"] * 2 for p in promos)
            lines.append(f"  {competitor.capitalize()}: {len(promos)} промо | engagement: {eng}")

        return "\n".join(lines)

    def _empty_report(self) -> str:
        date = datetime.now(timezone.utc).strftime("%d %b %Y")
        return (f"📊 INTEL REPORT — {date}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"За последние 24ч промо конкурентов не обнаружено.\n"
                f"Агент продолжает мониторинг.")
