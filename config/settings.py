"""Configuration settings for the LLM Agent Orchestration System."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Neo4j Configuration
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER")
    neo4j_password: str = Field(default="cardiosmartai", env="NEO4J_PASSWORD")
    
    # ChromaDB Configuration
    chroma_path: str = Field(default="./chroma_storage", env="CHROMA_PATH")
    
    # Ollama Configuration
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gpt-oss:20b", env="OLLAMA_MODEL")
    ollama_temperature: float = Field(default=0.1, env="OLLAMA_TEMPERATURE")
    ollama_timeout: int = Field(default=3000, env="OLLAMA_TIMEOUT")
    
    # Translation Configuration
    translator_model: str = Field(default="gemma3:27b", env="TRANSLATOR_MODEL")
    dictionary_path: str = Field(default="/storage03/Saboori/ActionPlan/Agents/dataset/Dictionary.md", env="DICTIONARY_PATH")
    segmentation_chunk_size: int = Field(default=500, env="SEGMENTATION_CHUNK_SIZE")
    term_context_window: int = Field(default=3, env="TERM_CONTEXT_WINDOW")  # sentences before/after
    
    # Document Paths (Unified - same directory for all documents)
    docs_dir: str = Field(default="/storage03/Saboori/ActionPlan/HELD/docs", env="DOCS_DIR")
    
    # Embedding Model (SentenceTransformer - legacy)
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL"
    )
    
    # Ollama Embedding Configuration
    ollama_embedding_model: str = Field(
        default="embeddinggemma:latest",
        env="OLLAMA_EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=768, env="EMBEDDING_DIMENSION")
    
    # RAG Configuration
    chunk_size: int = Field(default=400, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="CHUNK_OVERLAP")
    top_k_results: int = Field(default=5, env="TOP_K_RESULTS")
    max_section_tokens: int = Field(default=1000, env="MAX_SECTION_TOKENS")
    
    # Retrieval Modes per Agent
    analyzer_retrieval_mode: str = Field(default="automatic", env="ANALYZER_RETRIEVAL_MODE")
    assigner_retrieval_mode: str = Field(default="summary", env="ASSIGNER_RETRIEVAL_MODE")
    prioritizer_retrieval_mode: str = Field(default="content", env="PRIORITIZER_RETRIEVAL_MODE")
    
    # Workflow Configuration
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    quality_threshold: float = Field(default=0.7, env="QUALITY_THRESHOLD")
    
    # Validator Configuration
    max_validator_retries: int = Field(default=2, env="MAX_VALIDATOR_RETRIES")
    validator_quality_threshold: float = Field(default=0.8, env="VALIDATOR_QUALITY_THRESHOLD")
    enable_self_repair: bool = Field(default=True, env="ENABLE_SELF_REPAIR")
    
    # ChromaDB Collection Names (Unified)
    summary_collection_name: str = Field(default="summaries", env="SUMMARY_COLLECTION_NAME")
    content_collection_name: str = Field(default="documents", env="CONTENT_COLLECTION_NAME")
    documents_collection: str = Field(default="health_documents", env="DOCUMENTS_COLLECTION")
    dictionary_collection: str = Field(default="dictionary", env="DICTIONARY_COLLECTION")
    
    # Neo4j Graph Name (Unified)
    graph_prefix: str = Field(default="health", env="GRAPH_PREFIX")
    dictionary_graph_prefix: str = Field(default="dictionary", env="DICTIONARY_GRAPH_PREFIX")
    
    # Rule Documents List (for identifying which docs are rules)
    rule_document_names: list = Field(
        default=["Comprehensive Health System Preparedness and Response Plan under Sanctions and War Conditions", "Checklist Template Guide", "National Health System Response Plan for Disasters and Emergencies_General Guides"],
        env="RULE_DOCUMENT_NAMES"
    )
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # phase3 Configuration (Multi-Phase Deep Analysis)
    phase3_score_threshold: float = Field(default=0.5, env="PHASE3_SCORE_THRESHOLD")
    phase3_max_depth: int = Field(default=3, env="PHASE3_MAX_DEPTH")
    phase3_initial_top_k: int = Field(default=10, env="PHASE3_INITIAL_TOP_K")
    phase3_min_nodes_per_subject: int = Field(default=3, env="PHASE3_MIN_NODES_PER_SUBJECT")
    
    # Analyzer Configuration (2-Phase Workflow)
    analyzer_context_sample_lines: int = Field(default=10, env="ANALYZER_CONTEXT_SAMPLE_LINES")
    analyzer_d_score_threshold: float = Field(default=0.7, env="ANALYZER_D_SCORE_THRESHOLD")
    analyzer_d_max_depth: int = Field(default=3, env="ANALYZER_D_MAX_DEPTH")
    analyzer_d_initial_top_k: int = Field(default=10, env="ANALYZER_D_INITIAL_TOP_K")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

