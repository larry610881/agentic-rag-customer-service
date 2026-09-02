"""Redis LINE webhook 事件去重（Issue #58）

``SET line:evt:{webhookEventId} 1 NX EX ttl``：第一次寫入成功 → 認領；
已存在 → redelivery 重送，跳過。Redis 不可用時 fail-open（視為第一次），
重送造成的重複回覆比訊息丟失可接受。
"""

import structlog

from src.domain.line.services import WebhookEventDeduplicator

logger = structlog.get_logger(__name__)


class RedisWebhookEventDeduplicator(WebhookEventDeduplicator):
    def __init__(self, redis_client, ttl_seconds: int = 3600) -> None:  # noqa: ANN001
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def claim(self, event_id: str) -> bool:
        try:
            result = await self._redis.set(
                f"line:evt:{event_id}", "1", nx=True, ex=self._ttl
            )
        except Exception:
            logger.warning("line.webhook.dedup_redis_unavailable", event_id=event_id)
            return True
        return result is not None
