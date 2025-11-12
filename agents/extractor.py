"""Extractor Agent for multi-subject action extraction with who/when/what format.

Enhanced with:
- Maximum granularity action extraction (atomic, quantitative actions only)
- Formula extraction with computation examples
- Table and checklist extraction
- Comprehensive reference tracking
- WHO-based output formatting
"""

import logging
import json
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from utils.llm_client import LLMClient
from rag_tools.graph_rag import GraphRAG
from utils.document_parser import DocumentParser
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURE SCHEMAS
# ============================================================================

def create_reference(document: str, line_range: str, node_id: str, node_title: str) -> Dict[str, str]:
    """
    Create a reference object for tracing extracted items back to source.
    
    Args:
        document: Full document path/name
        line_range: Line range as string (e.g., "45-52")
        node_id: Source node identifier
        node_title: Human-readable node title
        
    Returns:
        Reference dictionary
    """
    return {
        "document": document,
        "line_range": line_range,
        "node_id": node_id,
        "node_title": node_title
    }


def create_action_schema(
    action: str,
    who: str,
    when: str,
    reference: Dict[str, str],
    timing_flagged: bool = False,
    actor_flagged: bool = False,
    flag_reason: str = "",
    original_formula_reference: Optional[Dict[str, Any]] = None,
    action_id: str = None
) -> Dict[str, Any]:
    """
    Create an action object with enhanced schema.
    
    Args:
        action: Comprehensive action description including all details, outcomes, resources, and procedures
        who: Responsible role/unit (for validation purposes)
        when: Timeline or trigger (for validation purposes)
        reference: Source reference object
        timing_flagged: True if WHO valid but WHEN generic/missing
        actor_flagged: True if WHO generic/missing
        flag_reason: Explanation of what needs clarification (for flagged actions)
        original_formula_reference: Reference to original formula if this action includes a merged formula
        action_id: Unique identifier (generated if not provided)
        
    Returns:
        Action dictionary (note: 'what' field has been removed, all details are in 'action' field)
    """
    return {
        "id": action_id or str(uuid.uuid4()),
        "action": action,
        "who": who,
        "when": when,
        "reference": reference,
        "timing_flagged": timing_flagged,
        "actor_flagged": actor_flagged,
        "flag_reason": flag_reason,
        "original_formula_reference": original_formula_reference,
        # Legacy fields for backward compatibility
        "source_node": reference["node_id"],
        "source_lines": reference["line_range"]
    }


def create_formula_schema(
    formula: str,
    computation_example: str,
    sample_result: str,
    formula_context: str,
    reference: Dict[str, str],
    related_actions: List[str] = None,
    merged_into_actions: bool = False,
    formula_id: str = None
) -> Dict[str, Any]:
    """
    Create a formula object schema.
    
    Args:
        formula: Raw formula/equation as written
        computation_example: Worked example showing application
        sample_result: Calculated output from example
        formula_context: What the formula calculates and when to use it
        reference: Source reference object
        related_actions: List of action IDs if applicable
        merged_into_actions: True if formula was merged into action(s)
        formula_id: Unique identifier (generated if not provided)
        
    Returns:
        Formula dictionary
    """
    return {
        "id": formula_id or str(uuid.uuid4()),
        "formula": formula,
        "computation_example": computation_example,
        "sample_result": sample_result,
        "formula_context": formula_context,
        "reference": reference,
        "related_actions": related_actions or [],
        "merged_into_actions": merged_into_actions
    }


def create_table_schema(
    table_title: str,
    table_type: str,
    headers: List[str],
    rows: List[List[str]],
    markdown_content: str,
    reference: Dict[str, str],
    extracted_actions: List[str] = None,
    table_id: str = None
) -> Dict[str, Any]:
    """
    Create a table/checklist object schema.
    
    Args:
        table_title: Descriptive title from context
        table_type: One of "checklist", "action_table", "decision_matrix", "other"
        headers: Column headers if present
        rows: All row data preserved
        markdown_content: Original markdown representation
        reference: Source reference object
        extracted_actions: List of action IDs if actions extracted from table
        table_id: Unique identifier (generated if not provided)
        
    Returns:
        Table dictionary
    """
    return {
        "id": table_id or str(uuid.uuid4()),
        "table_title": table_title,
        "table_type": table_type,
        "headers": headers,
        "rows": rows,
        "markdown_content": markdown_content,
        "reference": reference,
        "extracted_actions": extracted_actions or []
    }


