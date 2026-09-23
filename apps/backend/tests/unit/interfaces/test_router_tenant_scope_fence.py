"""Fence（Issue #101）：路徑上的租戶資源 ID 必須有擁有權檢查。

背景：Issue #100 發現 /knowledge-bases/{kb_id}/categories 底下四支端點只拿路徑 ID
查資料、沒有擁有權檢查，任何租戶都能讀別家租戶的文件切塊。認證（誰在呼叫）有
test_router_auth_fence 守著，但「呼叫者能不能碰這個 ID」是每支 handler 自己記得
做的事——這個測試把它變成結構性的預設拒絕。

判定方式（決定性，不執行 handler）：
對每條 app route、每個「租戶擁有」的路徑參數 P，在 handler 與其相依（Depends）
的函式本體做 AST 資料流分析，找「P 與呼叫者身分交會的檢查」：

- 比較式：某個由 P 衍生的值與呼叫者身分（`tenant.tenant_id`、widget principal 的
  bot…）出現在同一個比較式的不同運算元（`row.tenant_id != tenant.tenant_id`）。
- 可解析的呼叫：P 與身分一起傳進某個函式／use case 方法時，**遞迴進去**驗證那個
  函式真的做了上述檢查（只把 tenant_id 傳進去但沒比對＝不算）。
- 不可解析的呼叫（repository 介面、domain 實體方法）：P 與身分以不同引數直接一起
  傳入，視為租戶範圍查詢（`repo.find(kb_id, tenant_id=...)`、
  `server.is_accessible_to(tenant.tenant_id)`）。
- 鏈式：已通過檢查的父資源 ID（例如 bot_id）也算身分，子資源（worker_id）只要與
  它交會（`worker.bot_id != bot_id`）即可。
- 只允許 system_admin 的端點（require_role 只含 system_admin）豁免。

無法靠結構證明但實際安全的端點列在 ALLOWLIST 並附理由；清單項若已不再被標記或
端點已不存在也會 fail（清單要誠實）。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import sys
import textwrap
import typing
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.routing import APIRoute

# 路徑參數分類：新增參數時必須二選一，否則 test_every_path_param_is_classified 會紅。
TENANT_OWNED_PARAMS = {
    "bot_id",
    "case_id",
    "cat_id",
    "channel_id",
    "chunk_id",
    "config_hash",
    "conversation_id",
    "dataset_id",
    "doc_id",
    "event_id",
    "feedback_id",
    "key_id",
    "kb_id",
    "request_id",
    "run_id",
    "server_id",
    "setting_id",
    "task_id",
    "tenant_id",
    "trace_id",
    "user_id",
    "version_id",
    "worker_id",
}
NOT_TENANT_OWNED_PARAMS = {
    "bot_short_code": "公開的 LINE webhook 識別碼，由簽章驗證",
    "short_code": "公開的 widget 識別碼，由 widget 票驗證",
    "full_path": "admin SPA fallback（只在 static/admin 有建置產物時掛載）",
    "iteration": "run 底下的序號，run_id 已檢查",
    "name": "平台層級名稱（防護設定檔、工具、Milvus collection），僅 system_admin",
    "plan_id": "平台方案目錄，僅 system_admin",
    "plan_name": "平台方案目錄，僅 system_admin",
    "pricing_id": "平台計價目錄，僅 system_admin",
}

# (method, path, param) → 理由。
ALLOWLIST: dict[tuple[str, str, str], str] = {
    ("GET", "/api/v1/config-snapshots/{config_hash}", "config_hash"): (
        "內容定址（SHA-256，64 hex）且快照表無租戶欄；雜湊只經由已做租戶檢查的"
        " trace / config-timeline 回應揭露，不可列舉"
    ),
    ("PATCH", "/api/v1/admin/documents/{doc_id}/chunks/{chunk_id}", "doc_id"): (
        "路徑上的 doc_id 不參與查詢；UpdateChunkUseCase 以 chunk→doc→kb 鏈檢查"
        " chunk 的租戶，doc_id 無法用來觸及他租戶資料"
    ),
}

ADMIN_ONLY_ROLES = {"system_admin"}
# 呼叫者身分（CurrentTenant / widget principal）上不代表租戶的欄位
NON_IDENTITY_ATTRS = {"user_id", "client_id", "scopes", "is_api_client", "origin"}
# 這些呼叫即使同時帶了 ID 與 tenant，也不是擁有權檢查（記 log、排背景工作、冪等鍵）
NON_GUARD_CALLS = {
    "add_task",
    "create_task",
    "debug",
    "enqueue",
    "error",
    "exception",
    "fingerprint_parts",
    "idempotency_scope",
    "info",
    "run_idempotent",
    "warning",
}
MAX_DEPTH = 6


@pytest.fixture(scope="module")
def app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


def _iter_api_routes(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):  # FastAPI _IncludedRouter
            yield from _iter_api_routes(r.original_router.routes)
        elif hasattr(r, "routes"):
            yield from _iter_api_routes(r.routes)


def _path_params(path: str) -> list[str]:
    return re.findall(r"\{(\w+)(?::\w+)?\}", path)


# ---------------------------------------------------------------------------
# AST 資料流：一個函式內，P（資源 ID）與 I（呼叫者身分）有沒有交會的檢查
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Carriers:
    """一組存取路徑：整個名稱（"kb_id"）或欄位（"command.kb_id"）。"""

    names: frozenset[str] = frozenset()
    attrs: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.names or self.attrs)


@dataclass
class _Ctx:
    fn: Callable
    owner: type | None


def _unwrap(obj):
    obj = inspect.unwrap(obj)
    return getattr(obj, "__func__", obj)


def _func_ast(fn) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    try:
        src = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None
    tree = ast.parse(src)
    node = tree.body[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node
    return None


def _is_stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [
        s
        for s in node.body
        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
    ]
    return all(
        isinstance(s, (ast.Pass, ast.Raise))
        or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        for s in body
    )


def _contains(expr: ast.AST, c: Carriers, exclude_attrs: bool) -> bool:
    """expr 是否引用了 c 裡的任一存取路徑。"""

    def visit(n: ast.AST) -> bool:
        if _path_param_read(n) in c.names:  # request.path_params.get("doc_id")
            return True
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            base = n.value.id
            if f"{base}.{n.attr}" in c.attrs:
                return True
            if base in c.names:
                return not (exclude_attrs and n.attr in NON_IDENTITY_ATTRS)
            return False
        if isinstance(n, ast.Name):
            return n.id in c.names
        return any(visit(ch) for ch in ast.iter_child_nodes(n))

    return visit(expr)


def _path_param_read(n: ast.AST) -> str | None:
    """`x.path_params.get("P")` / `x.path_params["P"]` → "P"（相依讀路徑參數）。"""
    key = None
    if (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "path_params"
        and n.args
    ):
        key = n.args[0]
    elif (
        isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Attribute)
        and n.value.attr == "path_params"
    ):
        key = n.slice
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return key.value
    return None


def _targets(t: ast.AST) -> list[str]:
    return [n.id for n in ast.walk(t) if isinstance(n, ast.Name)]


def _ctor_name(call: ast.Call) -> str | None:
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
    return name if name[:1].isupper() else None


def _call_name(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _assign_pairs(n: ast.AST) -> list[tuple[list[str], ast.AST]]:
    """賦值類節點 → [(目標名稱, 來源運算式)]。"""
    if isinstance(n, ast.Assign):
        return [(_targets(t), n.value) for t in n.targets]
    if isinstance(n, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and n.value:
        return [(_targets(n.target), n.value)]
    if isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
        return [(_targets(n.target), n.iter)]
    if isinstance(n, ast.withitem) and n.optional_vars is not None:
        return [(_targets(n.optional_vars), n.context_expr)]
    return []


def _taint(
    node: ast.AST, p: Carriers, i: Carriers
) -> tuple[Carriers, Carriers, dict[str, ast.Call]]:
    """把由 P / I 衍生的區域變數加進各自的集合（跑到不動點）。"""
    pairs = [pair for n in ast.walk(node) for pair in _assign_pairs(n)]
    ctor_vars: dict[str, ast.Call] = {}
    for names, value in pairs:
        v = value.value if isinstance(value, ast.Await) else value
        if isinstance(v, ast.Call) and _ctor_name(v) and len(names) == 1:
            ctor_vars[names[0]] = v
    sets = [(set(p.names), p.attrs, False), (set(i.names), i.attrs, True)]
    for names_set, attrs, exclude in sets:
        changed = True
        while changed:
            changed = False
            for names, value in pairs:
                cur = Carriers(frozenset(names_set), attrs)
                if _contains(value, cur, exclude) and not set(names) <= names_set:
                    names_set |= set(names)
                    changed = True
    (pn, _, _), (inames, _, _) = sets
    return (
        Carriers(frozenset(pn), p.attrs),
        Carriers(frozenset(inames), i.attrs),
        ctor_vars,
    )


def _type_hints(fn) -> dict:
    try:
        return typing.get_type_hints(fn)
    except Exception:  # noqa: BLE001 — 前向參照解不開就退回原始註記
        return {
            k: v.annotation
            for k, v in inspect.signature(fn).parameters.items()
            if not isinstance(v.annotation, str)
        }


def _param_class(fn, name: str) -> type | None:
    """參數的類別：型別註記，或 Depends(Provide[...]) 背後 provider 的類別。"""
    hint = _type_hints(fn).get(name)
    if isinstance(hint, type) and hint is not typing.Any:
        return hint
    param = inspect.signature(fn).parameters.get(name)
    marker = getattr(getattr(param, "default", None), "dependency", None)
    provider = getattr(marker, "provider", None)
    cls = getattr(provider, "cls", None)
    return cls if isinstance(cls, type) else None


def _attr_types(cls: type) -> dict[str, type]:
    """從 __init__ 的 `self._x = param` 推出 self._x 的型別。"""
    init = cls.__dict__.get("__init__")
    node = _func_ast(init) if init is not None else None
    if node is None:
        return {}
    hints = _type_hints(init)
    out: dict[str, type] = {}
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Attribute)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "self"
            and isinstance(n.value, ast.Name)
            and isinstance(hints.get(n.value.id), type)
        ):
            out[n.targets[0].attr] = hints[n.value.id]
    return out


def _local_import(node: ast.AST, name: str):
    for n in ast.walk(node):
        if isinstance(n, ast.ImportFrom) and n.module:
            for alias in n.names:
                if (alias.asname or alias.name) == name:
                    mod = importlib.import_module(n.module)
                    return getattr(mod, alias.name, None)
    return None


def _receiver_class(recv: ast.AST, ctx: _Ctx) -> type | None:
    if isinstance(recv, ast.Name):
        if recv.id == "self":
            return ctx.owner
        return _param_class(ctx.fn, recv.id)
    if (
        isinstance(recv, ast.Attribute)
        and isinstance(recv.value, ast.Name)
        and recv.value.id == "self"
        and ctx.owner is not None
    ):
        return _attr_types(ctx.owner).get(recv.attr)
    return None


def _resolve(call: ast.Call, ctx: _Ctx, node: ast.AST):
    """回傳 (callee function, owner class, 是否為綁定方法)；解不開回 None。"""
    f = call.func
    if isinstance(f, ast.Name):
        mod = sys.modules[ctx.fn.__module__]
        target = getattr(mod, f.id, None) or _local_import(node, f.id)
        if target is not None and inspect.isfunction(_unwrap(target)):
            return _unwrap(target), None, False
        return None
    if not isinstance(f, ast.Attribute):
        return None
    cls = _receiver_class(f.value, ctx)
    meth = inspect.getattr_static(cls, f.attr, None) if cls else None
    if meth is None or not inspect.isfunction(_unwrap(meth)):
        return None
    owner = next((k for k in cls.__mro__ if f.attr in k.__dict__), cls)
    return _unwrap(meth), owner, True


def _arg_mapping(callee, bound: bool, call: ast.Call) -> dict[str, ast.AST]:
    """呼叫端引數 → callee 參數名。"""
    params = list(inspect.signature(callee).parameters.values())
    if bound and params:
        params = params[1:]
    positional = [
        x for x in params if x.kind in (x.POSITIONAL_ONLY, x.POSITIONAL_OR_KEYWORD)
    ]
    mapping: dict[str, ast.AST] = {}
    for idx, arg in enumerate(call.args):
        if isinstance(arg, ast.Starred) or idx >= len(positional):
            break
        mapping[positional[idx].name] = arg
    names = {x.name for x in params}
    mapping.update({k.arg: k.value for k in call.keywords if k.arg in names})
    return mapping


def _carrier_of(
    pname: str, expr: ast.AST, c: Carriers, exclude: bool, ctor_vars
) -> tuple[set[str], set[str]]:
    """callee 參數 pname 收到 expr 時，承載了 c 的哪些路徑（整體或欄位）。"""
    ctor = expr if isinstance(expr, ast.Call) and _ctor_name(expr) else None
    if ctor is None and isinstance(expr, ast.Name):
        ctor = ctor_vars.get(expr.id)
    if ctor is not None:  # command 物件：欄位層級追蹤
        attrs = {
            f"{pname}.{kw.arg}"
            for kw in ctor.keywords
            if kw.arg is not None and _contains(kw.value, c, exclude)
        }
        return set(), attrs
    return ({pname} if _contains(expr, c, exclude) else set()), set()


def _bind(
    callee, bound: bool, call: ast.Call, p: Carriers, i: Carriers, ctor_vars
) -> tuple[Carriers, Carriers]:
    pn, pa, inames, ia = set(), set(), set(), set()
    for pname, expr in _arg_mapping(callee, bound, call).items():
        n1, a1 = _carrier_of(pname, expr, p, False, ctor_vars)
        n2, a2 = _carrier_of(pname, expr, i, True, ctor_vars)
        pn |= n1
        pa |= a1
        inames |= n2
        ia |= a2
    return (
        Carriers(frozenset(pn), frozenset(pa)),
        Carriers(frozenset(inames), frozenset(ia)),
    )


def _meets(ops: list[ast.AST], p: Carriers, i: Carriers) -> bool:
    """P 與 I 出現在不同運算元／引數。"""
    hp = [k for k, o in enumerate(ops) if _contains(o, p, False)]
    hi = [k for k, o in enumerate(ops) if _contains(o, i, True)]
    return any(a != b for a in hp for b in hi)


def _call_guards(n: ast.Call, ctx: _Ctx, node, p, i, ctor_vars, depth, memo) -> bool:
    if _call_name(n) in NON_GUARD_CALLS or _ctor_name(n):
        return False  # 記 log／排工作／建構資料物件都不是檢查
    resolved = _resolve(n, ctx, node)
    if resolved is not None:
        callee, callee_owner, bound = resolved
        callee_node = _func_ast(callee)
        if callee_node is not None and not _is_stub(callee_node):
            cp, ci = _bind(callee, bound, n, p, i, ctor_vars)
            return bool(cp and ci) and _guards(
                callee, callee_owner, cp, ci, depth + 1, memo
            )
    # 解不開（repository 介面、domain 實體方法）：P 與 I 以不同引數一起傳入
    recv = [n.func.value] if isinstance(n.func, ast.Attribute) else []
    return _meets([*n.args, *(k.value for k in n.keywords), *recv], p, i)


def _guards(
    fn, owner: type | None, p: Carriers, i: Carriers, depth: int, memo: dict
) -> bool:
    """fn 內是否存在 P 與 I 交會的擁有權檢查。"""
    key = (fn, owner, p, i)
    if key in memo:
        return memo[key]
    memo[key] = False  # 遞迴保護
    node = _func_ast(fn)
    if node is None or depth > MAX_DEPTH:
        return False
    ctx = _Ctx(fn=fn, owner=owner)
    p, i, ctor_vars = _taint(node, p, i)
    result = any(
        _meets([n.left, *n.comparators], p, i)
        if isinstance(n, ast.Compare)
        else _call_guards(n, ctx, node, p, i, ctor_vars, depth, memo)
        for n in ast.walk(node)
        if isinstance(n, (ast.Compare, ast.Call))
    )
    memo[key] = result
    return result


def _identity_params(fn) -> set[str]:
    from src.interfaces.api.deps import CurrentTenant
    from src.interfaces.api.widget_router import WidgetPrincipal

    hints = _type_hints(fn)
    return {
        name
        for name in inspect.signature(fn).parameters
        if hints.get(name) in (CurrentTenant, WidgetPrincipal)
    }


def _required_role_sets(dependant) -> list[set[str]]:
    out: list[set[str]] = []
    for sub in dependant.dependencies:
        call = sub.call
        if getattr(call, "__qualname__", "") == "require_role.<locals>._check":
            for cell in call.__closure__ or ():
                if isinstance(cell.cell_contents, tuple):
                    out.append(set(cell.cell_contents))
        out.extend(_required_role_sets(sub))
    return out


def _sub_dependants(dependant):
    for sub in dependant.dependencies:
        yield sub
        yield from _sub_dependants(sub)


def _reads_path_param(fn, name: str) -> bool:
    node = _func_ast(fn)
    return node is not None and any(
        _path_param_read(n) == name for n in ast.walk(node)
    )


def _covered_params(route: APIRoute, owned: list[str]) -> set[str]:
    memo: dict = {}
    covered: set[str] = set()
    fns = [route.endpoint] + [
        s.call
        for s in _sub_dependants(route.dependant)
        if inspect.isfunction(_unwrap(s.call))
    ]
    changed = True
    while changed:
        changed = False
        for target in owned:
            if target in covered:
                continue
            for fn in fns:
                fn = _unwrap(fn)
                sig = inspect.signature(fn).parameters
                if target not in sig and not _reads_path_param(fn, target):
                    continue
                ident = _identity_params(fn) | (covered & set(sig))
                if not ident:
                    continue
                if _guards(
                    fn,
                    None,
                    Carriers(frozenset({target})),
                    Carriers(frozenset(ident)),
                    0,
                    memo,
                ):
                    covered.add(target)
                    changed = True
                    break
    return covered


def _scan(app) -> tuple[set, set]:
    """回傳 (未檢查的 (method, path, param), 所有被檢視的 (method, path, param))。"""
    unguarded: set[tuple[str, str, str]] = set()
    seen: set[tuple[str, str, str]] = set()
    for route in _iter_api_routes(app.routes):
        owned = [p for p in _path_params(route.path) if p in TENANT_OWNED_PARAMS]
        if not owned:
            continue
        roles = _required_role_sets(route.dependant)
        admin_only = any(r <= ADMIN_ONLY_ROLES for r in roles)
        covered = set(owned) if admin_only else _covered_params(route, owned)
        for method in route.methods:
            for p in owned:
                seen.add((method, route.path, p))
                if p not in covered:
                    unguarded.add((method, route.path, p))
    return unguarded, seen


@pytest.fixture(scope="module")
def scan(app):
    return _scan(app)


def test_every_tenant_owned_path_param_has_ownership_check(scan):
    unguarded, _ = scan
    leaked = sorted(unguarded - set(ALLOWLIST))
    assert leaked == [], (
        "path IDs without a detectable tenant ownership check "
        f"(fix the endpoint or add ALLOWLIST entry with a reason): {leaked}"
    )


def test_allowlist_is_honest(scan):
    unguarded, seen = scan
    missing = sorted(set(ALLOWLIST) - seen)
    assert missing == [], f"ALLOWLIST entries that no longer exist: {missing}"
    stale = sorted(set(ALLOWLIST) - unguarded)
    assert stale == [], f"ALLOWLIST entries that are now guarded: {stale}"


# 依部署產物有條件掛載的路由參數：不存在時不算清單過期。CI 後端 job 與乾淨的
# worktree 沒有 build:embed 產物，_mount_admin_spa 不掛 /{full_path:path}
# （同 test_router_auth_fence.py 的 CONDITIONAL_ROUTES）。
CONDITIONAL_PARAMS = {"full_path"}

def test_every_path_param_is_classified(app):
    params = {
        p for r in _iter_api_routes(app.routes) for p in _path_params(r.path)
    }
    unknown = sorted(params - TENANT_OWNED_PARAMS - set(NOT_TENANT_OWNED_PARAMS))
    assert unknown == [], (
        "new path params must be classified as tenant-owned or not: "
        f"{unknown}"
    )
    stale = sorted(
        (TENANT_OWNED_PARAMS | set(NOT_TENANT_OWNED_PARAMS))
        - params
        - CONDITIONAL_PARAMS
    )
    assert stale == [], f"classified params no longer used: {stale}"


def test_scan_covers_the_tenant_owned_surface(scan):
    _, seen = scan
    assert len(seen) > 100, "route scan lost the included routers"


# ---------------------------------------------------------------------------
# 分析器自身的正反例：確保它真的會抓 Issue #100 那一類漏洞
# ---------------------------------------------------------------------------


class _Repo:
    async def find_by_id(self, _id: str): ...


class _UseCaseChecks:
    def __init__(self, repo: _Repo) -> None:
        self._repo = repo

    async def execute(self, kb_id: str, tenant_id: str):
        kb = await self._repo.find_by_id(kb_id)
        if kb.tenant_id != tenant_id:
            raise LookupError
        return kb


class _UseCaseIgnoresTenant:
    def __init__(self, repo: _Repo) -> None:
        self._repo = repo

    async def execute(self, kb_id: str, tenant_id: str):
        return await self._repo.find_by_id(kb_id)


async def _h_no_tenant(kb_id: str, tenant, repo: _Repo):
    return await repo.find_by_id(kb_id)


async def _h_compare(kb_id: str, tenant, repo: _Repo):
    kb = await repo.find_by_id(kb_id)
    if kb.tenant_id != tenant.tenant_id:
        raise LookupError
    return kb


async def _h_delegates_ok(kb_id: str, tenant, uc: _UseCaseChecks):
    return await uc.execute(kb_id, tenant.tenant_id)


async def _h_delegates_but_ignored(kb_id: str, tenant, uc: _UseCaseIgnoresTenant):
    return await uc.execute(kb_id, tenant.tenant_id)


async def _h_user_id_is_not_tenant(kb_id: str, tenant, repo: _Repo):
    kb = await repo.find_by_id(kb_id)
    if kb.owner != tenant.user_id:
        raise LookupError
    return kb


@pytest.mark.parametrize(
    ("handler", "expected"),
    [
        (_h_no_tenant, False),
        (_h_compare, True),
        (_h_delegates_ok, True),
        (_h_delegates_but_ignored, False),
        (_h_user_id_is_not_tenant, False),
    ],
)
def test_analyzer_distinguishes_real_checks(handler, expected):
    got = _guards(
        handler,
        None,
        Carriers(frozenset({"kb_id"})),
        Carriers(frozenset({"tenant"})),
        0,
        {},
    )
    assert got is expected
