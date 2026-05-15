import os
import asyncio
import logging
import httpx
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from modules.twitter_monitor import TwitterMonitor
from modules.promo_detector import PromoDetector
from modules.report_generator import ReportGenerator
from modules.telegram_sender import TelegramSender
from modules.database import Database

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COMPETITORS = {
    "rollbit": {"keywords": ["rollbit promo", "rollbit race", "rollbit bonus", "rollbit code"]},
    "shuffle": {"keywords": ["shuffle.com promo", "shuffle casino bonus", "shufflecom code", "shuffle rakeback"]},
    "stake":   {"keywords": ["stake.com promo", "stake casino bonus", "stake race", "stake code"]},
    "roobet":  {"keywords": ["roobet promo", "roobet bonus", "roobet code", "roobet casino"]}
}

is_running = False

async def run_monitoring_cycle(db, monitor, detector):
    global is_running
    if is_running:
        logger.info("Monitoring already running, skipping")
        return
    is_running = True
    try:
        logger.info("Starting monitoring cycle...")
        for competitor, config in COMPETITORS.items():
            try:
                tweets = await monitor.search_promo_tweets(
                    keywords=config["keywords"],
                    competitor=competitor
                )
                if not tweets:
                    continue
                results = await detector.classify_batch(tweets, competitor)
                saved = 0
                results_by_id = {r.get("tweet_id"): r for r in results}
                for tweet in tweets:
                    promo_data = results_by_id.get(tweet["id"], {})
                    if promo_data.get("is_promo"):
                        await db.save_promo(tweet, promo_data, competitor)
                        saved += 1
                logger.info(f"{competitor}: {len(tweets)} tweets checked, {saved} promos saved")
            except Exception as e:
                logger.error(f"Error monitoring {competitor}: {e}")
    finally:
        is_running = False

async def run_daily_report(db, generator, sender):
    logger.info("Generating daily report...")
    try:
        report = await generator.generate(db)
        await sender.send(report)
        logger.info("Daily report sent")
    except Exception as e:
        logger.error(f"Error generating report: {e}")

async def handle_telegram_commands(sender, db, generator, monitor, detector):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base_url = f"https://api.telegram.org/bot{token}"

    # Получаем текущий offset чтобы пропустить старые команды
    last_update_id = 0
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/getUpdates",
                params={"offset": -1},
                timeout=10
            )
            data = response.json()
            updates = data.get("result", [])
            if updates:
                last_update_id = updates[-1]["update_id"]
                logger.info(f"Skipping old commands, starting from update_id: {last_update_id}")
    except Exception as e:
        logger.error(f"Error getting initial offset: {e}")

    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": last_update_id + 1, "timeout": 30},
                    timeout=35
                )
                data = response.json()

                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "")
                    from_chat = str(message.get("chat", {}).get("id", ""))

                    if from_chat != chat_id:
                        continue

                    if text == "/report":
                        await sender.send("⏳ Собираю данные и генерирую отчёт...")
                        await run_monitoring_cycle(db, monitor, detector)
                        await run_daily_report(db, generator, sender)

                    elif text == "/status":
                        await sender.send("✅ Агент работает. Мониторинг активен.")

        except Exception as e:
            logger.error(f"Telegram command error: {e}")
            await asyncio.sleep(5)

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
    # Мониторинг 2 раза в день
    scheduler.add_job(run_monitoring_cycle, 'cron', hour='8,20', args=[db, monitor, detector])
    # Дейли отчёт
    scheduler.add_job(run_daily_report, 'cron', hour=report_hour, minute=0, args=[db, generator, sender])
    scheduler.start()

    logger.info(f"Agent started. Report at {report_hour}:00 UTC daily.")
    await handle_telegram_commands(sender, db, generator, monitor, detector)

if __name__ == "__main__":
    asyncio.run(main())
