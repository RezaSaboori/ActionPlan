"""Extractor Agent for multi-subject action extraction with who/when/what format."""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from utils.llm_client import LLMClient
from rag_tools.graph_rag import GraphRAG
from utils.document_parser import DocumentParser
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


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
        Execute multi-subject extraction logic.
        
        Args:
            data: Dictionary containing:
                - subject_nodes: List of {subject: str, nodes: List[Dict]}
                
        Returns:
            Dictionary with:
                - complete_actions: List of actions with who/when defined
                - flagged_actions: List of actions missing who/when
                - subject_actions: List of {subject: str, actions: List[Dict]} (for compatibility)
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
        subject_actions = []
        
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
            
            # Extract actions for this subject
            complete, flagged = self._process_subject(subject, nodes)
            
            # Aggregate across all subjects
            all_complete_actions.extend(complete)
            all_flagged_actions.extend(flagged)
            
            # Also maintain subject grouping for compatibility
            subject_actions.append({
                "subject": subject,
                "complete_actions": complete,
                "flagged_actions": flagged,
                "actions": complete + flagged  # Combined for backward compatibility
            })
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SUBJECT '{subject}' COMPLETED: {len(complete)} complete, {len(flagged)} flagged actions")
            logger.info(f"{'='*80}\n")
        
        logger.info(f"=" * 80)
        logger.info(f"EXTRACTOR AGENT COMPLETED")
        logger.info(f"Total complete actions: {len(all_complete_actions)}")
        logger.info(f"Total flagged actions: {len(all_flagged_actions)}")
        logger.info(f"Total actions: {len(all_complete_actions) + len(all_flagged_actions)}")
        logger.info(f"=" * 80)
        
        return {
            "complete_actions": all_complete_actions,
            "flagged_actions": all_flagged_actions,
            "subject_actions": subject_actions
        }
    
    def _process_subject(self, subject: str, nodes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process all nodes for a single subject.
        
        Args:
            subject: Subject name
            nodes: List of nodes with metadata
            
        Returns:
            Tuple of (complete_actions, flagged_actions)
        """
        if not nodes:
            logger.warning(f"No nodes provided for subject: {subject}")
            return [], []
        
        logger.info(f"Processing {len(nodes)} nodes for subject '{subject}'")
        
        complete_actions = []
        flagged_actions = []
        
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
            
            node_complete, node_flagged = self._extract_from_node(subject, node)
            
            # Add to temp lists
            complete_actions.extend(node_complete)
            flagged_actions.extend(node_flagged)
            
            # Log accumulation after each node
            logger.info(f"  → This node: {len(node_complete)} complete, {len(node_flagged)} flagged actions")
            logger.info(f"  ✅ Added to temp lists. Running totals: {len(complete_actions)} complete, {len(flagged_actions)} flagged")
            
            if self.markdown_logger:
                self.markdown_logger.add_text(f"**Node Extraction Summary:**")
                self.markdown_logger.add_list_item(f"Complete actions from this node: {len(node_complete)}", level=0)
                self.markdown_logger.add_list_item(f"Flagged actions from this node: {len(node_flagged)}", level=0)
                self.markdown_logger.add_text("")
                self.markdown_logger.add_text(f"**🎯 Running Totals After Node {idx}:**")
                self.markdown_logger.add_list_item(f"Total complete actions: {len(complete_actions)}", level=0)
                self.markdown_logger.add_list_item(f"Total flagged actions: {len(flagged_actions)}", level=0)
                self.markdown_logger.add_list_item(f"Total all actions: {len(complete_actions) + len(flagged_actions)}", level=0)
                self.markdown_logger.add_text("")
        
        logger.info(f"✅ Subject '{subject}' complete: {len(complete_actions)} complete, {len(flagged_actions)} flagged actions total")
        
        return complete_actions, flagged_actions
    
    def _extract_from_node(self, subject: str, node: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract actions from a single node.
        
        Reads complete content using line numbers and extracts in who/when/what format.
        Automatically segments long content and processes with memory.
        Validates each action and separates into complete/flagged lists.
        
        Args:
            subject: Subject name
            node: Node metadata with id, start_line, end_line
            
        Returns:
            Tuple of (complete_actions, flagged_actions)
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
            
            return [], []
        
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
            
            return [], []
        
        logger.info(f"✅ Content retrieved for node {node_id}, length: {len(content)} characters")
        
        if self.markdown_logger:
            self.markdown_logger.add_text(f"✅ **Content Retrieved Successfully**")
            self.markdown_logger.add_list_item(f"Content length: {len(content)} characters", level=0)
            self.markdown_logger.add_list_item(f"Content preview: {content[:200]}...", level=0)
            self.markdown_logger.add_text("")
        
        # Estimate tokens (rough: chars / 4)
        estimated_tokens = len(content) / 4
        
        if estimated_tokens > 2000:
            # Segment and process with memory
            logger.info(f"Node {node_id} is large ({estimated_tokens:.0f} tokens), segmenting...")
            segments = self._segment_content(content, max_tokens=2000)
            logger.info(f"Split into {len(segments)} segments")
            actions = self._extract_from_segments(subject, node, segments)
        else:
            # Process as single unit
            logger.debug(f"Node {node_id} fits in single segment ({estimated_tokens:.0f} tokens)")
            actions = self._llm_extract_actions(subject, node, content)
        
        # Validate and separate actions into complete/flagged
        complete_actions, flagged_actions = self._validate_and_separate_actions(actions, node_id, node_title)
        
        # Log detailed results to markdown
        self._log_node_extraction_details(node_id, node_title, start_line, end_line, 
                                          complete_actions, flagged_actions)
        
        if complete_actions or flagged_actions:
            logger.info(f"Successfully extracted from node {node_id}: {len(complete_actions)} complete, {len(flagged_actions)} flagged")
        else:
            logger.warning(f"No actions extracted from node {node_id} ({node_title})")
        
        return complete_actions, flagged_actions
    
    def _validate_and_separate_actions(
        self, 
        actions: List[Dict[str, Any]], 
        node_id: str, 
        node_title: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate actions and separate into complete and flagged lists.
        
        Complete actions have both 'who' and 'when' defined and non-generic.
        Flagged actions are missing one or both of these fields.
        
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
            
            # Categorize action
            if who_is_valid and when_is_valid:
                # Complete action
                complete_actions.append(action)
                logger.info(f"✅ Action {idx}: COMPLETE - {action_text[:80]}")
                
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"✅ **Action {idx}: COMPLETE**")
                    self.markdown_logger.add_list_item(f"Action: {action_text}", level=1)
                    self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}'", level=1)
                    self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}'", level=1)
                    self.markdown_logger.add_text("")
            else:
                # Flagged action
                action['missing_fields'] = missing_fields
                action['flag_reason'] = '; '.join(flag_reasons)
                action['flagged'] = True
                flagged_actions.append(action)
                logger.warning(f"⚠️ Action {idx}: FLAGGED (missing {', '.join(missing_fields)}) - {action_text[:80]}")
                
                if self.markdown_logger:
                    self.markdown_logger.add_text(f"⚠️ **Action {idx}: FLAGGED**")
                    self.markdown_logger.add_list_item(f"Action: {action_text}", level=1)
                    self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}' (valid: {who_is_valid})", level=1)
                    self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}' (valid: {when_is_valid})", level=1)
                    self.markdown_logger.add_list_item(f"Missing: {', '.join(missing_fields)}", level=1)
                    self.markdown_logger.add_list_item(f"Reason: {action['flag_reason']}", level=1)
                    self.markdown_logger.add_text("")
        
        logger.info(f"📊 Validation results for node {node_id}: {len(complete_actions)} complete, {len(flagged_actions)} flagged")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                f"Validation Summary for {node_title}",
                {
                    "complete_actions": len(complete_actions),
                    "flagged_actions": len(flagged_actions),
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
                self.markdown_logger.add_list_item(f"WHAT: {action.get('what', 'N/A')}", level=1)
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
                self.markdown_logger.add_list_item(f"WHAT: {action.get('what', 'N/A')}", level=1)
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
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract actions in structured who/when/what format.
        
        Args:
            subject: Subject name
            node: Node metadata
            content: Full content text
            
        Returns:
            List of extracted actions
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.debug(f"Extracting actions from node {node_id} ({node_title}) for subject '{subject}'")
        logger.debug(f"Content length: {len(content)} characters")
        
        prompt = f"""Extract actionable items from this content related to the subject: {subject}

Source Node: {node_title} (ID: {node_id})
Lines: {start_line}-{end_line}

Content:
{content}

Extract actions in the following structured format:

For each action, identify:
- WHO: Responsible role/unit (e.g., "Incident Commander", "Triage Team", "EOC")
- WHEN: Timeline or trigger (e.g., "Within 1 hour", "Immediately upon notification", "During phase 1")
- WHAT: Specific activity or task (clear and actionable)

Respond with a JSON object:
{{
  "actions": [
    {{
      "action": "WHO does WHAT",
      "who": "Responsible role/unit",
      "when": "Timeline or trigger",
      "what": "Specific activity",
      "source_node": "{node_id}",
      "source_lines": "{start_line}-{end_line}",
      "context": "Brief context from content"
    }}
  ]
}}

Extract 3-10 most important actions from this content. Focus on concrete, implementable actions.
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
            
            if isinstance(result, dict) and "actions" in result:
                actions = result["actions"]
                logger.info(f"📋 Extracted {len(actions)} actions from node {node_id}")
                
                # Log each extracted action before validation
                if self.markdown_logger and actions:
                    self.markdown_logger.add_text(f"**Raw Extracted Actions (Before Validation):**")
                    for idx, action in enumerate(actions, 1):
                        self.markdown_logger.add_text(f"{idx}. {action.get('action', 'N/A')}")
                        self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}'", level=1)
                        self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}'", level=1)
                        self.markdown_logger.add_list_item(f"WHAT: '{action.get('what', 'N/A')}'", level=1)
                    self.markdown_logger.add_text("")
                
                # Add full_context field
                for action in actions:
                    action['full_context'] = content[:500]  # First 500 chars as context
                    action['subject'] = subject
                
                return actions
            elif isinstance(result, list):
                # If LLM returned list directly
                logger.info(f"📋 Extracted {len(result)} actions from node {node_id} (list format)")
                
                if self.markdown_logger and result:
                    self.markdown_logger.add_text(f"**Raw Extracted Actions (List Format, Before Validation):**")
                    for idx, action in enumerate(result, 1):
                        self.markdown_logger.add_text(f"{idx}. {action.get('action', 'N/A')}")
                        self.markdown_logger.add_list_item(f"WHO: '{action.get('who', 'N/A')}'", level=1)
                        self.markdown_logger.add_list_item(f"WHEN: '{action.get('when', 'N/A')}'", level=1)
                        self.markdown_logger.add_list_item(f"WHAT: '{action.get('what', 'N/A')}'", level=1)
                    self.markdown_logger.add_text("")
                
                for action in result:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                return result
            else:
                logger.warning(f"⚠️ Unexpected extraction result format for node {node_id}: {type(result)}")
                logger.warning(f"Result content: {str(result)[:500]}")
                
                if self.markdown_logger:
                    self.markdown_logger.log_processing_step(
                        f"⚠️ Unexpected LLM Response Format",
                        {
                            "node_id": node_id,
                            "expected": "dict with 'actions' key or list",
                            "received": str(type(result)),
                            "content_preview": str(result)[:300]
                        }
                    )
                return []
                
        except Exception as e:
            logger.error(f"❌ Error in LLM extraction for node {node_id}: {e}", exc_info=True)
            
            if self.markdown_logger:
                self.markdown_logger.log_error(
                    f"LLM Extraction Error for {node_title}",
                    str(e)
                )
            
            return []
    
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
    ) -> List[Dict[str, Any]]:
        """
        Extract actions from multiple segments with memory.
        
        Processes each segment sequentially, passing summary of previous
        extractions to avoid duplicates.
        
        Args:
            subject: Subject name
            node: Node metadata
            segments: List of content segments
            
        Returns:
            Combined list of actions from all segments
        """
        node_id = node.get('id', 'Unknown')
        all_actions = []
        extraction_summary = ""
        
        logger.info(f"Processing {len(segments)} segments for node {node_id}")
        
        for idx, segment in enumerate(segments, 1):
            logger.info(f"Processing segment {idx}/{len(segments)} ({len(segment)} chars)")
            
            if idx == 1:
                # First segment: normal extraction
                actions = self._llm_extract_actions(subject, node, segment)
            else:
                # Subsequent segments: pass summary + new content
                actions = self._llm_extract_actions_with_memory(
                    subject, node, segment, extraction_summary
                )
            
            if actions:
                logger.info(f"  → Extracted {len(actions)} actions from segment {idx}")
                all_actions.extend(actions)
                
                # Update summary for next iteration
                extraction_summary = self._create_extraction_summary(all_actions)
            else:
                logger.info(f"  → No actions from segment {idx}")
        
        logger.info(f"Total: {len(all_actions)} actions from {len(segments)} segments")
        return all_actions
    
    def _llm_extract_actions_with_memory(
        self,
        subject: str,
        node: Dict[str, Any],
        content: str,
        previous_summary: str
    ) -> List[Dict[str, Any]]:
        """
        Extract actions with memory of previous extractions to avoid duplicates.
        
        Args:
            subject: Subject name
            node: Node metadata
            content: Segment content
            previous_summary: Summary of previously extracted actions
            
        Returns:
            List of extracted actions
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.debug(f"Extracting with memory from node {node_id} segment")
        
        prompt = f"""Extract actionable items from this content related to the subject: {subject}

