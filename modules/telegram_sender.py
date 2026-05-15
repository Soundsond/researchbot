import httpx
import logging

logger = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def send(self, text: str):
        # Telegram лимит 4096 символов — разбиваем если нужно
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

        async with httpx.AsyncClient() as client:
            for chunk in chunks:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "disable_web_page_preview": True
                    },
                    timeout=30
                )
                if response.status_code != 200:
                    logger.error(f"Telegram error: {response.text}")
                else:
                    logger.info("Message sent to Telegram")