class ExtractorAgent:
    """
    Enhanced Extractor agent for multi-subject processing.
    
    Workflow:
    - Process each subject separately
    - Read full node content from original files
    - Extract actions in structured format (who, when, what)
    - Can consult Quality Agent for validation
    - Maintains subject grouping
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        graph_rag: Optional[GraphRAG] = None,
        quality_agent=None,
        orchestrator_agent=None,
        markdown_logger=None
    ):
        """
        Initialize Enhanced Extractor Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            graph_rag: Graph RAG for content retrieval (optional)
            quality_agent: Quality checker agent for validation (optional)
            orchestrator_agent: Orchestrator for clarifications (optional)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.graph_rag = graph_rag
        self.quality_agent = quality_agent
        self.orchestrator_agent = orchestrator_agent
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("extractor_multi_subject")
        logger.info(f"Initialized ExtractorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multi-subject extraction logic with maximum granularity.
        
        Extracts atomic, quantitative actions along with formulas and tables.
        Provides both structured programmatic access and human-readable formatted output.
        
        Args:
            data: Dictionary containing:
                - subject_nodes: List of {subject: str, nodes: List[Dict]}
                
        Returns:
            Dictionary with:
                **New Format:**
                - formatted_output: Human-readable text with WHO-based grouping
                - actions_by_actor: Dict mapping WHO to List[actions]
                - formulas: List of formula objects with references
                - tables: List of table objects with references
                - metadata: Extraction statistics
                
                **Legacy Format (for compatibility):**
                - complete_actions: List of actions with valid who/when
                - flagged_actions: List of actions missing/generic who/when
                - subject_actions: List of {subject: str, actions, formulas, tables}
        """
        subject_nodes = data.get("subject_nodes", [])
        
        if not subject_nodes:
            logger.warning("No subject nodes provided for extraction")
            return {
                "complete_actions": [],
                "flagged_actions": [],
                "subject_actions": []
            }
        
        logger.info(f"=" * 80)
        logger.info(f"🚀 EXTRACTOR AGENT STARTING: Processing {len(subject_nodes)} subjects")
        logger.info(f"=" * 80)
        
        if self.markdown_logger:
            self.markdown_logger.add_text("## 🚀 Extractor Agent Processing Start")
            self.markdown_logger.add_text(f"Total subjects to process: {len(subject_nodes)}")
            self.markdown_logger.add_text("")
        
        # Debug: log structure of first subject_node
        if subject_nodes:
            sample = subject_nodes[0]
            logger.info(f"📋 Sample subject_node structure:")
            logger.info(f"   Keys: {list(sample.keys())}")
            logger.info(f"   Subject: {sample.get('subject', 'MISSING')}")
            logger.info(f"   Nodes count: {len(sample.get('nodes', []))}")
            if sample.get('nodes'):
                first_node = sample['nodes'][0]
                logger.info(f"   First node keys: {list(first_node.keys())}")
                logger.info(f"   First node ID: {first_node.get('id', 'MISSING')}")
        
        all_complete_actions = []
        all_flagged_actions = []
        all_tables = []
        subject_data_list = []
        
        for idx, subject_node_data in enumerate(subject_nodes, 1):
            subject = subject_node_data.get("subject", "Unknown")
            nodes = subject_node_data.get("nodes", [])
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SUBJECT {idx}/{len(subject_nodes)}: '{subject}'")
            logger.info(f"Nodes to process: {len(nodes)}")
            logger.info(f"{'='*80}")
            
            # Log node details for debugging
            if nodes:
                logger.debug(f"Node IDs for subject '{subject}':")
                for node in nodes:
                    logger.debug(f"  - {node.get('id', 'Unknown')} ({node.get('title', 'Unknown')})")
            
            # Extract actions and tables for this subject (formulas now integrated into actions)
            complete, flagged, tables = self._process_subject(subject, nodes)
            
            # Aggregate across all subjects
            all_complete_actions.extend(complete)
            all_flagged_actions.extend(flagged)
            all_tables.extend(tables)
            
            # Store subject-specific data
            subject_data_list.append({
                "subject": subject,
                "complete_actions": complete,
                "flagged_actions": flagged,
                "tables": tables,
                "actions": complete + flagged  # Combined for backward compatibility
            })
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SUBJECT '{subject}' COMPLETED: {len(complete)} complete, {len(flagged)} flagged actions, "
                       f"{len(tables)} tables")
            logger.info(f"{'='*80}\n")
        
        # Combine all actions
        all_actions = all_complete_actions + all_flagged_actions
        
        # Group actions by WHO (responsible actor)
        actions_by_actor = {}
        for action in all_actions:
            who = action.get('who', 'Unknown')
            if who not in actions_by_actor:
                actions_by_actor[who] = []
            actions_by_actor[who].append(action)
        
        # Generate formatted output
        formatted_output = self._generate_formatted_output(
            all_actions, 
            all_tables,
            subject_name="All Subjects" if len(subject_nodes) > 1 else subject_nodes[0].get("subject", "Unknown")
        )
        
        # Calculate metadata
        metadata = {
            "total_subjects": len(subject_nodes),
            "total_nodes_processed": sum(len(s.get("nodes", [])) for s in subject_nodes),
            "total_actions": len(all_actions),
            "complete_actions": len(all_complete_actions),
            "flagged_actions": len(all_flagged_actions),
            "timing_flagged": sum(1 for a in all_actions if a.get('timing_flagged', False)),
            "actor_flagged": sum(1 for a in all_actions if a.get('actor_flagged', False)),
            "actions_with_formulas": sum(1 for a in all_actions if a.get('original_formula_reference')),
            "total_tables": len(all_tables),
            "unique_actors": len(actions_by_actor)
        }
        
        logger.info(f"=" * 80)
        logger.info(f"EXTRACTOR AGENT COMPLETED")
        logger.info(f"Total actions: {metadata['total_actions']} ({metadata['complete_actions']} complete, {metadata['flagged_actions']} flagged)")
        logger.info(f"Actions with integrated formulas: {metadata['actions_with_formulas']}")
        logger.info(f"Total tables: {metadata['total_tables']}")
        logger.info(f"Unique actors (WHO): {metadata['unique_actors']}")
        logger.info(f"=" * 80)
        
        return {
            # New format
            "formatted_output": formatted_output,
            "actions_by_actor": actions_by_actor,
            "tables": all_tables,
            "metadata": metadata,
            
            # Legacy format for backward compatibility during transition
            "complete_actions": all_complete_actions,
            "flagged_actions": all_flagged_actions,
            "subject_actions": subject_data_list
        }
    
    def _process_subject(
        self, 
        subject: str, 
        nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process all nodes for a single subject.
        
        Extracts actions and tables from each node and aggregates them.
        Note: Formulas are now integrated directly into actions.
        
        Args:
            subject: Subject name
            nodes: List of nodes with metadata
            
        Returns:
            Tuple of (complete_actions, flagged_actions, tables)
        """
        if not nodes:
            logger.warning(f"No nodes provided for subject: {subject}")
            return [], [], []
        
        logger.info(f"Processing {len(nodes)} nodes for subject '{subject}'")
        
        complete_actions = []
        flagged_actions = []
        all_tables = []
        
        logger.info(f"🔄 Starting node-by-node extraction for subject '{subject}'")
        if self.markdown_logger:
            self.markdown_logger.add_text(f"### Subject: {subject}")
            self.markdown_logger.add_text(f"Processing {len(nodes)} nodes sequentially...\n")
        
        for idx, node in enumerate(nodes, 1):
            node_id = node.get('id', 'Unknown')
            node_title = node.get('title', 'Unknown')
            logger.info(f"📄 Processing node {idx}/{len(nodes)}: {node_id} ({node_title})")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"---")
                self.markdown_logger.add_text(f"#### Node {idx}/{len(nodes)}: {node_title}")
                self.markdown_logger.add_list_item(f"Node ID: {node_id}", level=0)
                self.markdown_logger.add_text("")
            
            node_complete, node_flagged, node_tables = self._extract_from_node(subject, node)
            
            # Add to temp lists
            complete_actions.extend(node_complete)
            flagged_actions.extend(node_flagged)
            all_tables.extend(node_tables)
            
            # Count actions with integrated formulas
            actions_with_formulas = sum(1 for a in (node_complete + node_flagged) if a.get('original_formula_reference'))
            
            # Log accumulation after each node
            logger.info(f"  → This node: {len(node_complete)} complete, {len(node_flagged)} flagged actions "
                       f"({actions_with_formulas} with formulas), {len(node_tables)} tables")
            logger.info(f"  ✅ Running totals: {len(complete_actions)} complete, {len(flagged_actions)} flagged, "
                       f"{len(all_tables)} tables")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"**Node Extraction Summary:**")
                self.markdown_logger.add_list_item(f"Complete actions from this node: {len(node_complete)}", level=0)
                self.markdown_logger.add_list_item(f"Flagged actions from this node: {len(node_flagged)}", level=0)
                self.markdown_logger.add_list_item(f"Actions with integrated formulas: {actions_with_formulas}", level=0)
                self.markdown_logger.add_list_item(f"Tables from this node: {len(node_tables)}", level=0)
                self.markdown_logger.add_text("")
                self.markdown_logger.add_text(f"**🎯 Running Totals After Node {idx}:**")
                self.markdown_logger.add_list_item(f"Total complete actions: {len(complete_actions)}", level=0)
                self.markdown_logger.add_list_item(f"Total flagged actions: {len(flagged_actions)}", level=0)
                self.markdown_logger.add_list_item(f"Total tables: {len(all_tables)}", level=0)
                self.markdown_logger.add_text("")
        
        logger.info(f"✅ Subject '{subject}' complete: {len(complete_actions)} complete, {len(flagged_actions)} flagged actions, "
                   f"{len(all_tables)} tables")
        
        return complete_actions, flagged_actions, all_tables
    
    def _extract_from_node(
        self, 
        subject: str, 
        node: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract actions and tables from a single node.
        
        Reads complete content using line numbers and extracts:
        - Actions at maximum granularity (atomic, quantitative)
        - Formulas are integrated directly into actions (not returned separately)
        - Tables and checklists with complete structure
        
        Automatically segments long content and processes with memory.
        Validates each action and separates into complete/flagged lists.
        Adds comprehensive reference information to all extracted items.
        
        Args:
            subject: Subject name
            node: Node metadata with id, start_line, end_line, source
            
        Returns:
            Tuple of (complete_actions, flagged_actions, tables)
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.info(f"🔍 STARTING EXTRACTION from node {node_id} ({node_title})")
        logger.info(f"   Subject: {subject}")
        logger.info(f"   Node metadata: id={node_id}, start_line={start_line}, end_line={end_line}")
        
        if self.markdown_logger:
            self.markdown_logger.add_text(f"##### 🔍 Starting Extraction from Node: {node_title}")
            self.markdown_logger.add_list_item(f"Node ID: {node_id}", level=0)
            self.markdown_logger.add_list_item(f"Lines: {start_line}-{end_line}", level=0)
            self.markdown_logger.add_list_item(f"Subject: {subject}", level=0)
            self.markdown_logger.add_text("")
        
        if not all([node_id, start_line is not None, end_line is not None]):
            error_msg = f"Missing required metadata for node: {node_id} - id:{node_id}, start_line:{start_line}, end_line:{end_line}"
            logger.warning(f"⚠️ {error_msg}")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"⚠️ **Error: Missing Metadata**")
                self.markdown_logger.add_text(error_msg)
                self.markdown_logger.add_text("")
            
            return [], [], [], []
        
        # Read complete content from original file
        logger.info(f"📖 Reading content for node {node_id}...")
        
        if self.markdown_logger:
            self.markdown_logger.add_text(f"**Step 1: Reading Node Content**")
            self.markdown_logger.add_text("")
        
        content = self._read_full_content(node)
        
        if not content:
            error_msg = f"No content retrieved for node {node_id} ({node_title})"
            logger.warning(f"⚠️ {error_msg}")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"⚠️ **Error: No Content Retrieved**")
                self.markdown_logger.add_text(error_msg)
                self.markdown_logger.add_text("This could mean:")
                self.markdown_logger.add_list_item("Source file not found", level=0)
                self.markdown_logger.add_list_item("Line numbers out of range", level=0)
                self.markdown_logger.add_list_item("Graph query failed", level=0)
                self.markdown_logger.add_text("")
            
            return [], [], [], []
        
        logger.info(f"✅ Content retrieved for node {node_id}, length: {len(content)} characters")
        
        if self.markdown_logger:
            self.markdown_logger.add_text(f"✅ **Content Retrieved Successfully**")
            self.markdown_logger.add_list_item(f"Content length: {len(content)} characters", level=0)
            self.markdown_logger.add_list_item(f"Content preview: {content[:200]}...", level=0)
            self.markdown_logger.add_text("")
        
        # Initialize extraction metadata
        extraction_metadata = {
            "node_id": node_id,
            "markdown_recovery_applied": False,
            "formulas_merged": 0,
            "tables_with_inferred_titles": 0,
            "schema_validation_errors": 0,
            "errors": []
        }
        
        # Step 2: Apply markdown recovery if needed
        logger.info(f"🔧 Checking for markdown corruption in node {node_id}...")
        recovered_content, was_recovered, recovery_notes = self._recover_corrupted_markdown(
            content, 
            context=f"Node: {node_title}\nSubject: {subject}"
        )
        
        if was_recovered:
            extraction_metadata["markdown_recovery_applied"] = True
            extraction_metadata["recovery_notes"] = recovery_notes
            content = recovered_content
            logger.info(f"✅ Markdown recovery applied: {recovery_notes}")
        
        # Estimate tokens (rough: chars / 4)
        estimated_tokens = len(content) / 4
        
        # Step 3: Extract actions, formulas, and tables
        if estimated_tokens > 2000:
            # Segment and process with memory
            logger.info(f"Node {node_id} is large ({estimated_tokens:.0f} tokens), segmenting...")
            segments = self._segment_content(content, max_tokens=2000)
            logger.info(f"Split into {len(segments)} segments")
            extraction_result = self._extract_from_segments(subject, node, segments)
        else:
            # Process as single unit
            logger.debug(f"Node {node_id} fits in single segment ({estimated_tokens:.0f} tokens)")
            extraction_result = self._llm_extract_actions(subject, node, content)
        
        # Extract components from result
        raw_actions = extraction_result.get("actions", [])
        raw_formulas = extraction_result.get("formulas", [])
        raw_tables = extraction_result.get("tables", [])
        
        logger.info(f"📊 Raw extraction from node {node_id}: {len(raw_actions)} actions, {len(raw_formulas)} formulas, {len(raw_tables)} tables")
        
        # Step 4: Enhance formulas with references (for integration into actions)
        formulas = self._enhance_formulas_with_references(raw_formulas, node)
        
        # Step 5: Integrate formulas into actions
        logger.info(f"🔗 Integrating {len(formulas)} formulas into actions for node {node_id}...")
        raw_actions, formulas_merged = self._integrate_formulas_into_actions(raw_actions, formulas)
        extraction_metadata["formulas_merged"] = formulas_merged
        
        # Step 6: Enhance tables with references and title inference
        tables = self._enhance_tables_with_references(raw_tables, node, content, node_title)
        
        # Count tables with inferred titles
        extraction_metadata["tables_with_inferred_titles"] = sum(
            1 for t in tables 
            if t.get('title_inferred', False)
        )
        
        # Create reference for actions
        document = node.get('source', node.get('document', 'Unknown'))
        reference = create_reference(
            document=document,
            line_range=f"{start_line}-{end_line}",
            node_id=node_id,
            node_title=node_title
        )
        
        # Add references to actions
        for action in raw_actions:
            if 'reference' not in action:
                action['reference'] = reference
        
        # Step 7: Validate and separate actions into complete/flagged
        complete_actions, flagged_actions = self._validate_and_separate_actions(raw_actions, node_id, node_title)
        
        # Step 8: Validate schema compliance (formulas are now part of actions, not separate)
        logger.info(f"✅ Validating schema compliance for node {node_id}...")
        validation_result = self._validate_schema_compliance(
            complete_actions + flagged_actions,
            tables
        )
        extraction_metadata["schema_validation_errors"] = len(validation_result.get('errors', []))
        extraction_metadata["schema_validation_warnings"] = len(validation_result.get('warnings', []))
        if not validation_result['valid']:
            extraction_metadata["errors"].extend(validation_result['errors'])
        
        # Step 9: Log detailed results to markdown
        self._log_node_extraction_details(node_id, node_title, start_line, end_line, 
                                          complete_actions, flagged_actions)
        
        # Log extraction metadata
        if self.markdown_logger:
            self.markdown_logger.add_text("### Extraction Metadata")
            self.markdown_logger.add_list_item(f"Markdown recovery: {'Yes' if extraction_metadata['markdown_recovery_applied'] else 'No'}", level=0)
            if extraction_metadata['markdown_recovery_applied']:
                self.markdown_logger.add_list_item(f"Recovery notes: {extraction_metadata.get('recovery_notes', 'N/A')}", level=1)
            self.markdown_logger.add_list_item(f"Formulas merged into actions: {extraction_metadata['formulas_merged']}", level=0)
            self.markdown_logger.add_list_item(f"Tables with inferred titles: {extraction_metadata['tables_with_inferred_titles']}", level=0)
            self.markdown_logger.add_list_item(f"Schema validation errors: {extraction_metadata['schema_validation_errors']}", level=0)
            self.markdown_logger.add_list_item(f"Schema validation warnings: {extraction_metadata['schema_validation_warnings']}", level=0)
            self.markdown_logger.add_text("")
        
        logger.info(f"✅ Extraction complete for node {node_id}: {len(complete_actions)} complete actions, "
                   f"{len(flagged_actions)} flagged actions, {len(tables)} tables")
        logger.info(f"   {extraction_metadata['formulas_merged']} formulas integrated into actions")
        logger.info(f"   Metadata: {extraction_metadata}")
        
        return complete_actions, flagged_actions, tables
    
    def _validate_and_separate_actions(
        self, 
        actions: List[Dict[str, Any]], 
        node_id: str, 
        node_title: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate actions and separate into complete and flagged lists.
        
        Enhanced validation with separate flags for timing vs actor issues:
        - timing_flagged: WHO is valid but WHEN is generic/missing
        - actor_flagged: WHO is generic/missing (regardless of WHEN)
        
        Complete actions: both WHO and WHEN are valid and non-generic
        Flagged actions: missing or generic WHO, or missing/generic WHEN
        
        Args:
            actions: Raw extracted actions
            node_id: Node identifier
            node_title: Node title
            
        Returns:
            Tuple of (complete_actions, flagged_actions)
        """
        logger.info(f"🔍 Validating {len(actions)} actions from node {node_id}")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                f"Action Validation for Node: {node_title}",
                {
                    "node_id": node_id,
                    "total_actions_to_validate": len(actions)
                }
            )
        
        complete_actions = []
        flagged_actions = []
        
        generic_who_terms = {'staff', 'team', 'personnel', 'people', 'someone', 'n/a', 'unknown', ''}
        generic_when_terms = {'soon', 'later', 'eventually', 'n/a', 'unknown', ''}
        
        for idx, action in enumerate(actions, 1):
            who = action.get('who', '').strip().lower()
            when = action.get('when', '').strip().lower()
            action_text = action.get('action', 'N/A')
            
            missing_fields = []
            flag_reasons = []
            
            # Validate WHO field
            who_is_valid = who and who not in generic_who_terms and len(who) > 2
            if not who_is_valid:
                missing_fields.append('who')
                if not who or who in generic_who_terms:
                    flag_reasons.append('Missing or generic responsible role/unit')
                else:
                    flag_reasons.append('Responsible role is too vague')
            
            # Validate WHEN field
            when_is_valid = when and when not in generic_when_terms and len(when) > 2
            if not when_is_valid:
                missing_fields.append('when')
                if not when or when in generic_when_terms:
                    flag_reasons.append('Missing or generic timeline/trigger')
                else:
                    flag_reasons.append('Timeline is too vague')
            
            # Set flag types
            action['timing_flagged'] = who_is_valid and not when_is_valid
            action['actor_flagged'] = not who_is_valid
            
            # Categorize action
            if who_is_valid and when_is_valid:
                # Complete action - both WHO and WHEN are valid
                action['timing_flagged'] = False
                action['actor_flagged'] = False
                complete_actions.append(action)
                logger.info(f"✅ Action {idx}: COMPLETE - {action_text[:80]}")
                
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"✅ **Action {idx}: COMPLETE**")
                    self.markdown_logger.add_list_item(f"Action: {action_text}", level=1)
                    self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}'", level=1)
                    self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}'", level=1)
                    self.markdown_logger.add_text("")
            else:
                # Flagged action - set legacy fields and new flag fields
                action['missing_fields'] = missing_fields
                action['flag_reason'] = '; '.join(flag_reasons)
                action['flagged'] = True
                flagged_actions.append(action)
                
                # Log with specific flag type
                flag_type = "actor unclear" if action['actor_flagged'] else "timing unclear"
                logger.warning(f"⚠️ Action {idx}: FLAGGED ({flag_type}) - {action_text[:80]}")
                
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"⚠️ **Action {idx}: FLAGGED ({flag_type.upper()})**")
                    self.markdown_logger.add_list_item(f"Action: {action_text}", level=1)
                    self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}' (valid: {who_is_valid})", level=1)
                    self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}' (valid: {when_is_valid})", level=1)
                    self.markdown_logger.add_list_item(f"Actor flagged: {action['actor_flagged']}", level=1)
                    self.markdown_logger.add_list_item(f"Timing flagged: {action['timing_flagged']}", level=1)
                    self.markdown_logger.add_list_item(f"Reason: {action['flag_reason']}", level=1)
                    self.markdown_logger.add_text("")
        
        logger.info(f"📊 Validation results for node {node_id}: {len(complete_actions)} complete, {len(flagged_actions)} flagged")
        
        # Count flag types
        timing_flagged_count = sum(1 for a in flagged_actions if a.get('timing_flagged'))
        actor_flagged_count = sum(1 for a in flagged_actions if a.get('actor_flagged'))
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                f"Validation Summary for {node_title}",
                {
                    "complete_actions": len(complete_actions),
                    "flagged_actions": len(flagged_actions),
                    "timing_flagged": timing_flagged_count,
                    "actor_flagged": actor_flagged_count,
                    "total_validated": len(actions)
                }
            )
        
        return complete_actions, flagged_actions
    
    def _log_node_extraction_details(
        self,
        node_id: str,
        node_title: str,
        start_line: int,
        end_line: int,
        complete_actions: List[Dict[str, Any]],
        flagged_actions: List[Dict[str, Any]]
    ):
        """
        Log detailed extraction results for a node to markdown logger.
        
        Args:
            node_id: Node identifier
            node_title: Node title
            start_line: Start line number
            end_line: End line number
            complete_actions: List of complete actions
            flagged_actions: List of flagged actions
        """
        if not self.markdown_logger:
            return
        
        # Log node header
        self.markdown_logger.log_processing_step(
            f"Node Extraction: {node_title}",
            {
                "node_id": node_id,
                "lines": f"{start_line}-{end_line}",
                "complete_actions": len(complete_actions),
                "flagged_actions": len(flagged_actions)
            }
        )
        
        # Log complete actions
        if complete_actions:
            self.markdown_logger.add_text("**Complete Actions:**", bold=True)
            for idx, action in enumerate(complete_actions, 1):
                self.markdown_logger.add_text(f"\n{idx}. **{action.get('action', 'N/A')}**")
                self.markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                context = action.get('context', '')
                if context:
                    self.markdown_logger.add_list_item(f"Context: {context[:150]}...", level=1)
            self.markdown_logger.add_text("")
        
        # Log flagged actions
        if flagged_actions:
            self.markdown_logger.add_text("**Flagged Actions (Incomplete):**", bold=True)
            for idx, action in enumerate(flagged_actions, 1):
                self.markdown_logger.add_text(f"\n{idx}. **{action.get('action', 'N/A')}**")
                self.markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"⚠️ MISSING: {', '.join(action.get('missing_fields', []))}", level=1)
                self.markdown_logger.add_list_item(f"Reason: {action.get('flag_reason', 'N/A')}", level=1)
            self.markdown_logger.add_text("")
    
    def _read_full_content(self, node: Dict[str, Any]) -> str:
        """
        Read complete content for a node directly from document file.
        
        Extracts document name from node_id, queries Neo4j for source path,
        then reads content directly using line numbers.
        
        Args:
            node: Node with metadata (id, start_line, end_line)
            
        Returns:
            Full content text
        """
        node_id = node.get('id')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.info(f"📖 _read_full_content called for node {node_id}")
        logger.info(f"   start_line: {start_line}, end_line: {end_line}")
        
        # Validate required metadata
        if not node_id:
            error_msg = "Node missing 'id' field"
            logger.warning(f"⚠️ {error_msg}")
            if self.markdown_logger:
                self.markdown_logger.add_text(f"⚠️ {error_msg}")
            return ""
        
        if start_line is None or end_line is None:
            error_msg = f"Node {node_id} missing line range information (start_line={start_line}, end_line={end_line})"
            logger.warning(f"⚠️ {error_msg}")
            if self.markdown_logger:
                self.markdown_logger.add_text(f"⚠️ {error_msg}")
            return ""
        
        # Try to get source path from node first
        source_path = node.get('source')
        logger.info(f"   source_path from node: {source_path}")
        
        # If not in node, query graph to get document source by traversing relationships
        if not source_path:
            logger.info(f"🔍 Source path not in node metadata for {node_id}, querying graph...")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"Querying graph for source path...")
            
            # Query graph to get document source by following relationships from node
            source_path = self._get_document_source_from_node(node_id)
            
            if not source_path:
                error_msg = f"Could not find source path for node: {node_id}"
                logger.error(f"❌ {error_msg}")
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"❌ {error_msg}")
                    self.markdown_logger.add_text("Possible reasons:")
                    self.markdown_logger.add_list_item("Node not in graph database", level=0)
                    self.markdown_logger.add_list_item("No parent document relationship", level=0)
                    self.markdown_logger.add_list_item("Graph RAG not initialized", level=0)
                return ""
            else:
                logger.info(f"✅ Found source path from graph: {source_path}")
        
        # Read content directly from file using line numbers
        try:
            logger.info(f"📄 Reading content from {source_path} lines {start_line}-{end_line}")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"Reading from file: {source_path}")
                self.markdown_logger.add_list_item(f"Lines: {start_line}-{end_line}", level=0)
            
            content = DocumentParser.get_content_by_lines(source_path, start_line, end_line)
            
            if content:
                logger.info(f"✅ Successfully read {len(content)} characters for node {node_id}")
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"✅ Content read: {len(content)} characters")
            else:
                logger.warning(f"⚠️ No content retrieved for node {node_id} (empty result)")
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"⚠️ Content is empty")
            
            return content
            
        except Exception as e:
            error_msg = f"Error reading content for node {node_id} from {source_path}: {e}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"Exception details:", exc_info=True)
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"❌ **Error Reading Content**")
                self.markdown_logger.add_text(f"File: {source_path}")
                self.markdown_logger.add_text(f"Error: {str(e)}")
            
            return ""
    
    def _get_document_source_from_node(self, node_id: str) -> str:
        """
        Query Neo4j to get document source path by traversing from node to its parent document.
        
        This approach doesn't rely on document name matching, instead it follows
        the graph relationships from the node up to its parent document.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Source file path or empty string if not found
        """
        if not self.graph_rag:
            logger.warning("No graph_rag available for document lookup")
            return ""
        
        try:
            # Query Neo4j by traversing relationships from node to document
            # This works regardless of document naming conventions
            query = """
            MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: $node_id})
            RETURN doc.source as source
            LIMIT 1
            """
            
            with self.graph_rag.driver.session() as session:
                result = session.run(query, node_id=node_id)
                record = result.single()
                
                if record and record['source']:
                    source_path = record['source']
                    logger.debug(f"Found source path for node '{node_id}': {source_path}")
                    return source_path
                else:
                    logger.warning(f"No document found for node '{node_id}'")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error querying graph for node '{node_id}': {e}")
            return ""
    
    def _llm_extract_actions(
        self,
        subject: str,
        node: Dict[str, Any],
        content: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Use LLM to extract actions, formulas, and tables from content.
        
        Enhanced to extract at maximum granularity:
        - Actions: Atomic, quantitative, independently executable
        - Formulas: All mathematical expressions with computation examples
        - Tables: All tables, checklists, and structured lists
        
        Args:
            subject: Subject name
            node: Node metadata
            content: Full content text
            
        Returns:
            Dictionary with keys: "actions", "formulas", "tables"
            Each value is a list of extracted items
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.debug(f"Extracting actions from node {node_id} ({node_title}) for subject '{subject}'")
        logger.debug(f"Content length: {len(content)} characters")
        
        prompt = f"""Extract ALL actionable items, formulas, and tables from this content related to the subject: {subject}

