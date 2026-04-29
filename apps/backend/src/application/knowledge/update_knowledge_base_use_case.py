from dataclasses import dataclass

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.domain.knowledge.repository import KnowledgeBaseRepository


@dataclass(frozen=True)
class UpdateKnowledgeBaseCommand:
    kb_id: str
    # 必填（router 從 token 拿）— default 空字串保舊 caller backward compat
    requester_tenant_id: str = ""
    name: str | None = None
    description: str | None = None
    ocr_mode: str | None = None
    ocr_model: str | None = None
    context_model: str | None = None
    classification_model: str | None = None


class UpdateKnowledgeBaseUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._repo = knowledge_base_repository

    async def execute(self, command: UpdateKnowledgeBaseCommand) -> None:
        # 之前完全無 tenant 檢查 → 任意 tenant 知道 kb_id 就能改任意 KB（CRITICAL）
        # ensure_kb_accessible: 同租戶 OK / system_admin bypass OK / 跨租戶 → 404
        await ensure_kb_accessible(
            self._repo, command.kb_id, command.requester_tenant_id
        )
        fields = {
            k: v
            for k, v in {
                "name": command.name,
                "description": command.description,
                "ocr_mode": command.ocr_mode,
                "ocr_model": command.ocr_model,
                "context_model": command.context_model,
                "classification_model": command.classification_model,
            }.items()
            if v is not None
        }
        if fields:
            await self._repo.update(command.kb_id, **fields)
