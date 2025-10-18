"""Ollama Embeddings Client for generating embeddings using Ollama API."""

import logging
import time
from typing import List, Union, Optional
import requests
import numpy as np
from config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaEmbeddingsClient:
    """Client for generating embeddings using Ollama's embedding models."""
    
    _instance: Optional['OllamaEmbeddingsClient'] = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the Ollama embeddings client."""
        if self._initialized:
            return
            
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url
        self.model = self.settings.ollama_embedding_model
        self.embedding_dim = self.settings.embedding_dimension
        self.timeout = self.settings.ollama_timeout
        
        # Cache for embeddings
        self._cache = {}
        self._cache_enabled = True
        
        self._initialized = True
        logger.info(f"Initialized OllamaEmbeddingsClient with model: {self.model}")
    
    def embed(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings
            
        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.embedding_dim
        
        # Check cache
        if use_cache and self._cache_enabled:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                logger.debug(f"Using cached embedding for text: {text[:50]}...")
                return self._cache[cache_key]
        
        # Generate embedding
        try:
            embedding = self._generate_embedding(text)
            
            # Cache result
            if use_cache and self._cache_enabled:
                cache_key = self._get_cache_key(text)
                self._cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            use_cache: Whether to use cached embeddings
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            logger.warning("Empty text list provided for batch embedding")
            return []
        
        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")
            
            batch_embeddings = []
            for text in batch:
                embedding = self.embed(text, use_cache=use_cache)
                batch_embeddings.append(embedding)
            
            embeddings.extend(batch_embeddings)
            
            # Rate limiting - small delay between batches
            if i + batch_size < len(texts):
                time.sleep(0.1)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def _generate_embedding(self, text: str, retry_count: int = 3) -> List[float]:
        """
        Generate embedding using Ollama API with retry logic.
        
        Args:
            text: Text to embed
            retry_count: Number of retries on failure
            
        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                embedding = result.get("embedding", [])
                
                if not embedding:
                    raise ValueError("Empty embedding returned from Ollama")
                
                # Validate embedding dimension
                if len(embedding) != self.embedding_dim:
                    logger.warning(
                        f"Unexpected embedding dimension: {len(embedding)} "
                        f"(expected {self.embedding_dim})"
                    )
                    # Update the dimension setting if needed
                    self.settings.embedding_dimension = len(embedding)
                    self.embedding_dim = len(embedding)
                
                return embedding
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(2 ** attempt)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(2 ** attempt)
        
        raise RuntimeError("Max retries exceeded for embedding generation")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        # Simple hash-based key
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_size(self) -> int:
        """Get number of cached embeddings."""
        return len(self._cache)
    
    def enable_cache(self):
        """Enable embedding cache."""
        self._cache_enabled = True
        logger.info("Embedding cache enabled")
    
    def disable_cache(self):
        """Disable embedding cache."""
        self._cache_enabled = False
        logger.info("Embedding cache disabled")
    
    def check_connection(self) -> bool:
        """Check if Ollama server is accessible and model is available."""
        try:
            # Try to generate a small test embedding
            test_embedding = self._generate_embedding("test", retry_count=1)
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False
    
    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

