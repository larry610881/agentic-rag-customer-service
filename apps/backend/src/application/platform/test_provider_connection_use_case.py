import time
from dataclasses import dataclass

import httpx

from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ProviderName
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class TestConnectionResult:
    success: bool
    latency_ms: int
    error: str = ""


# Minimal test endpoints per provider
_TEST_ENDPOINTS: dict[str, str] = {
    ProviderName.OPENAI.value: "https://api.openai.com/v1/models",
    ProviderName.ANTHROPIC.value: "https://api.anthropic.com/v1/models",
    ProviderName.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
    ProviderName.GOOGLE.value: "https://generativelanguage.googleapis.com/v1beta/models",
    ProviderName.OPENROUTER.value: "https://openrouter.ai/api/v1/models",
}


class CheckProviderConnectionUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service

    async def execute(self, setting_id: str) -> TestConnectionResult:
        setting = await self._repository.find_by_id(setting_id)
        if setting is None:
            raise EntityNotFoundError("ProviderSetting", setting_id)

        if setting.provider_name == ProviderName.FAKE:
            return TestConnectionResult(success=True, latency_ms=0)

        api_key = self._encryption.decrypt(setting.api_key_encrypted)
        base_url = setting.base_url or _TEST_ENDPOINTS.get(
            setting.provider_name.value, ""
        )
        if not base_url:
            return TestConnectionResult(
                success=False, latency_ms=0, error="No test endpoint configured"
            )

        headers: dict[str, str] = {}
        if setting.provider_name == ProviderName.ANTHROPIC:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(base_url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code < 400:
                    return TestConnectionResult(success=True, latency_ms=latency)
                return TestConnectionResult(
                    success=False,
                    latency_ms=latency,
                    error=f"HTTP {resp.status_code}",
                )
        except httpx.HTTPError as e:
            latency = int((time.monotonic() - start) * 1000)
            return TestConnectionResult(
                success=False, latency_ms=latency, error=str(e)
            )
