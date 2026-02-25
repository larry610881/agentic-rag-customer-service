import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.domain.platform.services import EncryptionService


class AESEncryptionService(EncryptionService):
    """AES-256-GCM encryption with random 96-bit nonce."""

    def __init__(self, master_key: str) -> None:
        self._key = bytes.fromhex(master_key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._key)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()

    def decrypt(self, ciphertext: str) -> str:
        data = base64.b64decode(ciphertext)
        nonce, ct = data[:12], data[12:]
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(nonce, ct, None).decode()
