"""BDD Step Definitions — Notification Channel Management."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.observability.notification_use_cases import (
    CreateChannelCommand,
    CreateChannelUseCase,
    DispatchNotificationUseCase,
    NotificationDispatcher,
    SendTestNotificationUseCase,
)
from src.domain.observability.error_event import ErrorEvent
from src.domain.observability.notification import (
    NotificationChannel,
    NotificationChannelRepository,
    NotificationSender,
    NotificationThrottleService,
)
from src.domain.platform.services import EncryptionService

scenarios("unit/observability/notification_channel.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture()
def context():
    return {}


# -----------------------------------------------------------------------
# Scenario: 建立 email 通知渠道（config 加密存儲）
# -----------------------------------------------------------------------


@given("管理員提供 email 渠道設定")
def admin_provides_email_config(context):
    repo = AsyncMock(spec=NotificationChannelRepository)
    repo.save.side_effect = lambda ch: ch
    enc = MagicMock(spec=EncryptionService)
    enc.encrypt.return_value = "encrypted_blob"
    context["repo"] = repo
    context["enc"] = enc
    context["command"] = CreateChannelCommand(
        channel_type="email",
        name="Ops Email",
        enabled=True,
        config={"smtp_host": "smtp.example.com", "recipients": ["ops@test.com"]},
    )


@when("建立 email 通知渠道", target_fixture="create_result")
def create_email_channel(context):
    uc = CreateChannelUseCase(
        channel_repo=context["repo"],
        encryption_service=context["enc"],
    )
    return _run(uc.execute(context["command"]))


@then("渠道應建立成功")
def verify_channel_created(create_result):
    assert create_result is not None
    assert create_result.channel_type == "email"
    assert create_result.name == "Ops Email"


@then("config 應被加密存儲")
def verify_config_encrypted(context, create_result):
    context["enc"].encrypt.assert_called_once()
    assert create_result.config_encrypted == "encrypted_blob"


# -----------------------------------------------------------------------
# Scenario: 啟用通知時新錯誤觸發寄信
# -----------------------------------------------------------------------


@given("一個已啟用的 email 通知渠道")
def setup_enabled_email(context):
    channel = NotificationChannel(
        id="ch-1",
        channel_type="email",
        name="Ops Email",
        enabled=True,
        throttle_minutes=15,
    )
    channel_repo = AsyncMock(spec=NotificationChannelRepository)
    channel_repo.list_enabled.return_value = [channel]

    throttle = AsyncMock(spec=NotificationThrottleService)
    throttle.is_throttled.return_value = False
    throttle.record_sent.return_value = None

    sender = AsyncMock(spec=NotificationSender)
    sender.channel_type.return_value = "email"
    dispatcher = NotificationDispatcher(senders={"email": sender})

    context["channel_repo"] = channel_repo
    context["throttle"] = throttle
    context["dispatcher"] = dispatcher
    context["sender"] = sender


@when("新錯誤事件發生並觸發通知分派", target_fixture="dispatch_result")
def dispatch_notification(context):
    event = ErrorEvent(
        id="evt-1",
        fingerprint="fp-test",
        source="backend",
        error_type="RuntimeError",
        message="Something broke",
        path="/api/v1/agent/chat",
    )
    uc = DispatchNotificationUseCase(
        channel_repo=context["channel_repo"],
        throttle_service=context["throttle"],
        dispatcher=context["dispatcher"],
    )
    _run(uc.execute(event))
    return True


@then("應呼叫 email sender 發送通知")
def verify_email_sent(context):
    context["sender"].send.assert_called_once()


# -----------------------------------------------------------------------
# Scenario: Throttle 時間內不重複寄信
# -----------------------------------------------------------------------


@given("一個已啟用的 email 通知渠道且 throttle 為 15 分鐘")
def setup_throttled_channel(context):
    channel = NotificationChannel(
        id="ch-1",
        channel_type="email",
        name="Ops Email",
        enabled=True,
        throttle_minutes=15,
    )
    channel_repo = AsyncMock(spec=NotificationChannelRepository)
    channel_repo.list_enabled.return_value = [channel]

    throttle = AsyncMock(spec=NotificationThrottleService)
    throttle.is_throttled.return_value = False
    throttle.record_sent.return_value = None

    sender = AsyncMock(spec=NotificationSender)
    sender.channel_type.return_value = "email"
    dispatcher = NotificationDispatcher(senders={"email": sender})

    context["channel_repo"] = channel_repo
    context["throttle"] = throttle
    context["dispatcher"] = dispatcher
    context["sender"] = sender


@given("throttle 服務判定該 fingerprint 已被節流")
def setup_throttled(context):
    context["throttle"].is_throttled.return_value = True


@when(
    "同一 fingerprint 的新錯誤觸發通知分派",
    target_fixture="throttle_result",
)
def dispatch_throttled_notif(context):
    event = ErrorEvent(
        id="evt-2",
        fingerprint="fp-throttle",
        source="backend",
        error_type="RuntimeError",
        message="Same error",
    )
    uc = DispatchNotificationUseCase(
        channel_repo=context["channel_repo"],
        throttle_service=context["throttle"],
        dispatcher=context["dispatcher"],
    )
    _run(uc.execute(event))
    return True


@then("不應呼叫 email sender")
def verify_no_email(context):
    context["sender"].send.assert_not_called()


# -----------------------------------------------------------------------
# Scenario: 發送測試通知
# -----------------------------------------------------------------------


@given("一個已建立的 email 通知渠道")
def setup_existing_channel(context):
    channel = NotificationChannel(
        id="ch-test",
        channel_type="email",
        name="Test Channel",
        enabled=False,
    )
    repo = AsyncMock(spec=NotificationChannelRepository)
    repo.get_by_id.return_value = channel

    enc = MagicMock(spec=EncryptionService)
    enc.decrypt.return_value = '{"smtp_host": "smtp.example.com"}'

    sender = AsyncMock(spec=NotificationSender)
    sender.channel_type.return_value = "email"
    dispatcher = NotificationDispatcher(senders={"email": sender})

    context["repo"] = repo
    context["enc"] = enc
    context["dispatcher"] = dispatcher
    context["sender"] = sender


@when("管理員觸發測試通知", target_fixture="test_result")
def trigger_test_notification(context):
    uc = SendTestNotificationUseCase(
        channel_repo=context["repo"],
        encryption_service=context["enc"],
        dispatcher=context["dispatcher"],
    )
    _run(uc.execute("ch-test"))
    return True


@then("應呼叫 email sender 發送測試郵件")
def verify_test_email_sent(context):
    context["sender"].send.assert_called_once()
    call_args = context["sender"].send.call_args
    assert "Test" in call_args[0][1]  # subject contains "Test"


# -----------------------------------------------------------------------
# Scenario: 多個 channel 都 enabled 時全部發送
# -----------------------------------------------------------------------


@given("兩個已啟用的通知渠道（email 和 slack）")
def setup_multi_channels(context):
    email_channel = NotificationChannel(
        id="ch-email",
        channel_type="email",
        name="Email",
        enabled=True,
        throttle_minutes=15,
    )
    slack_channel = NotificationChannel(
        id="ch-slack",
        channel_type="slack",
        name="Slack",
        enabled=True,
        throttle_minutes=15,
    )
    channel_repo = AsyncMock(spec=NotificationChannelRepository)
    channel_repo.list_enabled.return_value = [email_channel, slack_channel]

    throttle = AsyncMock(spec=NotificationThrottleService)
    throttle.is_throttled.return_value = False
    throttle.record_sent.return_value = None

    email_sender = AsyncMock(spec=NotificationSender)
    email_sender.channel_type.return_value = "email"
    slack_sender = AsyncMock(spec=NotificationSender)
    slack_sender.channel_type.return_value = "slack"

    dispatcher = NotificationDispatcher(
        senders={"email": email_sender, "slack": slack_sender}
    )

    context["channel_repo"] = channel_repo
    context["throttle"] = throttle
    context["dispatcher"] = dispatcher
    context["email_sender"] = email_sender
    context["slack_sender"] = slack_sender


@when("新錯誤事件觸發通知分派", target_fixture="multi_result")
def dispatch_multi(context):
    event = ErrorEvent(
        id="evt-multi",
        fingerprint="fp-multi",
        source="backend",
        error_type="RuntimeError",
        message="Multi-channel error",
    )
    uc = DispatchNotificationUseCase(
        channel_repo=context["channel_repo"],
        throttle_service=context["throttle"],
        dispatcher=context["dispatcher"],
    )
    _run(uc.execute(event))
    return True


@then("兩個 sender 都應被呼叫")
def verify_both_senders(context):
    context["email_sender"].send.assert_called_once()
    context["slack_sender"].send.assert_called_once()
