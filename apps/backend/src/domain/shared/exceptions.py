class DomainException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str = "A domain error occurred") -> None:
        self.message = message
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(f"{entity_type} with id '{entity_id}' not found")
        self.entity_type = entity_type
        self.entity_id = entity_id


class DuplicateEntityError(DomainException):
    """Raised when an entity with the same unique constraint already exists."""

    def __init__(self, entity_type: str, field: str, value: str) -> None:
        super().__init__(
            f"{entity_type} with {field} '{value}' already exists"
        )
        self.entity_type = entity_type
        self.field = field
        self.value = value
