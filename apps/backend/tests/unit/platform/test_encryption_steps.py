"""AES 加密服務 BDD Step Definitions"""

import os

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService

scenarios("unit/platform/encryption.feature")


@pytest.fixture
def context():
    return {}


@given("一個 AES 加密服務")
def aes_service(context):
    key = os.urandom(32).hex()
    context["service"] = AESEncryptionService(master_key=key)


@when(parsers.parse('我加密 "{plaintext}"'))
def encrypt_text(context, plaintext):
    context["encrypted"] = context["service"].encrypt(plaintext)


@when("我解密加密後的結果")
def decrypt_text(context):
    context["decrypted"] = context["service"].decrypt(context["encrypted"])


@when(parsers.parse('我加密 "{plaintext}" 兩次'))
def encrypt_twice(context, plaintext):
    context["encrypted_1"] = context["service"].encrypt(plaintext)
    context["encrypted_2"] = context["service"].encrypt(plaintext)


@then(parsers.parse('解密結果應為 "{expected}"'))
def decrypted_matches(context, expected):
    assert context["decrypted"] == expected


@then("兩次加密結果應不同")
def encryptions_differ(context):
    assert context["encrypted_1"] != context["encrypted_2"]
