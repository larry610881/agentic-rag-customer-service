"""回饋匯出用例"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.shared.pii_masking import mask_pii_in_text, mask_user_id


class ExportFeedbackUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self,
        tenant_id: str,
        *,
        format: str = "json",
        days: int = 90,
        mask_pii: bool = False,
    ) -> str:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        feedbacks = await self._feedback_repo.find_by_date_range(
            tenant_id, start, end
        )

        rows = []
        for f in feedbacks:
            row = {
                "id": f.id.value,
                "conversation_id": f.conversation_id,
                "message_id": f.message_id,
                "user_id": (
                    mask_user_id(f.user_id) if mask_pii else (f.user_id or "")
                ),
                "channel": f.channel.value,
                "rating": f.rating.value,
                "comment": (
                    mask_pii_in_text(f.comment) if mask_pii else (f.comment or "")
                ),
                "tags": ",".join(f.tags),
                "created_at": f.created_at.isoformat(),
            }
            rows.append(row)

        if format == "csv":
            output = io.StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            return output.getvalue()

        return json.dumps(rows, ensure_ascii=False, indent=2)
