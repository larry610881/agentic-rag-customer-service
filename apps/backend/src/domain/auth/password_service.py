from abc import ABC, abstractmethod


class PasswordService(ABC):
    @abstractmethod
    def hash_password(self, password: str) -> str: ...

    @abstractmethod
    def verify_password(self, password: str, hashed: str) -> bool: ...
