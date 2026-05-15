import os
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
from modules.twitter_monitor import TwitterMonitor
from modules.promo_detector import PromoDetector
from modules.report_generator import ReportGenerator
from modules.telegram_sender import TelegramSender
from modules.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COMPETITORS = {
    "rollbit": {
        "twitter_handle": "rollbit",
        "keywords": ["rollbit", "rlb", "rollbit race", "rollbit promo"]
    },
    "shuffle": {
        "twitter_handle": "shufflecom",
        "keywords": ["shuffle.com", "shufflecom", "shuffle casino", "shfl"]
    },
    "stake": {
        "twitter_handle": "stake",
        "keywords": ["stake.com", "stake casino", "stake promo", "stake race"]
    },
    "roobet": {
        "twitter_handle": "roobetcom",
        "keywords": ["roobet", "roobet.com", "roobet promo", "roobet casino"]
    }
}

async def run_monitoring_cycle(db: Database, monitor: TwitterMonitor, detector: PromoDetector):
    logger.info("Starting monitoring cycle...")
    for competitor, config in COMPETITORS.items():
        try:
            tweets = await monitor.search_promo_tweets(
                keywords=config["keywords"],
                competitor=competitor
            )
            for tweet in tweets:
                is_promo, promo_data = await detector.classify(tweet, competitor)
                if is_promo:
                    await db.save_promo(tweet, promo_data, competitor)
                    logger.info(f"Saved promo for {competitor}: {tweet['id']}")
        except Exception as e:
            logger.error(f"Error monitoring {competitor}: {e}")

async def run_daily_report(db: Database, generator: ReportGenerator, sender: TelegramSender):
    logger.info("Generating daily report...")
    try:
        report = await generator.generate(db)
        await sender.send(report)
        logger.info("Daily report sent successfully")
    except Exception as e:
        logger.error(f"Error generating report: {e}")

async def main():
    db = Database()
    await db.init()

    monitor = TwitterMonitor(bearer_token=os.environ["TWITTER_BEARER_TOKEN"])
    detector = PromoDetector(api_key=os.environ["ANTHROPIC_API_KEY"])
    generator = ReportGenerator(api_key=os.environ["ANTHROPIC_API_KEY"])
    sender = TelegramSender(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"]
    )

    report_hour = int(os.environ.get("REPORT_HOUR_UTC", "11"))

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Мониторинг каждые 2 часа
    scheduler.add_job(
        run_monitoring_cycle,
        'interval',
        hours=2,
        args=[db, monitor, detector]
    )

    # Дейли отчёт
    scheduler.add_job(
        run_daily_report,
        'cron',
        hour=report_hour,
        minute=0,
        args=[db, generator, sender]
    )

    scheduler.start()
    logger.info(f"Agent started. Monitoring {len(COMPETITORS)} competitors. Report at {report_hour}:00 UTC")

    # Первый цикл сразу при старте
    await run_monitoring_cycle(db, monitor, detector)

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent stopped")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