Source Node: {node_title} (ID: {node_id})
Lines: {start_line}-{end_line}

Content:
{content}

═══════════════════════════════════════════════════════════════════════════
EXTRACTION REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════

1. ACTIONS: Extract at MAXIMUM GRANULARITY
   - ONLY atomic, quantitative, independently executable actions
   - Break compound actions into individual atomic steps
   - REJECT qualitative descriptions, strategic goals, vague statements
   - Each action must have specific WHO, WHEN, and WHAT
   
2. FORMULAS: Extract ALL mathematical expressions
   - Include computation examples and sample results
   
3. TABLES: Identify ALL tables, checklists, structured lists
   - Classify type and preserve complete structure

═══════════════════════════════════════════════════════════════════════════
JSON OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════

{{
  "actions": [
    {{
      "action": "WHO does WHAT WHEN",
      "who": "Specific role/unit (NOT 'staff', 'team', 'personnel')",
      "when": "Precise timeline/trigger (NOT 'soon', 'later', 'as needed')",
      "what": "Detailed activity with specific values, methods, tools",
      "context": "Brief context explaining why/how"
    }}
  ],
  "formulas": [
    {{
      "formula": "Raw equation as written",
      "computation_example": "Worked example with specific values",
      "sample_result": "Calculated output",
      "formula_context": "What it calculates and when to use it"
    }}
  ],
  "tables": [
    {{
      "table_title": "Descriptive title",
      "table_type": "checklist|action_table|decision_matrix|other",
      "headers": ["column1", "column2"],
      "rows": [["data1", "data2"], ["data3", "data4"]],
      "markdown_content": "Original markdown table"
    }}
  ]
}}

