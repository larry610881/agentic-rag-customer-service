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


class UnsupportedFileTypeError(DomainException):
    """Raised when an unsupported file type is uploaded."""

    def __init__(self, content_type: str) -> None:
        super().__init__(f"Unsupported file type: '{content_type}'")
        self.content_type = content_type


class DocumentProcessingError(DomainException):
    """Raised when document processing fails."""

    def __init__(self, document_id: str, reason: str) -> None:
        super().__init__(
            f"Failed to process document '{document_id}': {reason}"
        )
        self.document_id = document_id
        self.reason = reason


class NoRelevantKnowledgeError(DomainException):
    """Raised when no relevant knowledge is found for a query."""

    def __init__(self, query: str) -> None:
        super().__init__(f"No relevant knowledge found for query: '{query}'")
        self.query = query
