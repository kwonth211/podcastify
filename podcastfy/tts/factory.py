"""Factory for creating TTS providers."""

from typing import Dict, Type, Optional
from .base import TTSProvider

class TTSProviderFactory:
    """Factory class for creating TTS providers."""
    
    _providers: Dict[str, Type[TTSProvider]] = {}
    _loaded = False
    
    @classmethod
    def _load_providers(cls):
        """Lazily load providers to avoid import errors for missing packages."""
        if cls._loaded:
            return
        
        # Edge TTS (built-in)
        try:
            from .providers.edge import EdgeTTS
            cls._providers['edge'] = EdgeTTS
        except ImportError:
            pass
        
        # Gemini TTS
        try:
            from .providers.gemini import GeminiTTS
            cls._providers['gemini'] = GeminiTTS
        except ImportError:
            pass
        
        # Gemini Multi TTS
        try:
            from .providers.geminimulti import GeminiMultiTTS
            cls._providers['geminimulti'] = GeminiMultiTTS
        except ImportError:
            pass
        
        # OpenAI TTS (optional)
        try:
            from .providers.openai import OpenAITTS
            cls._providers['openai'] = OpenAITTS
        except ImportError:
            pass
        
        # ElevenLabs TTS (optional)
        try:
            from .providers.elevenlabs import ElevenLabsTTS
            cls._providers['elevenlabs'] = ElevenLabsTTS
        except ImportError:
            pass
        
        cls._loaded = True
    
    @classmethod
    def create(cls, provider_name: str, api_key: Optional[str] = None, model: Optional[str] = None) -> TTSProvider:
        """
        Create a TTS provider instance.
        
        Args:
            provider_name: Name of the provider to create
            api_key: Optional API key for the provider
            model: Optional model name for the provider
            
        Returns:
            TTSProvider instance
            
        Raises:
            ValueError: If provider_name is not supported
        """
        cls._load_providers()
        
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            raise ValueError(f"Unsupported provider: {provider_name}. "
                           f"Choose from: {', '.join(cls._providers.keys())}")
                           
        return provider_class(api_key, model) if api_key else provider_class(model=model)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[TTSProvider]) -> None:
        """Register a new provider class."""
        cls._providers[name.lower()] = provider_class
