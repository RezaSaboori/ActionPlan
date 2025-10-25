"""State definitions for LangGraph workflow."""

from typing import TypedDict, List, Dict, Any, Optional


class ActionPlanState(TypedDict, total=False):
    """State for the action plan development workflow."""
    
    # Input (user configuration)
    subject: str  # User's action plan subject (DEPRECATED: now in user_config)
    user_config: Dict[str, str]  # NEW: User configuration (name, timing, level, phase, subject)
    
    # User-configurable parameters (legacy/optional)
    documents_to_query: Optional[List[str]]  # User-selected documents (default: all non-dictionary docs)
    guideline_documents: List[str]  # Always-included guideline docs
    timing: Optional[str]  # Timing context (e.g., "yearly", "seasonal", "monthly")
    trigger: Optional[str]  # Action plan activation trigger
    responsible_party: Optional[str]  # Responsible party
    process_owner: Optional[str]  # Process owner
    
    # NEW: Orchestrator outputs (template-based)
    problem_statement: str  # Focused problem statement from Orchestrator
    rules_context: Dict[str, Any]  # DEPRECATED: Context from rules documents (no longer used)
    plan_structure: Dict[str, Any]  # DEPRECATED: Initial plan structure (no longer used)
    topics: List[str]  # DEPRECATED: Topics identified by Orchestrator (no longer used)
    
    # NEW: Analyzer Phase 1 outputs
    all_document_summaries: List[Dict[str, Any]]  # All document summaries for global context
    refined_queries: List[str]  # Refined Graph RAG queries from Phase 1
    
    # NEW: Analyzer Phase 2 outputs
    node_ids: List[str]  # Relevant node IDs extracted in Phase 2
    
    # DEPRECATED: Old Analyzer outputs
    context_map: Dict[str, Any]  # DEPRECATED: Document structure from old Analyzer Phase 1
    identified_subjects: List[str]  # DEPRECATED: Specific subjects from old Analyzer Phase 2
    
    # Phase3 outputs (NEW: graph traversal-based)
    phase3_nodes: List[Dict[str, Any]]  # Nodes with complete metadata (id, title, start_line, end_line, source) from Phase3
    subject_nodes: List[Dict[str, Any]]  # BACKWARD COMPATIBILITY: Wrapped phase3_nodes for Extractor
    
    # LEGACY: Analyzer outputs (for backward compatibility)
    extracted_actions: List[Dict[str, Any]]  # Raw actions from protocols
    
    # NEW: Enhanced Extractor outputs
    subject_actions: List[Dict[str, Any]]  # [{subject: str, actions: List[Dict]}]
    complete_actions: List[Dict[str, Any]]  # Actions with who/when defined
    flagged_actions: List[Dict[str, Any]]  # Actions missing who/when
    
    # De-duplicator outputs
    merge_summary: Dict[str, Any]  # Statistics about action merging
    
    # Selector outputs
    selection_summary: Dict[str, Any]  # Statistics about action filtering
    discarded_actions: List[Dict[str, Any]]  # Actions filtered out by selector with reasons
    
    # Extractor outputs (legacy/consolidated)
    refined_actions: List[Dict[str, Any]]  # Deduplicated actions (post de-duplicator, post selector)
    
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

