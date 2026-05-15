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

        # Группируем по конкуренту
        by_competitor = {}
        for p in promos:
            c = p["competitor"]
            if c not in by_competitor:
                by_competitor[c] = []
            by_competitor[c].append(p)

        # Топ промо по engagement
        top_promos = sorted(promos, key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)[:5]

        # Формируем данные для Claude
        data_summary = self._format_data_for_claude(by_competitor, top_promos, influencers)

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="""You are a crypto casino competitive intelligence analyst.
Generate a concise daily Telegram report in Russian based on the data provided.
Use emojis for readability. Keep it focused on actionable insights.
Format: plain text suitable for Telegram (no markdown headers, use emojis instead).
Always end with a concrete recommendation on where to place ads.""",
            messages=[{"role": "user", "content": data_summary}]
        )

        ai_analysis = message.content[0].text

        # Собираем итоговый отчёт
        report = self._build_report(by_competitor, top_promos, influencers, ai_analysis)
        return report

    def _format_data_for_claude(self, by_competitor, top_promos, influencers) -> str:
        lines = ["DATA FOR ANALYSIS:\n"]

        lines.append("PROMOS BY COMPETITOR:")
        for competitor, promos in by_competitor.items():
            total_engagement = sum(p["likes"] + p["retweets"] for p in promos)
            lines.append(f"- {competitor.upper()}: {len(promos)} promos, total engagement: {total_engagement}")
            for p in sorted(promos, key=lambda x: x["likes"] + x["retweets"], reverse=True)[:3]:
                lines.append(f"  @{p['author_handle']} ({p['author_followers']:,} followers): "
                           f"{p['likes']} likes, {p['retweets']} RT, type: {p['promo_type']}, "
                           f"sentiment: {p['sentiment']}")
                if p.get('promo_code'):
                    lines.append(f"  Promo code: {p['promo_code']}")

        lines.append("\nTOP INFLUENCERS BY ACTIVITY:")
        for inf in influencers:
            lines.append(f"- @{inf['handle']}: {inf['followers']:,} followers, "
                        f"{inf['total_promos']} promos for {inf['competitor']}")

        return "\n".join(lines)

    def _build_report(self, by_competitor, top_promos, influencers, ai_analysis) -> str:
        date = datetime.now(timezone.utc).strftime("%d %b %Y")
        total_promos = sum(len(v) for v in by_competitor.values())

        lines = [
            f"📊 COMPETITOR PROMO REPORT — {date}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Всего промо за 24ч: {total_promos}",
            ""
        ]

        # По каждому конкуренту
        lines.append("🔴 АКТИВНОСТЬ КОНКУРЕНТОВ:")
        for competitor, promos in by_competitor.items():
            total_eng = sum(p["likes"] + p["retweets"] * 2 for p in promos)
            lines.append(f"\n{competitor.upper()} — {len(promos)} промо, engagement: {total_eng}")
            top = sorted(promos, key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)[:2]
            for p in top:
                lines.append(f"  @{p['author_handle']} ({p['author_followers']:,} fol)")
                lines.append(f"  {p['likes']} ❤️  {p['retweets']} 🔄  {p['replies']} 💬")
                lines.append(f"  Тип: {p['promo_type']} | {p['sentiment']}")
                if p.get("promo_code"):
                    lines.append(f"  Код: {p['promo_code']}")
                lines.append(f"  🔗 {p['url']}")

        # Топ инфлюенсеры
        if influencers:
            lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("👥 ТОП ИНФЛЮЕНСЕРЫ КОНКУРЕНТОВ:")
            for i, inf in enumerate(influencers[:5], 1):
                lines.append(f"{i}. @{inf['handle']} — {inf['followers']:,} fol | "
                           f"{inf['total_promos']} промо | {inf['competitor']}")

        # AI анализ
        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 АНАЛИЗ И РЕКОМЕНДАЦИИ:")
        lines.append(ai_analysis)

        return "\n".join(lines)

    def _empty_report(self) -> str:
        date = datetime.now(timezone.utc).strftime("%d %b %Y")
        return (f"📊 COMPETITOR PROMO REPORT — {date}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"За последние 24ч промо конкурентов не обнаружено.\n"
                f"Агент продолжает мониторинг.")
