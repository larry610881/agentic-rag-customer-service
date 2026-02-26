import bcrypt

from src.domain.auth.password_service import PasswordService


class BcryptPasswordService(PasswordService):
    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash_password(self, password: str) -> str:
        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=self._rounds),
        )
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8"),
        )
