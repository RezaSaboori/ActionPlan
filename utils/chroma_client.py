"""Shared ChromaDB client to avoid multiple instance conflicts."""

import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings


class SharedChromaClient:
    """Singleton ChromaDB client."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self):
        """Get or create ChromaDB client."""
        if self._client is None:
            settings = get_settings()
            self._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        return self._client


def get_chroma_client():
    """Get shared ChromaDB client instance."""
    return SharedChromaClient().get_client()

