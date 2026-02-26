import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.auth.jwt_service import JWTService

scenarios("unit/auth/jwt_backward_compatibility.feature")


@pytest.fixture
def jwt_service():
    return JWTService(
        secret_key="test-secret-key",
        algorithm="HS256",
        access_token_expire_minutes=60,
    )


@pytest.fixture
def context():
    return {}


@given(
    parsers.parse(
        '一個 type 為 "{token_type}" 的舊版 JWT 包含 tenant_id "{tenant_id}"'
    )
)
def old_jwt(context, jwt_service, token_type, tenant_id):
    context["token"] = jwt_service.create_tenant_token(tenant_id)


@given(
    parsers.parse(
        '一個 type 為 "{token_type}" 的新版 JWT 包含 user_id "{user_id}" tenant_id "{tenant_id}" role "{role}"'
    )
)
def new_jwt(context, jwt_service, token_type, user_id, tenant_id, role):
    context["token"] = jwt_service.create_user_token(
        user_id=user_id, tenant_id=tenant_id, role=role
    )


@when("解析此 JWT")
def decode_jwt(context, jwt_service):
    context["payload"] = jwt_service.decode_token(context["token"])


@then(parsers.parse('應取得 tenant_id "{tenant_id}"'))
def check_tenant_id(context, tenant_id):
    payload = context["payload"]
    token_type = payload.get("type")
    if token_type == "user_access":
        assert payload.get("tenant_id") == tenant_id
    else:
        assert payload.get("sub") == tenant_id


@then(parsers.parse('應取得 user_id "{user_id}"'))
def check_user_id(context, user_id):
    assert context["payload"].get("sub") == user_id


@then(parsers.parse('應取得 role "{role}"'))
def check_role(context, role):
    assert context["payload"].get("role") == role


@then("user_id 應為空")
def user_id_is_none(context):
    # Old tokens use sub for tenant_id, no user_id field
    assert context["payload"].get("type") == "tenant_access"


@then("role 應為空")
def role_is_none(context):
    assert context["payload"].get("role") is None
