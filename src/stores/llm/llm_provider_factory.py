from src.enums.llm_enums import LLMEnums
from src.helpers.config import Settings
from .providers.cohere_provider import CoHereProvider
from .providers.openai_provider import OpenAIProvider


class LLMProviderFactory:
    def __init__(self, config: Settings):
        self.config = config
        
    def create(self, provider: str):
        if provider == LLMEnums.OPENAI.value:
            return OpenAIProvider(
                api_key=self.config.OPENAI_API_KEY,
                api_url=self.config.OPENAI_API_URL,
                input_max_characters=self.config.INPUT_MAX_CHARACTERS,
                output_max_tokens=self.config.OUTPUT_MAX_TOKENS,
                temperature=self.config.TEMPERATURE
            )
            
        
        if provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key=self.config.COHERE_API_KEY,
                input_max_characters=self.config.INPUT_MAX_CHARACTERS,
                output_max_tokens=self.config.OUTPUT_MAX_TOKENS,
                temperature=self.config.TEMPERATURE
            )
        return None