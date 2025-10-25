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

    # OpenAI-compatible API Configuration (Legacy - for backward compatibility)
    gapgpt_api_key: Optional[str] = Field(default=None, env="GAPGPT_API_KEY")
    gapgpt_api_base: Optional[str] = Field(default=None, env="GAPGPT_API_BASE")
    
    # Per-Agent LLM Configuration
    # Orchestrator
    orchestrator_provider: str = Field(default="ollama", env="ORCHESTRATOR_PROVIDER")
    orchestrator_model: str = Field(default="gpt-oss:20b", env="ORCHESTRATOR_MODEL")
    orchestrator_temperature: float = Field(default=0.1, env="ORCHESTRATOR_TEMPERATURE")
    orchestrator_api_key: Optional[str] = Field(default=None, env="ORCHESTRATOR_API_KEY")
    orchestrator_api_base: Optional[str] = Field(default=None, env="ORCHESTRATOR_API_BASE")
    
    # Analyzer
    analyzer_provider: str = Field(default="ollama", env="ANALYZER_PROVIDER")
    analyzer_model: str = Field(default="gpt-oss:20b", env="ANALYZER_MODEL")
    analyzer_temperature: float = Field(default=0.1, env="ANALYZER_TEMPERATURE")
    analyzer_api_key: Optional[str] = Field(default=None, env="ANALYZER_API_KEY")
    analyzer_api_base: Optional[str] = Field(default=None, env="ANALYZER_API_BASE")
    
    # Extractor
    extractor_provider: str = Field(default="ollama", env="EXTRACTOR_PROVIDER")
    extractor_model: str = Field(default="gpt-oss:20b", env="EXTRACTOR_MODEL")
    extractor_temperature: float = Field(default=0.1, env="EXTRACTOR_TEMPERATURE")
    extractor_api_key: Optional[str] = Field(default=None, env="EXTRACTOR_API_KEY")
    extractor_api_base: Optional[str] = Field(default=None, env="EXTRACTOR_API_BASE")
    
    # Deduplicator
    deduplicator_provider: str = Field(default="ollama", env="DEDUPLICATOR_PROVIDER")
    deduplicator_model: str = Field(default="gpt-oss:20b", env="DEDUPLICATOR_MODEL")
    deduplicator_temperature: float = Field(default=0.1, env="DEDUPLICATOR_TEMPERATURE")
    deduplicator_api_key: Optional[str] = Field(default=None, env="DEDUPLICATOR_API_KEY")
    deduplicator_api_base: Optional[str] = Field(default=None, env="DEDUPLICATOR_API_BASE")
    
    # Selector
    selector_provider: str = Field(default="ollama", env="SELECTOR_PROVIDER")
    selector_model: str = Field(default="gpt-oss:20b", env="SELECTOR_MODEL")
    selector_temperature: float = Field(default=0.2, env="SELECTOR_TEMPERATURE")
    selector_api_key: Optional[str] = Field(default=None, env="SELECTOR_API_KEY")
    selector_api_base: Optional[str] = Field(default=None, env="SELECTOR_API_BASE")
    
    # Prioritizer
    prioritizer_provider: str = Field(default="ollama", env="PRIORITIZER_PROVIDER")
    prioritizer_model: str = Field(default="gpt-oss:20b", env="PRIORITIZER_MODEL")
    prioritizer_temperature: float = Field(default=0.1, env="PRIORITIZER_TEMPERATURE")
    prioritizer_api_key: Optional[str] = Field(default=None, env="PRIORITIZER_API_KEY")
    prioritizer_api_base: Optional[str] = Field(default=None, env="PRIORITIZER_API_BASE")
    
    # Assigner
    assigner_provider: str = Field(default="ollama", env="ASSIGNER_PROVIDER")
    assigner_model: str = Field(default="gpt-oss:20b", env="ASSIGNER_MODEL")
    assigner_temperature: float = Field(default=0.1, env="ASSIGNER_TEMPERATURE")
    assigner_api_key: Optional[str] = Field(default=None, env="ASSIGNER_API_KEY")
    assigner_api_base: Optional[str] = Field(default=None, env="ASSIGNER_API_BASE")
    
    # Quality Checker
    quality_checker_provider: str = Field(default="ollama", env="QUALITY_CHECKER_PROVIDER")
    quality_checker_model: str = Field(default="gpt-oss:20b", env="QUALITY_CHECKER_MODEL")
    quality_checker_temperature: float = Field(default=0.1, env="QUALITY_CHECKER_TEMPERATURE")
    quality_checker_api_key: Optional[str] = Field(default=None, env="QUALITY_CHECKER_API_KEY")
    quality_checker_api_base: Optional[str] = Field(default=None, env="QUALITY_CHECKER_API_BASE")
    
    # Formatter
    formatter_provider: str = Field(default="ollama", env="FORMATTER_PROVIDER")
    formatter_model: str = Field(default="gpt-oss:20b", env="FORMATTER_MODEL")
    formatter_temperature: float = Field(default=0.1, env="FORMATTER_TEMPERATURE")
    formatter_api_key: Optional[str] = Field(default=None, env="FORMATTER_API_KEY")
    formatter_api_base: Optional[str] = Field(default=None, env="FORMATTER_API_BASE")
    
    # Phase3
    phase3_provider: str = Field(default="ollama", env="PHASE3_PROVIDER")
    phase3_model: str = Field(default="gpt-oss:20b", env="PHASE3_MODEL")
    phase3_temperature: float = Field(default=0.1, env="PHASE3_TEMPERATURE")
    phase3_api_key: Optional[str] = Field(default=None, env="PHASE3_API_KEY")
    phase3_api_base: Optional[str] = Field(default=None, env="PHASE3_API_BASE")
    
    # Translator
    translator_provider: str = Field(default="ollama", env="TRANSLATOR_PROVIDER")
    translator_model: str = Field(default="gemma3:27b", env="TRANSLATOR_MODEL_NEW")
    translator_temperature: float = Field(default=0.1, env="TRANSLATOR_TEMPERATURE")
    translator_api_key: Optional[str] = Field(default=None, env="TRANSLATOR_API_KEY")
    translator_api_base: Optional[str] = Field(default=None, env="TRANSLATOR_API_BASE")
    
    # Summarizer (for data ingestion)
    summarizer_provider: str = Field(default="ollama", env="SUMMARIZER_PROVIDER")
    summarizer_model: str = Field(default="gpt-oss:20b", env="SUMMARIZER_MODEL")
    summarizer_temperature: float = Field(default=0.1, env="SUMMARIZER_TEMPERATURE")
    summarizer_api_key: Optional[str] = Field(default=None, env="SUMMARIZER_API_KEY")
    summarizer_api_base: Optional[str] = Field(default=None, env="SUMMARIZER_API_BASE")
    
    # Translation Configuration
    translator_model: str = Field(default="gemma3:27b", env="TRANSLATOR_MODEL")
    dictionary_path: str = Field(default="translator_tools/Dictionary.md", env="DICTIONARY_PATH")
    segmentation_chunk_size: int = Field(default=500, env="SEGMENTATION_CHUNK_SIZE")
    term_context_window: int = Field(default=3, env="TERM_CONTEXT_WINDOW")  # sentences before/after
    
    # Document Paths (Unified - same directory for all documents)
    docs_dir: str = Field(default="/storage03/Saboori/ActionPlan/HELD/docs", env="DOCS_DIR")
    
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
    
    # Advanced RAG Settings (v3.1)
    rag_use_rrf: bool = Field(default=True, env="RAG_USE_RRF")  # Use Reciprocal Rank Fusion
    rag_use_mmr: bool = Field(default=True, env="RAG_USE_MMR")  # Use Maximal Marginal Relevance
    rag_mmr_lambda: float = Field(default=0.7, env="RAG_MMR_LAMBDA")  # Balance relevance (1.0) vs diversity (0.0)
    rag_graph_expansion_depth: int = Field(default=1, env="RAG_GRAPH_EXPANSION_DEPTH")  # Relationship hops
    rag_graph_expansion_boost: float = Field(default=0.3, env="RAG_GRAPH_EXPANSION_BOOST")  # Score boost from related nodes
    rag_context_window: bool = Field(default=True, env="RAG_CONTEXT_WINDOW")  # Include parent/child context
    
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
    
    # Analyzer Phase 2 Batch Processing
    analyzer_phase2_batch_threshold: int = Field(default=50, env="ANALYZER_PHASE2_BATCH_THRESHOLD")
    analyzer_phase2_batch_size: int = Field(default=20, env="ANALYZER_PHASE2_BATCH_SIZE")
    
    # Orchestrator prompt template directory
    prompt_template_dir: str = Field(default="templates/prompt_extensions/Orchestrator", env="PROMPT_TEMPLATE_DIR")
    
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

