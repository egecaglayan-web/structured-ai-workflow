import logging

import httpx

logger = logging.getLogger(__name__)


class DemoNotifier:
    async def notify(self, request_id: str, code: str) -> bool:
        logger.warning("event=demo_owner_alert request_id=%s code=%s", request_id, code)
        return True


class WebhookNotifier:
    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout

    async def notify(self, request_id: str, code: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(
                    self.url,
                    json={"text": f"Structured workflow alert: {code}; request {request_id}."},
                    follow_redirects=False,
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            # Never log exception text: webhook URLs may contain credentials.
            logger.error("event=owner_alert_failed request_id=%s code=%s", request_id, code)
            return False
