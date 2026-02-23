from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


class JWTService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes

    def create_tenant_token(self, tenant_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._access_token_expire_minutes
        )
        payload = {
            "sub": tenant_id,
            "exp": expire,
            "type": "tenant_access",
        }
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}") from e
