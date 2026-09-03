"""使用者建立授權政策（Issue #67）

誰可以建立什麼角色的使用者，是 Auth 上下文的業務規則，與 HTTP 無關：

- system_admin：可建立任何角色、任何租戶的使用者。
- tenant_admin：只能在**自己的租戶**建立 user / tenant_admin。
- 其他（user、舊式租戶票、無角色）：不可建立使用者。
"""

from src.domain.auth.value_objects import Role

_TENANT_ADMIN_MAY_CREATE = frozenset({Role.USER, Role.TENANT_ADMIN})


def can_register(
    *,
    actor_role: str | None,
    actor_tenant_id: str | None,
    target_role: Role,
    target_tenant_id: str | None,
) -> bool:
    if actor_role == Role.SYSTEM_ADMIN:
        return True
    if actor_role == Role.TENANT_ADMIN:
        return (
            bool(actor_tenant_id)
            and target_tenant_id == actor_tenant_id
            and target_role in _TENANT_ADMIN_MAY_CREATE
        )
    return False
