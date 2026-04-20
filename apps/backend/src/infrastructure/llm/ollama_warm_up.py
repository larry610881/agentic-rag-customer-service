"""Ollama model warm-up service

切換模型時呼叫，等到模型完全載入 VRAM 後才回傳。
Ollama 收到第一次請求時會自動 unload 舊模型、load 新模型，
此 service 透過送一個極小的 chat request 來阻塞直到完成。
"""

import httpx

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_WARM_UP_TIMEOUT = 180.0  # 14B 模型通常 60-90 秒，給足夠緩衝


class OllamaWarmUpService:
    def __init__(self, base_url: str) -> None:
        # base_url 為 Ollama 根路徑，例如 http://<pod-id>-11434.proxy.runpod.net
        self._base_url = base_url.rstrip("/")

    async def warm_up(self, model: str) -> None:
        """送最小請求強制 Ollama 將模型載入 VRAM，等待完成。"""
        logger.info("ollama.warm_up.start", model=model, base_url=self._base_url)
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "options": {"num_predict": 1},
        }
        async with httpx.AsyncClient(timeout=_WARM_UP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        logger.info("ollama.warm_up.done", model=model)
