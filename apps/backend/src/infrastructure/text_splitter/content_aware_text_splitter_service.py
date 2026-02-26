from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService


class ContentAwareTextSplitterService(TextSplitterService):
    """Composite router that delegates to content-type-specific strategies.

    Routes ``split()`` calls to the matching strategy based on
    ``content_type``. Falls back to *default* when no strategy matches.
    """

    def __init__(
        self,
        strategies: dict[str, TextSplitterService],
        default: TextSplitterService,
    ) -> None:
        self._strategies = strategies
        self._default = default

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        strategy = self._strategies.get(content_type, self._default)
        return strategy.split(text, document_id, tenant_id, content_type)
