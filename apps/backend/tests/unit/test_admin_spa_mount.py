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