Source Node: {node_title} (ID: {node_id})
Lines: {start_line}-{end_line}

PREVIOUSLY EXTRACTED ACTIONS FROM THIS SECTION:
{previous_summary}

CURRENT SEGMENT CONTENT:
{content}

Extract NEW actions from the current segment that are NOT already covered in previous extractions.
Avoid duplicating actions already listed above.

Extract actions in the following structured format:

For each action, identify:
- WHO: Responsible role/unit (e.g., "Incident Commander", "Triage Team", "EOC")
- WHEN: Timeline or trigger (e.g., "Within 1 hour", "Immediately upon notification", "During phase 1")
- WHAT: Specific activity or task (clear and actionable)

Respond with a JSON object:
{{
  "actions": [
    {{
      "action": "WHO does WHAT",
      "who": "Responsible role/unit",
      "when": "Timeline or trigger",
      "what": "Specific activity",
      "source_node": "{node_id}",
      "source_lines": "{start_line}-{end_line}",
      "context": "Brief context from content"
    }}
  ]
}}

Extract 3-10 most important NEW actions from this segment. Focus on concrete, implementable actions.
Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            if isinstance(result, dict) and "actions" in result:
                actions = result["actions"]
                logger.info(f"Extracted {len(actions)} new actions with memory")
                
                # Add metadata
                for action in actions:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                
                return actions
            elif isinstance(result, list):
                logger.info(f"Extracted {len(result)} new actions with memory (list format)")
                for action in result:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                return result
            else:
                logger.warning(f"Unexpected result format: {type(result)}")
                return []
                
        except Exception as e:
            logger.error(f"Error in memory-aware extraction: {e}", exc_info=True)
            return []
    
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
