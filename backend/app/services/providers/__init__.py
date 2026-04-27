"""第三方 provider 封装导出。"""

from app.services.providers.funasr_provider import FunASRProviderClient
from app.services.providers.openai_provider import OpenAIProviderClient
from app.services.providers.ollama_provider import OllamaProviderClient
from app.services.providers.paddlespeech_provider import PaddleSpeechProviderClient

__all__ = [
	"OpenAIProviderClient",
	"OllamaProviderClient",
	"FunASRProviderClient",
	"PaddleSpeechProviderClient",
]
