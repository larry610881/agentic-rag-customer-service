"""Regression：bot 詳情回應的 intent_routes 讀錯 domain 欄位（Issue #100 B4）。

Issue #91 把 domain IntentRoute.system_prompt 正名為 worker_prompt，但
bot_router._to_response 仍讀 r.system_prompt → 任何設了 intent_routes 的 bot，
GET /bots/{id} 會 AttributeError（500）。對外 API 欄位名維持 system_prompt 不變。
"""

from src.domain.bot.entity import Bot, BotLLMParams, IntentRoute
from src.domain.bot.value_objects import BotId
from src.interfaces.api.bot_router import _to_response


def test_有_intent_routes_的_bot_可轉成回應且沿用_system_prompt_欄位名():
    bot = Bot(
        id=BotId(value="b1"),
        tenant_id="t1",
        name="b",
        knowledge_base_ids=["kb-1"],
        llm_params=BotLLMParams(),
        intent_routes=[
            IntentRoute(
                name="客訴", description="客訴處理", worker_prompt="請安撫客戶"
            ),
        ],
    )

    resp = _to_response(bot)

    assert resp.intent_routes == [
        {"name": "客訴", "description": "客訴處理", "system_prompt": "請安撫客戶"}
    ]
