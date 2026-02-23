"""對話管理 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.conversation.entity import Conversation

scenarios("unit/conversation/conversation_management.feature")


@pytest.fixture
def context():
    return {}


@given('一個屬於 tenant "tenant-001" 的新對話')
def new_conversation(context):
    context["conversation"] = Conversation(tenant_id="tenant-001")


@when('新增一條使用者訊息 "你好，請問退貨政策？"')
def add_user_message_policy(context):
    context["conversation"].add_message("user", "你好，請問退貨政策？")


@when('新增一條使用者訊息 "你好"')
def add_user_message_hello(context):
    context["conversation"].add_message("user", "你好")


@when('新增一條助手訊息 "您好，很高興為您服務"')
def add_assistant_message(context):
    context["conversation"].add_message("assistant", "您好，很高興為您服務")


@when("依序新增 3 條訊息")
def add_3_messages(context):
    context["conversation"].add_message("user", "問題一")
    context["conversation"].add_message("assistant", "回答一")
    context["conversation"].add_message("user", "問題二")


@then(parsers.parse("對話應包含 {count:d} 條訊息"))
def verify_message_count(context, count):
    assert len(context["conversation"].messages) == count


@then('訊息角色應為 "user"')
def verify_user_role(context):
    assert context["conversation"].messages[0].role == "user"


@then(parsers.parse('第 {index:d} 條訊息角色應為 "{role}"'))
def verify_message_role(context, index, role):
    assert context["conversation"].messages[index - 1].role == role


@then("訊息應按建立時間排序")
def verify_message_order(context):
    msgs = context["conversation"].messages
    for i in range(len(msgs) - 1):
        assert msgs[i].created_at <= msgs[i + 1].created_at
