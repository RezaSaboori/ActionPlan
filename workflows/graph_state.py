"""State definitions for LangGraph workflow."""

from typing import TypedDict, List, Dict, Any, Optional


class ActionPlanState(TypedDict, total=False):
    """State for the action plan development workflow."""
    
    # Input
    subject: str  # User's action plan subject
    
    # NEW: User-configurable parameters
    documents_to_query: Optional[List[str]]  # User-selected documents (default: all non-dictionary docs)
    guideline_documents: List[str]  # Always-included guideline docs
    timing: Optional[str]  # Timing context (e.g., "yearly", "seasonal", "monthly")
    trigger: Optional[str]  # Action plan activation trigger
    responsible_party: Optional[str]  # Responsible party
    process_owner: Optional[str]  # Process owner
    
    # Orchestrator outputs
    rules_context: Dict[str, Any]  # Context from rules documents
    plan_structure: Dict[str, Any]  # Initial plan structure
    topics: List[str]  # Topics identified by Orchestrator
    
    # NEW: Analyzer outputs (2-phase workflow)
    context_map: Dict[str, Any]  # Document structure from Analyzer Phase 1
    identified_subjects: List[str]  # Specific subjects from Analyzer Phase 2
    
    # NEW: phase3 outputs
    subject_nodes: List[Dict[str, Any]]  # [{subject: str, nodes: List[Dict]}]
    
    # LEGACY: Analyzer outputs (for backward compatibility)
    extracted_actions: List[Dict[str, Any]]  # Raw actions from protocols
    
    # NEW: Enhanced Extractor outputs
    subject_actions: List[Dict[str, Any]]  # [{subject: str, actions: List[Dict]}]
    
    # Extractor outputs (legacy/consolidated)
    refined_actions: List[Dict[str, Any]]  # Deduplicated actions
    
    # Prioritizer outputs
    prioritized_actions: List[Dict[str, Any]]  # Actions with priority/timeline
    
    # Assigner outputs
    assigned_actions: List[Dict[str, Any]]  # Actions with roles assigned
    
    # Quality Checker outputs
    quality_feedback: Dict[str, Any]  # Feedback on current stage
    
    # Comprehensive Quality Validator outputs
    orchestrator_context: Dict[str, Any]  # Full context from orchestrator
    original_input: Dict[str, Any]  # User's original request parameters
    validator_retry_count: int  # Track validator-initiated retries
    validation_report: Dict[str, Any]  # Detailed validation results
    quality_repairs: List[str]  # List of self-repairs made
    
    # Formatter outputs
    final_plan: str  # Formatted markdown plan
    
    # Translation workflow outputs
    translated_plan: str  # Initial Persian translation from Translator Agent
    segmented_chunks: List[Dict[str, Any]]  # Chunks with text and metadata
    identified_terms: List[Dict[str, Any]]  # Terms with context windows and positions
    dictionary_corrections: List[Dict[str, Any]]  # Corrections from dictionary lookup
    final_persian_plan: str  # Final corrected Persian translation
    
    # Workflow control
    current_stage: str  # Current workflow stage
    retry_count: Dict[str, int]  # Retry count per stage
    errors: List[str]  # Error messages
    metadata: Dict[str, Any]  # Additional metadata

