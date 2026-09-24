"""_mount_admin_spa — 同源 admin SPA 回退路由（前端與後端同一 Cloud Run）。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.main import _mount_admin_spa


def _build(tmp_path: Path, *, with_admin: bool = True) -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "api"}

    if with_admin:
        admin = tmp_path / "admin"
        (admin / "assets").mkdir(parents=True)
        (admin / "index.html").write_text("<html>SPA</html>")
        (admin / "assets" / "app.js").write_text("console.log(1)")
    _mount_admin_spa(app, str(tmp_path))
    return TestClient(app)


def test_unknown_path_falls_back_to_index(tmp_path: Path) -> None:
    client = _build(tmp_path)
    r = client.get("/admin/bots/123")
    assert r.status_code == 200
    assert "SPA" in r.text


def test_existing_asset_is_served_directly(tmp_path: Path) -> None:
    client = _build(tmp_path)
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert r.text == "console.log(1)"


def test_api_routes_still_win_and_unknown_api_is_404(tmp_path: Path) -> None:
    client = _build(tmp_path)
    assert client.get("/api/v1/ping").json() == {"ok": "api"}
    assert client.get("/api/v1/nope").status_code == 404
    assert client.get("/static/nope.js").status_code == 404


def test_path_traversal_does_not_escape_admin_dir(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("nope")
    client = _build(tmp_path)
    r = client.get("/../secret.txt")
    assert "nope" not in r.text  # 回退到 index.html，不外洩


def test_no_admin_build_means_no_catch_all(tmp_path: Path) -> None:
    client = _build(tmp_path, with_admin=False)
    assert client.get("/anything").status_code == 404


def test_non_frontend_paths_get_json_404_not_index(tmp_path: Path) -> None:
    """#470075：/health 被回退接走回 200 + index.html，Release 健康檢查永遠成功。

    健康檢查、API、靜態檔、文件這類非前端路徑一律 404 JSON，不回 SPA。
    """
    client = _build(tmp_path)
    # /docs、/redoc 由 FastAPI 自己的路由先接（測試 app 也有），不在此驗
    for path in ("/health", "/health/", "/api", "/static", "/api/v2/x"):
        r = client.get(path)
        assert r.status_code == 404, path
        assert r.headers["content-type"].startswith("application/json"), path
        assert "SPA" not in r.text, path


def test_frontend_routes_sharing_a_reserved_prefix_still_fall_back(
    tmp_path: Path,
) -> None:
    """保留字比對以路徑段為單位：/healthcare、/apis 這類前端路由仍回 SPA。"""
    client = _build(tmp_path)
    for path in ("/healthcare", "/apis", "/docs-center"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "SPA" in r.text, path
