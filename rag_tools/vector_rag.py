"""Vector-based RAG using ChromaDB for semantic search."""

import logging
from typing import List, Dict, Any, Optional
# Lazy import to avoid SSL issues with sentence-transformers
# from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient
from utils.chroma_client import get_chroma_client
import logging

logger = logging.getLogger(__name__)


class VectorRAG:
    """Semantic vector-based RAG using ChromaDB."""
    
    def __init__(self, collection_name: str = "documents", markdown_logger=None):
        """
        Initialize VectorRAG with ChromaDB.
        
        Args:
            collection_name: ChromaDB collection name
            markdown_logger: Optional MarkdownLogger instance
        """
        self.settings = get_settings()
        self.collection_name = collection_name
        self.markdown_logger = markdown_logger
        
        # Use shared ChromaDB client to avoid multiple instance conflicts
        self.client = get_chroma_client()
        self.collection = self.client.get_or_create_collection(self.collection_name)
        
        # Initialize embedding model - use Ollama embeddings instead of sentence-transformers
        # to avoid SSL/OpenSSL issues
        self.embedding_client = OllamaEmbeddingsClient()
        self.embedding_model = None  # Legacy field, no longer used
        
        logger.info(f"Initialized VectorRAG with ChromaDB collection: {collection_name} (using Ollama embeddings)")
    
    def create_collection(self):
        """Create ChromaDB collection if it doesn't exist (handled by get_or_create_collection)."""
        logger.info(f"Collection '{self.collection_name}' is ready.")
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using embeddings.
        
        Args:
            query: Search query text
            top_k: Number of results
            filter_metadata: Optional metadata filters
            
        Returns:
            List of search results with metadata
        """
        # Use Ollama embeddings instead of sentence-transformers
        query_vector = self.embedding_client.embed(query)
        
        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filter_metadata
            )
            
            formatted_results = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    metadata = results['metadatas'][0][i]
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'score': 1 - results['distances'][0][i] if results['distances'] else 0,
                        'text': metadata.get('text', ''),
                        'metadata': metadata
                    })
            
            logger.info(f"Found {len(formatted_results)} results for query: {query[:50]}...")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> None:
        """
        Add documents to the ChromaDB store.
        
        Args:
            documents: List of document dictionaries with 'text' and 'metadata'
        """
        if not documents:
            return

        ids = []
        embeddings = []
        metadatas = []
        
        for idx, doc in enumerate(documents):
            text = doc['text']
            metadata = doc.get('metadata', {})
            
            # Use Ollama embeddings instead of sentence-transformers
            vector = self.embedding_client.embed(text)
            
            ids.append(str(metadata.get('chunk_id', idx)))
            embeddings.append(vector)
            metadatas.append({**metadata, 'text': text})

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Added {len(ids)} documents to {self.collection_name}")
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise
    
    def delete_collection(self):
        """Delete the collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")

