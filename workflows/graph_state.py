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
    
    # NEW: Special Protocols feature
    special_protocols_node_ids: Optional[List[str]]  # User-selected node IDs for special protocols
    special_protocols_nodes: List[Dict[str, Any]]  # Formatted node data for special protocols
    
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
    
    # NEW: Enhanced Extractor outputs (with table extraction)
    formatted_output: str  # Human-readable formatted output with WHO-based grouping
    actions_by_actor: Dict[str, List[Dict[str, Any]]]  # Actions grouped by responsible actor (WHO)
    tables: List[Dict[str, Any]]  # Extracted tables/checklists with references
    extraction_metadata: Dict[str, Any]  # Extraction statistics (counts, flags, etc.)
    # DEPRECATED: formulas - now integrated directly into actions via original_formula_reference field
    
    # Legacy Extractor outputs (for backward compatibility)
    subject_actions: List[Dict[str, Any]]  # [{subject: str, actions, formulas, tables}]
    complete_actions: List[Dict[str, Any]]  # Actions with valid who/when
    flagged_actions: List[Dict[str, Any]]  # Actions missing/generic who/when
    
    # De-duplicator outputs
    merge_summary: Dict[str, Any]  # Statistics about action merging
    refined_actions: List[Dict[str, Any]]  # Combined complete + flagged actions after deduplication/selection
    
    # Selector outputs
    selection_summary: Dict[str, Any]  # Statistics about action filtering
    discarded_actions: List[Dict[str, Any]]  # Actions filtered out by selector with reasons
    
    # Timing outputs
    timed_actions: List[Dict[str, Any]]  # Actions with priority/timeline
    
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
    agent_output_dir: Optional[str] # Directory to save agent outputs for debugging

