from src.domain.knowledge.services import LanguageDetectionService


class LangdetectLanguageDetectionService(LanguageDetectionService):
    """Infrastructure adapter: language detection via ``langdetect`` library."""

    def detect(self, text: str) -> str:
        from langdetect import LangDetectException, detect

        try:
            return detect(text[:1000])
        except LangDetectException:
            return "unknown"
