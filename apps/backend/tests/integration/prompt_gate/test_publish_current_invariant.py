"""Regression: publish 翻轉 is_current 不得違反 partial unique index（C1）。

背景：PublishConfigVersionUseCase.execute 先 `mark_published()`（把新版本
is_current 設 True）再 `save(version)`（atomic 立即 commit），此時舊 current 列
尚未清除 → 同 bot 兩列 is_current=True → 違反 partial unique index ix_bcv_current
→ IntegrityError 500。任何已有 current 版本的 bot 再次 publish 必觸發。

原本整合測試抓不到，因為 model 的 __table_args__ 未宣告該 partial index，
conftest 的 create_all 建不出約束。本測試依賴 model 現已補上該 Index 宣告，
故能在真實約束下重現崩潰。
"""

import pytest


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


@pytest.fixture
def bot_id(client, auth_headers):
    headers = _auth_only(auth_headers)
    resp = client.post("/api/v1/bots", json={"name": "gate-bot"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_and_publish(client, headers, bot_id, prompt):
    """建一個改 base_prompt 的 draft 版本並發布，回傳版本 id。"""
    created = client.post(
        f"/api/v1/bots/{bot_id}/config-versions",
        json={"changes": {"base_prompt": prompt}},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    vid = created.json()["id"]
    published = client.post(
        f"/api/v1/bots/{bot_id}/config-versions/{vid}/publish",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    return vid, published.json()


def test_second_publish_flips_current_without_index_violation(
    client, auth_headers, bot_id
):
    """已有 current 版本的 bot 再 publish 新版本應成功翻轉 current（C1 regression）。"""
    headers = _auth_only(auth_headers)

    v1_id, _ = _create_and_publish(client, headers, bot_id, "第一版提示詞")
    # 第二次 publish：修復前在此 500（v1 仍 current 時 v2 就被寫成 current）
    v2_id, v2_resp = _create_and_publish(client, headers, bot_id, "第二版提示詞")

    # 回傳的版本應標記為 current（use case 回傳前需反映 DB 翻轉結果）
    assert v2_resp["is_current"] is True, "發布後版本應為 current"

    # 版本列表：恰好一個 current，且為 v2
    listing = client.get(
        f"/api/v1/bots/{bot_id}/config-versions", headers=headers
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    current = [v for v in items if v["is_current"]]
    assert len(current) == 1, f"應恰好一個 current，實得 {len(current)}"
    assert current[0]["id"] == v2_id
    v1 = next(v for v in items if v["id"] == v1_id)
    assert v1["is_current"] is False, "舊版本應不再是 current"


def test_put_bot_prompt_change_twice_keeps_single_current(
    client, auth_headers, bot_id
):
    """PUT /bots 版控墊片：連續改 base_prompt 兩次不得撞 ix_bcv_current（C1 第二現場）。

    gate off 時每次改受版控欄位會透明產生 published+current 版本；第二次改動
    需翻轉 current，與 publish 端點同一根因（mark_published + save 先於 set_current）。
    """
    headers = _auth_only(auth_headers)

    r1 = client.put(
        f"/api/v1/bots/{bot_id}",
        json={"base_prompt": "墊片第一版"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    # 第二次：修復前在此 500
    r2 = client.put(
        f"/api/v1/bots/{bot_id}",
        json={"base_prompt": "墊片第二版"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    listing = client.get(
        f"/api/v1/bots/{bot_id}/config-versions", headers=headers
    )
    assert listing.status_code == 200, listing.text
    current = [v for v in listing.json()["items"] if v["is_current"]]
    assert len(current) == 1, f"應恰好一個 current，實得 {len(current)}"
