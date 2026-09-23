from src.domain.knowledge.services import LanguageDetectionService


class LangdetectLanguageDetectionService(LanguageDetectionService):
    """Infrastructure adapter: language detection via ``langdetect`` library."""

    def detect(self, text: str) -> str:
        from langdetect import LangDetectException, detect

        try:
            # langdetect 無型別標註；detect() 實際回傳 ISO 語言代碼字串
            language: str = detect(text[:1000])
            return language
        except LangDetectException:
            return "unknown"