═══════════════════════════════════════════════════════════════════════════
CRITICAL REMINDERS
═══════════════════════════════════════════════════════════════════════════

✅ EXTRACT atomic actions only (one independently executable step per action)
✅ EXTRACT quantitative actions with specific numbers, frequencies, methods
✅ EXTRACT ALL formulas with working computation examples
✅ EXTRACT ALL tables/checklists with complete structure
❌ REJECT qualitative descriptions ("ensure quality", "improve standards")
❌ REJECT compound actions (break them into atomic steps)
❌ REJECT vague statements without specific actionable steps

Extract EVERYTHING relevant from the content. Better 50 precise atomic actions than 10 vague ones.
Respond with valid JSON only."""
        
        try:
            logger.info(f"⚙️ Sending extraction request to LLM for node {node_id}")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    f"LLM Extraction Request for Node: {node_title}",
                    {
                        "node_id": node_id,
                        "lines": f"{start_line}-{end_line}",
                        "content_length": len(content),
                        "subject": subject
                    }
                )
            
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            # Log raw LLM response
            logger.info(f"✅ LLM response received for node {node_id}, type: {type(result)}")
            logger.debug(f"Raw LLM response: {json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    f"LLM Raw Response for {node_title}",
                    {
                        "response_type": str(type(result)),
                        "response_preview": str(result)[:500] if result else "Empty response"
                    }
                )
            
            # Handle new format with actions, formulas, and tables
            if isinstance(result, dict):
                actions = result.get("actions", [])
                formulas = result.get("formulas", [])
                tables = result.get("tables", [])
                
                logger.info(f"📋 Extracted from node {node_id}: {len(actions)} actions, {len(formulas)} formulas, {len(tables)} tables")
                
                # Add metadata to actions
                for action in actions:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                
                # Log extracted items
                if self.markdown_logger:
                    if actions:
                        self.markdown_logger.add_text(f"**Extracted {len(actions)} Actions:**")
                        for idx, action in enumerate(actions[:5], 1):
                            self.markdown_logger.add_text(f"{idx}. {action.get('action', 'N/A')}")
                            self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}'", level=1)
                            self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}'", level=1)
                        if len(actions) > 5:
                            self.markdown_logger.add_text(f"... and {len(actions) - 5} more actions")
                        self.markdown_logger.add_text("")
                    
                    if formulas:
                        self.markdown_logger.add_text(f"**Extracted {len(formulas)} Formulas:**")
                        for idx, formula in enumerate(formulas, 1):
                            self.markdown_logger.add_text(f"{idx}. {formula.get('formula', 'N/A')}")
                        self.markdown_logger.add_text("")
                    
                    if tables:
                        self.markdown_logger.add_text(f"**Extracted {len(tables)} Tables/Checklists:**")
                        for idx, table in enumerate(tables, 1):
                            self.markdown_logger.add_text(f"{idx}. {table.get('table_title', 'Untitled')} ({table.get('table_type', 'unknown')})")
                        self.markdown_logger.add_text("")
                
                # Return dict with all extraction results
                return {
                    "actions": actions,
                    "formulas": formulas,
                    "tables": tables
                }
            elif isinstance(result, list):
                # Legacy format: LLM returned list directly (backward compatibility)
                logger.info(f"📋 Extracted {len(result)} actions from node {node_id} (legacy list format)")
                
                for action in result:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                
                return {
                    "actions": result,
                    "formulas": [],
                    "tables": []
                }
            else:
                logger.warning(f"⚠️ Unexpected extraction result format for node {node_id}: {type(result)}")
                logger.warning(f"Result content: {str(result)[:500]}")
                
                if self.markdown_logger:
                    self.markdown_logger.log_processing_step(
                        f"⚠️ Unexpected LLM Response Format",
                        {
                            "node_id": node_id,
                            "expected": "dict with 'actions', 'formulas', 'tables' keys",
                            "received": str(type(result)),
                            "content_preview": str(result)[:300]
                        }
                    )
                return {"actions": [], "formulas": [], "tables": []}
                
        except Exception as e:
            logger.error(f"❌ Error in LLM extraction for node {node_id}: {e}", exc_info=True)
            
            if self.markdown_logger:
                self.markdown_logger.log_error(
                    f"LLM Extraction Error for {node_title}",
                    str(e)
                )
            
            return {"actions": [], "formulas": [], "tables": []}
    
    def _enhance_formulas_with_references(
        self,
        formulas: List[Dict[str, Any]],
        node: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Enhance extracted formulas with complete reference information.
        
        Args:
            formulas: Raw formula extractions from LLM
            node: Node metadata
            
        Returns:
            Enhanced formula objects with reference info
        """
        if not formulas:
            return []
        
        node_id = node.get('id', 'Unknown')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line', 0)
        end_line = node.get('end_line', 0)
        document = node.get('source', node.get('document', 'Unknown'))
        
        # Create reference object
        reference = create_reference(
            document=document,
            line_range=f"{start_line}-{end_line}",
            node_id=node_id,
            node_title=node_title
        )
        
        enhanced_formulas = []
        for formula_data in formulas:
            enhanced = create_formula_schema(
                formula=formula_data.get('formula', ''),
                computation_example=formula_data.get('computation_example', ''),
                sample_result=formula_data.get('sample_result', ''),
                formula_context=formula_data.get('formula_context', ''),
                reference=reference,
                related_actions=formula_data.get('related_actions', [])
            )
            enhanced_formulas.append(enhanced)
        
        logger.debug(f"Enhanced {len(enhanced_formulas)} formulas with reference information")
        return enhanced_formulas
    
    def _enhance_tables_with_references(
        self,
        tables: List[Dict[str, Any]],
        node: Dict[str, Any],
        content: str = "",
        node_title: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Enhance extracted tables with complete reference information and infer missing titles.
        
        Args:
            tables: Raw table extractions from LLM
            node: Node metadata
            content: Full node content for context
            node_title: Node title for title inference
            
        Returns:
            Enhanced table objects with reference info and inferred titles
        """
        if not tables:
            return []
        
        node_id = node.get('id', 'Unknown')
        if not node_title:
            node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line', 0)
        end_line = node.get('end_line', 0)
        document = node.get('source', node.get('document', 'Unknown'))
        
        # Create reference object
        reference = create_reference(
            document=document,
            line_range=f"{start_line}-{end_line}",
            node_id=node_id,
            node_title=node_title
        )
        
        enhanced_tables = []
        for table_data in tables:
            # Infer title if missing or generic
            original_title = table_data.get('table_title', 'Untitled')
            title_needs_inference = (
                not original_title or
                original_title.lower() in ['untitled', 'table', 'n/a', '']
            )
            
            if title_needs_inference:
                inferred_title = self._infer_table_title(
                    table_data,
                    context=content[:1000],  # First 1000 chars for context
                    node_title=node_title
                )
                table_data['table_title'] = inferred_title
                table_data['title_inferred'] = True
                logger.info(f"Inferred table title: '{inferred_title}'")
            else:
                table_data['title_inferred'] = False
            
            enhanced = create_table_schema(
                table_title=table_data.get('table_title', 'Untitled'),
                table_type=table_data.get('table_type', 'other'),
                headers=table_data.get('headers', []),
                rows=table_data.get('rows', []),
                markdown_content=table_data.get('markdown_content', ''),
                reference=reference,
                extracted_actions=table_data.get('extracted_actions', [])
            )
            # Add title_inferred flag to enhanced table
            enhanced['title_inferred'] = table_data.get('title_inferred', False)
            enhanced_tables.append(enhanced)
        
        logger.debug(f"Enhanced {len(enhanced_tables)} tables with reference information and title inference")
        return enhanced_tables
    
    def _segment_content(self, content: str, max_tokens: int = 2000) -> List[str]:
        """
        Segment content into chunks with smart markdown-aware boundaries.
        
        Target: ~2000 tokens (~8000 characters).
        Respects markdown structures: paragraphs, tables, lists, code blocks.
        
        Args:
            content: Full content text
            max_tokens: Maximum tokens per segment (approx: chars / 4)
            
        Returns:
            List of content segments
        """
        max_chars = max_tokens * 4  # Approximate conversion
        
        if len(content) <= max_chars:
            return [content]
        
        logger.debug(f"Segmenting content: {len(content)} chars into ~{max_chars} char segments")
        
        segments = []
        current_segment = []
        current_length = 0
        
        # Split content into structural blocks
        blocks = self._identify_markdown_blocks(content)
        
        for block in blocks:
            block_length = len(block)
            
            # If single block exceeds max, split at paragraph level
            if block_length > max_chars:
                if current_segment:
                    segments.append('\n\n'.join(current_segment))
                    current_segment = []
                    current_length = 0
                
                # Split large block into paragraphs
                sub_blocks = self._split_large_block(block, max_chars)
                segments.extend(sub_blocks)
                continue
            
            # Check if adding this block would exceed limit
            if current_length + block_length > max_chars and current_segment:
                # Save current segment and start new one
                segments.append('\n\n'.join(current_segment))
                current_segment = [block]
                current_length = block_length
            else:
                # Add to current segment
                current_segment.append(block)
                current_length += block_length + 2  # +2 for separator
        
        # Add remaining segment
        if current_segment:
            segments.append('\n\n'.join(current_segment))
        
        logger.debug(f"Created {len(segments)} segments")
        return segments
    
    def _identify_markdown_blocks(self, content: str) -> List[str]:
        """
        Identify markdown structural blocks (paragraphs, tables, lists, code blocks).
        
        Args:
            content: Markdown content
            
        Returns:
            List of content blocks
        """
        blocks = []
        lines = content.split('\n')
        current_block = []
        in_code_block = False
        in_table = False
        in_list = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Code block detection
            if stripped.startswith('```'):
                if in_code_block:
                    # End of code block
                    current_block.append(line)
                    blocks.append('\n'.join(current_block))
                    current_block = []
                    in_code_block = False
                else:
                    # Start of code block
                    if current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    current_block.append(line)
                    in_code_block = True
                i += 1
                continue
            
            if in_code_block:
                current_block.append(line)
                i += 1
                continue
            
            # Table detection (lines starting with |)
            if stripped.startswith('|'):
                if not in_table:
                    if current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    in_table = True
                current_block.append(line)
                i += 1
                continue
            elif in_table and stripped:
                # End of table
                blocks.append('\n'.join(current_block))
                current_block = []
                in_table = False
            
            # List detection
            is_list_item = bool(re.match(r'^(\s*[-*+]\s|^\s*\d+\.\s)', line))
            if is_list_item:
                if not in_list:
                    if current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    in_list = True
                current_block.append(line)
                i += 1
                continue
            elif in_list and stripped and not is_list_item:
                # End of list
                blocks.append('\n'.join(current_block))
                current_block = []
                in_list = False
            
            # Horizontal rule
            if re.match(r'^-{3,}$', stripped):
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                blocks.append(line)
                i += 1
                continue
            
            # Empty line - potential paragraph boundary
            if not stripped:
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                i += 1
                continue
            
            # Regular line - add to current block
            current_block.append(line)
            i += 1
        
        # Add remaining block
        if current_block:
            blocks.append('\n'.join(current_block))
        
        return blocks
    
    def _split_large_block(self, block: str, max_chars: int) -> List[str]:
        """
        Split a large block at paragraph boundaries.
        
        Args:
            block: Large content block
            max_chars: Maximum characters per segment
            
        Returns:
            List of sub-segments
        """
        # Split into sentences or newlines
        parts = block.split('\n')
        segments = []
        current = []
        current_length = 0
        
        for part in parts:
            part_length = len(part)
            
            if current_length + part_length > max_chars and current:
                segments.append('\n'.join(current))
                current = [part]
                current_length = part_length
            else:
                current.append(part)
                current_length += part_length + 1
        
        if current:
            segments.append('\n'.join(current))
        
        return segments
    
    def _extract_from_segments(
        self,
        subject: str,
        node: Dict[str, Any],
        segments: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract actions, formulas, and tables from multiple segments with memory.
        
        Processes each segment sequentially, passing summary of previous
        extractions to avoid duplicates.
        
        Args:
            subject: Subject name
            node: Node metadata
            segments: List of content segments
            
        Returns:
            Dictionary with "actions", "formulas", "tables" keys
        """
        node_id = node.get('id', 'Unknown')
        all_actions = []
        all_formulas = []
        all_tables = []
        extraction_summary = ""
        
        logger.info(f"Processing {len(segments)} segments for node {node_id}")
        
        for idx, segment in enumerate(segments, 1):
            logger.info(f"Processing segment {idx}/{len(segments)} ({len(segment)} chars)")
            
            if idx == 1:
                # First segment: normal extraction
                result = self._llm_extract_actions(subject, node, segment)
            else:
                # Subsequent segments: pass summary + new content
                result = self._llm_extract_actions_with_memory(
                    subject, node, segment, extraction_summary
                )
            
            # Extract components
            actions = result.get("actions", [])
            formulas = result.get("formulas", [])
            tables = result.get("tables", [])
            
            if actions or formulas or tables:
                logger.info(f"  → Extracted from segment {idx}: {len(actions)} actions, {len(formulas)} formulas, {len(tables)} tables")
                all_actions.extend(actions)
                all_formulas.extend(formulas)
                all_tables.extend(tables)
                
                # Update summary for next iteration (actions only)
                extraction_summary = self._create_extraction_summary(all_actions)
            else:
                logger.info(f"  → No items from segment {idx}")
        
        logger.info(f"Total from {len(segments)} segments: {len(all_actions)} actions, {len(all_formulas)} formulas, {len(all_tables)} tables")
        return {
            "actions": all_actions,
            "formulas": all_formulas,
            "tables": all_tables
        }
    
    def _llm_extract_actions_with_memory(
        self,
        subject: str,
        node: Dict[str, Any],
        content: str,
        previous_summary: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract actions, formulas, and tables with memory of previous extractions.
        
        Args:
            subject: Subject name
            node: Node metadata
            content: Segment content
            previous_summary: Summary of previously extracted actions
            
        Returns:
            Dictionary with "actions", "formulas", "tables" keys
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.debug(f"Extracting with memory from node {node_id} segment")
        
        prompt = f"""Extract NEW actionable items, formulas, and tables from this content related to the subject: {subject}

Source Node: {node_title} (ID: {node_id})
Lines: {start_line}-{end_line}

PREVIOUSLY EXTRACTED ACTIONS FROM THIS SECTION:
{previous_summary}

CURRENT SEGMENT CONTENT:
{content}

Extract NEW items from the current segment that are NOT already covered in previous extractions.
Avoid duplicating items already listed above.

Extract at MAXIMUM GRANULARITY:
- ACTIONS: Atomic, quantitative, independently executable (NOT qualitative goals)
- FORMULAS: All mathematical expressions with computation examples
- TABLES: All tables, checklists, structured lists

Respond with a JSON object:
{{
  "actions": [
    {{
      "action": "WHO does WHAT WHEN",
      "who": "Specific role/unit",
      "when": "Precise timeline/trigger",
      "what": "Detailed activity with specific values, methods, tools",
      "context": "Brief context explaining why/how"
    }}
  ],
  "formulas": [
    {{
      "formula": "Raw equation as written",
      "computation_example": "Worked example with specific values",
      "sample_result": "Calculated output",
      "formula_context": "What it calculates and when to use it"
    }}
  ],
  "tables": [
    {{
      "table_title": "Descriptive title",
      "table_type": "checklist|action_table|decision_matrix|other",
      "headers": ["column1", "column2"],
      "rows": [["data1", "data2"]],
      "markdown_content": "Original markdown table"
    }}
  ]
}}

Focus on NEW items not in the previous extraction summary.
Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            if isinstance(result, dict):
                actions = result.get("actions", [])
                formulas = result.get("formulas", [])
                tables = result.get("tables", [])
                
                logger.info(f"Extracted with memory: {len(actions)} actions, {len(formulas)} formulas, {len(tables)} tables")
                
                # Add metadata to actions
                for action in actions:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                
                return {
                    "actions": actions,
                    "formulas": formulas,
                    "tables": tables
                }
            else:
                logger.warning(f"Unexpected result format: {type(result)}")
                return {"actions": [], "formulas": [], "tables": []}
                
        except Exception as e:
            logger.error(f"Error in memory-aware extraction: {e}", exc_info=True)
            return {"actions": [], "formulas": [], "tables": []}
    
    def _create_extraction_summary(self, actions: List[Dict[str, Any]]) -> str:
        """
        Create a concise summary of extracted actions for memory context.
        
        Args:
            actions: List of extracted actions
            
        Returns:
            Summary string (limited to ~500 characters)
        """
        if not actions:
            return "None extracted yet."
        
        summary_lines = []
        total_length = 0
        max_length = 500
        
        for idx, action in enumerate(actions, 1):
            action_text = action.get('action', 'Unknown action')
            line = f"{idx}. {action_text}"
            
            if total_length + len(line) > max_length:
                summary_lines.append(f"... and {len(actions) - idx + 1} more actions")
                break
            
            summary_lines.append(line)
            total_length += len(line) + 1
        
        return '\n'.join(summary_lines)
    
    def _generate_formatted_output(
        self,
        all_actions: List[Dict[str, Any]],
        all_tables: List[Dict[str, Any]],
        subject_name: str = "All Subjects"
    ) -> str:
        """
        Generate human-readable formatted output with WHO-based grouping.
        
        Format:
        - Groups actions by WHO (responsible actor)
        - Within each WHO group, lists actions with timing flags inline
        - Actions with integrated formulas show the formula inline
        - Separate section for actor-unclear actions
        - Includes all tables
        - Uses visual separators for clarity
        
        Args:
            all_actions: List of all actions (complete and flagged, with formulas integrated)
            all_tables: List of all tables/checklists
            subject_name: Name of the subject being processed
            
        Returns:
            Formatted text output
        """
        output_lines = []
        
        # Header
        output_lines.append("=" * 80)
        output_lines.append(f"=== SUBJECT: {subject_name} ===")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        # Separate actions by actor validity
        actions_with_actor = [a for a in all_actions if not a.get('actor_flagged', False)]
        actions_without_actor = [a for a in all_actions if a.get('actor_flagged', False)]
        
        # Group actions with valid WHO by their WHO value
        actions_by_who = {}
        for action in actions_with_actor:
            who = action.get('who', 'Unknown')
            if who not in actions_by_who:
                actions_by_who[who] = []
            actions_by_who[who].append(action)
        
        # Generate output for each WHO group
        for who, actions in sorted(actions_by_who.items()):
            output_lines.append(f"WHO: {who}")
            output_lines.append("─" * 80)
            
            # List actions for this WHO
            for idx, action in enumerate(actions, 1):
                action_text = action.get('action', 'N/A')
                
                # Add timing flag if applicable
                if action.get('timing_flagged', False):
                    action_text += " [🚩 FLAGGED: timing not clearly mentioned]"
                
                output_lines.append(f"ACTION {idx}: {action_text}")
            
            output_lines.append("")
            
            # Find tables related to this WHO (if any)
            related_tables = [t for t in all_tables if any(
                a.get('id') in t.get('extracted_actions', [])
                for a in actions
            )]
            
            if related_tables:
                for table in related_tables:
                    output_lines.append(f"📋 TABLE: {table.get('table_title', 'Untitled')}")
                    output_lines.append(table.get('markdown_content', '[Table content not available]'))
                    output_lines.append("")
            
            # Add reference for this WHO group (using first action's reference)
            if actions:
                ref = actions[0].get('reference', {})
                doc = ref.get('document', 'Unknown')
                line_range = ref.get('line_range', 'Unknown')
                node_id = ref.get('node_id', 'Unknown')
                output_lines.append(f"📎 REFERENCE: {doc}, lines {line_range}, node {node_id}")
            
            output_lines.append("")
            output_lines.append("=" * 80)
            output_lines.append("")
        
        # Add tables (not linked to any action)
        unrelated_tables = [t for t in all_tables if not t.get('extracted_actions')]
        if unrelated_tables:
            output_lines.append("📋 ADDITIONAL TABLES/CHECKLISTS")
            output_lines.append("─" * 80)
            for table in unrelated_tables:
                output_lines.append(f"Title: {table.get('table_title', 'Untitled')}")
                output_lines.append(f"Type: {table.get('table_type', 'other')}")
                output_lines.append(table.get('markdown_content', '[Table content not available]'))
                ref = table.get('reference', {})
                output_lines.append(f"📎 Reference: {ref.get('document', 'Unknown')}, lines {ref.get('line_range', 'Unknown')}")
                output_lines.append("")
            output_lines.append("=" * 80)
            output_lines.append("")
        
        # Section for actions with unclear actors
        if actions_without_actor:
            output_lines.append("🚩 FLAGGED ACTIONS (Unclear Responsible Actor)")
            output_lines.append("─" * 80)
            
            for idx, action in enumerate(actions_without_actor, 1):
                action_text = action.get('action', 'N/A')
                ref = action.get('reference', {})
                ref_str = f"{ref.get('document', 'Unknown')}, lines {ref.get('line_range', 'Unknown')}"
                output_lines.append(f"ACTION {idx}: {action_text} | Source: {ref_str}")
            
            output_lines.append("")
            output_lines.append("=" * 80)
            output_lines.append("")
        
        return '\n'.join(output_lines)
    
    def _recover_corrupted_markdown(self, content: str, context: str = "") -> Tuple[str, bool, str]:
        """
        Use LLM to intelligently recover corrupted or incomplete markdown structures.
        
        Detects and repairs:
        - Incomplete table rows
        - Missing headers or header separators
        - Malformed lists
        - Broken code blocks
        
        Args:
            content: Potentially corrupted markdown content
            context: Surrounding context for semantic understanding
            
        Returns:
            Tuple of (recovered_content, was_recovered, recovery_notes)
        """
        logger.debug("Checking content for markdown corruption...")
        
        # Detect potential corruption patterns
        corruption_detected = False
        issues = []
        
        lines = content.split('\n')
        in_table = False
        table_col_count = None
        
        for idx, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for table issues
            if stripped.startswith('|'):
                if not in_table:
                    in_table = True
                    # Check for header separator
                    if idx + 1 < len(lines):
                        next_line = lines[idx + 1].strip()
                        if not (next_line.startswith('|') and '-' in next_line):
                            corruption_detected = True
                            issues.append(f"Line {idx + 1}: Missing table header separator")
                
                # Count columns
                cols = len([c for c in stripped.split('|') if c.strip()])
                if table_col_count is None:
                    table_col_count = cols
                elif cols != table_col_count and '-' not in stripped:
                    corruption_detected = True
                    issues.append(f"Line {idx + 1}: Table column mismatch (expected {table_col_count}, got {cols})")
            elif in_table and stripped:
                in_table = False
                table_col_count = None
            
            # Check for broken code blocks
            if stripped.startswith('```'):
                # Check if there's a closing marker
                remaining = '\n'.join(lines[idx + 1:])
                if '```' not in remaining:
                    corruption_detected = True
                    issues.append(f"Line {idx + 1}: Unclosed code block")
        
        if not corruption_detected:
            logger.debug("No corruption detected in content")
            return content, False, "No corruption detected"
        
        logger.warning(f"Markdown corruption detected: {len(issues)} issues found")
        logger.warning(f"Issues: {', '.join(issues)}")
        
        # Use LLM to recover
        try:
            recovery_prompt = f"""Corrupted markdown content needs repair.

**Issues Detected:**
{chr(10).join(f"- {issue}" for issue in issues)}

**Surrounding Context:**
{context[:500] if context else "No additional context provided"}

**Content to Recover:**
{content}

**Instructions:**
1. Fix all detected structural issues
2. Preserve all actual content exactly
3. Use "..." or empty cells for truly missing data
4. Return ONLY the corrected markdown
5. After the corrected markdown, add a line starting with "CORRECTIONS:" explaining what was fixed

**Output Format:**
[Corrected markdown here]

CORRECTIONS: [Brief explanation of fixes]"""
            
            recovery_prompt_system = get_prompt("markdown_recovery")
            
            result = self.llm.generate(
                prompt=recovery_prompt,
                system_prompt=recovery_prompt_system,
                temperature=0.1
            )
            
            # Parse result to separate recovered content from corrections note
            if "CORRECTIONS:" in result:
                parts = result.split("CORRECTIONS:", 1)
                recovered_content = parts[0].strip()
                recovery_notes = "CORRECTIONS:" + parts[1].strip()
            else:
                recovered_content = result.strip()
                recovery_notes = "Recovered but no correction notes provided"
            
            logger.info(f"Markdown recovery successful. {recovery_notes}")
            
            if self.markdown_logger:
                self.markdown_logger.add_text("### Markdown Recovery Applied")
                self.markdown_logger.add_text(f"**Issues Found:** {len(issues)}")
                for issue in issues:
                    self.markdown_logger.add_list_item(issue, level=0)
                self.markdown_logger.add_text(f"**Recovery Notes:** {recovery_notes}")
                self.markdown_logger.add_text("")
            
            return recovered_content, True, recovery_notes
            
        except Exception as e:
            logger.error(f"Error in markdown recovery: {e}", exc_info=True)
            return content, False, f"Recovery failed: {str(e)}"
    
    def _infer_table_title(self, table_data: Dict[str, Any], context: str = "", node_title: str = "") -> str:
        """
        Use LLM to infer a contextually appropriate title for a table/checklist.
        
        Args:
            table_data: Table structure (headers, rows, type)
            context: Surrounding document context
            node_title: Title of the containing document section
            
        Returns:
            Inferred title string
        """
        # Check if table already has a title
        existing_title = table_data.get('table_title', '').strip()
        if existing_title and existing_title.lower() not in ['untitled', 'table', 'n/a', '']:
            logger.debug(f"Table already has title: {existing_title}")
            return existing_title
        
        logger.info("Inferring title for untitled table...")
        
        try:
            # Prepare table description
            headers = table_data.get('headers', [])
            rows = table_data.get('rows', [])
            table_type = table_data.get('table_type', 'other')
            markdown_content = table_data.get('markdown_content', '')
            
            # Sample first few rows for context
            sample_rows = rows[:3] if rows else []
            
            inference_prompt = f"""Infer a descriptive title for this table.

**Document Section:** {node_title if node_title else "Unknown section"}

**Surrounding Context:**
{context[:600] if context else "No additional context provided"}

**Table Type:** {table_type}

**Table Headers:** {', '.join(headers) if headers else "No headers"}

**Sample Rows (first 3):**
{json.dumps(sample_rows, indent=2) if sample_rows else "No row data"}

**Table Markdown:**
{markdown_content[:400] if markdown_content else "Not available"}

Based on the context and table structure, generate a specific, descriptive title (5-12 words).
Return ONLY the title, no quotes, no explanation."""
            
            inference_prompt_system = get_prompt("table_title_inference")
            
            inferred_title = self.llm.generate(
                prompt=inference_prompt,
                system_prompt=inference_prompt_system,
                temperature=0.3
            ).strip()
            
            # Clean up the title
            inferred_title = inferred_title.strip('"\'')
            
            logger.info(f"Inferred table title: '{inferred_title}'")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"**Table Title Inferred:** '{inferred_title}'")
                self.markdown_logger.add_list_item(f"Type: {table_type}", level=1)
                self.markdown_logger.add_list_item(f"Headers: {', '.join(headers) if headers else 'None'}", level=1)
                self.markdown_logger.add_text("")
            
            return inferred_title
            
        except Exception as e:
            logger.error(f"Error inferring table title: {e}", exc_info=True)
            # Fallback to generic title based on type
            return f"{table_type.title()} Table from {node_title}" if node_title else f"{table_type.title()} Table"
    
    def _integrate_formulas_into_actions(
        self,
        actions: List[Dict[str, Any]],
        formulas: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Integrates formulas into related actions by updating the 'what' field.
        
        Args:
            actions: List of action dictionaries
            formulas: List of formula dictionaries
            
        Returns:
            Tuple containing:
            - Updated list of actions with formulas integrated.
            - Count of formulas merged.
        """
        if not formulas:
            return actions, 0

        # Use a simple text-matching approach for now
        # This could be improved with semantic search or more advanced NLP
        
        updated_actions = actions.copy()
        formulas_merged = 0
        
        for formula in formulas:
            formula_text = formula.get('formula', '')
            related_action_text = formula.get('related_actions', [])
            
            if not related_action_text:
                continue

            # Find the best matching action
            # For now, just use the first related action text
            target_action_text = related_action_text[0]
            
            found_match = False
            for action in updated_actions:
                if target_action_text in action.get('action', ''):
                    # Append formula details to the 'action' field
                    formula_desc = (
                        f"Calculate using formula: `{formula_text}`. "
                        f"Example: `{formula.get('computation_example', '')}` = `{formula.get('sample_result', '')}`. "
                        f"Apply when: `{formula.get('formula_context', '')}`."
                    )
                    action['action'] = f"{action['action']}. {formula_desc}"
                    
                    formulas_merged += 1
                    formula['merged_into_actions'] = True
                    found_match = True
                    break # Assume one-to-one mapping for now
            
            if not found_match:
                logger.warning(f"Could not find a matching action for formula: {formula_text}")

        logger.info(f"Successfully integrated {formulas_merged} formula-action links")
        
        if self.markdown_logger and formulas_merged > 0:
            self.markdown_logger.add_processing_step(
                "Formula-Action Integration",
                f"Integrated {formulas_merged} formulas directly into the 'action' field of their corresponding actions."
            )

        return updated_actions, formulas_merged
    
    def _validate_schema_compliance(
        self,
        actions: List[Dict[str, Any]],
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate all outputs against expected JSON schemas before returning.
        
        Checks:
        - Actions: WHO, WHEN, WHAT, context, reference
        - Tables: table_title, table_type, headers, rows, markdown_content
        
        Note: Formulas are now integrated into actions, not validated separately.
        
        Args:
            actions: List of action objects
            tables: List of table objects
            
        Returns:
            Dictionary with validation results and any errors found
        """
        logger.debug("Validating schema compliance for all extracted items...")
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "actions_validated": len(actions),
            "tables_validated": len(tables)
        }
        
        # Validate actions
        required_action_fields = ['who', 'when', 'what', 'reference', 'context']
        for idx, action in enumerate(actions):
            for field in required_action_fields:
                if field not in action or action[field] is None:
                    error_msg = f"Action {idx} missing required field: {field}"
                    validation_results['errors'].append(error_msg)
                    validation_results['valid'] = False
                    logger.error(error_msg)
                elif field == 'reference':
                    # Validate reference structure
                    ref = action[field]
                    if not isinstance(ref, dict):
                        error_msg = f"Action {idx} reference is not a dict: {type(ref)}"
                        validation_results['errors'].append(error_msg)
                        validation_results['valid'] = False
                    else:
                        for ref_field in ['document', 'line_range', 'node_id', 'node_title']:
                            if ref_field not in ref:
                                error_msg = f"Action {idx} reference missing field: {ref_field}"
                                validation_results['errors'].append(error_msg)
                                validation_results['valid'] = False
        
        # Validate tables
        required_table_fields = ['table_title', 'table_type', 'headers', 'rows', 'reference']
        for idx, table in enumerate(tables):
            for field in required_table_fields:
                if field not in table or table[field] is None:
                    error_msg = f"Table {idx} missing required field: {field}"
                    validation_results['errors'].append(error_msg)
                    validation_results['valid'] = False
                    logger.error(error_msg)
            
            # Check if table is empty (shell table)
            if not table.get('rows') and not table.get('markdown_content'):
                warning_msg = f"Table {idx} ('{table.get('table_title', 'Untitled')}') appears to be empty - no rows or markdown content"
                validation_results['warnings'].append(warning_msg)
                logger.warning(warning_msg)
        
        if validation_results['valid']:
            logger.info(f"✅ Schema validation passed: {len(actions)} actions, {len(tables)} tables")
        else:
            logger.error(f"❌ Schema validation failed with {len(validation_results['errors'])} errors")
        
        if validation_results['warnings']:
            logger.warning(f"⚠️ Schema validation found {len(validation_results['warnings'])} warnings")
        
        return validation_results
    
    def _check_quality(self, subject: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Consult Quality Agent for action validation.
        
        Args:
            subject: Subject name
            actions: Extracted actions
            
        Returns:
            Quality check result
        """
        if not self.quality_agent:
            return {"needs_refinement": False}
        
        try:
            # Call quality agent
            quality_result = self.quality_agent.execute(
                {"actions": actions, "subject": subject},
                stage="extractor"
            )
            
            return quality_result
        except Exception as e:
            logger.error(f"Quality check error: {e}")
            return {"needs_refinement": False}
