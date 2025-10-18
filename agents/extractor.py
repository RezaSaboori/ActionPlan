"""Extractor Agent for multi-subject action extraction with who/when/what format."""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from utils.llm_client import OllamaClient
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
        llm_client: OllamaClient,
        graph_rag: Optional[GraphRAG] = None,
        quality_agent=None,
        orchestrator_agent=None,
        markdown_logger=None
    ):
        """
        Initialize Enhanced Extractor Agent.
        
        Args:
            llm_client: Ollama client instance
            graph_rag: Graph RAG for content retrieval (optional)
            quality_agent: Quality checker agent for validation (optional)
            orchestrator_agent: Orchestrator for clarifications (optional)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.graph_rag = graph_rag
        self.quality_agent = quality_agent
        self.orchestrator_agent = orchestrator_agent
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("extractor_multi_subject")
        logger.info("Initialized Enhanced ExtractorAgent with multi-subject processing")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multi-subject extraction logic.
        
        Args:
            data: Dictionary containing:
                - subject_nodes: List of {subject: str, nodes: List[Dict]}
                
        Returns:
            Dictionary with:
                - subject_actions: List of {subject: str, actions: List[Dict]}
        """
        subject_nodes = data.get("subject_nodes", [])
        
        if not subject_nodes:
            logger.warning("No subject nodes provided for extraction")
            return {"subject_actions": []}
        
        logger.info(f"=" * 80)
        logger.info(f"EXTRACTOR AGENT STARTING: Processing {len(subject_nodes)} subjects")
        logger.info(f"=" * 80)
        
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
            actions = self._process_subject(subject, nodes)
            
            # Optional: Consult Quality Agent
            if self.quality_agent and actions:
                try:
                    quality_result = self._check_quality(subject, actions)
                    if quality_result.get("needs_refinement", False):
                        logger.info(f"Quality check suggests refinement for subject '{subject}'")
                        # Could implement refinement logic here
                except Exception as e:
                    logger.debug(f"Quality check failed: {e}")
            
            subject_actions.append({
                "subject": subject,
                "actions": actions
            })
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SUBJECT '{subject}' COMPLETED: {len(actions)} actions extracted")
            logger.info(f"{'='*80}\n")
        
        total_actions = sum(len(sa["actions"]) for sa in subject_actions)
        logger.info(f"=" * 80)
        logger.info(f"EXTRACTOR AGENT COMPLETED")
        logger.info(f"Total actions: {total_actions} across {len(subject_actions)} subjects")
        logger.info(f"=" * 80)
        
        return {"subject_actions": subject_actions}
    
    def _process_subject(self, subject: str, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process all nodes for a single subject.
        
        Args:
            subject: Subject name
            nodes: List of nodes with metadata
            
        Returns:
            List of extracted actions for this subject
        """
        if not nodes:
            logger.warning(f"No nodes provided for subject: {subject}")
            return []
        
        logger.info(f"Processing {len(nodes)} nodes for subject '{subject}'")
        
        actions = []
        
        for idx, node in enumerate(nodes, 1):
            node_id = node.get('id', 'Unknown')
            node_title = node.get('title', 'Unknown')
            logger.info(f"Processing node {idx}/{len(nodes)}: {node_id} ({node_title})")
            
            node_actions = self._extract_from_node(subject, node)
            if node_actions:
                logger.info(f"  → Extracted {len(node_actions)} actions from this node")
                actions.extend(node_actions)
            else:
                logger.info(f"  → No actions extracted from this node")
        
        logger.info(f"Total raw actions extracted for subject '{subject}': {len(actions)}")
        
        # Deduplicate and refine actions
        refined_actions = self._refine_actions(subject, actions)
        
        logger.info(f"After refinement for subject '{subject}': {len(refined_actions)} unique actions")
        
        return refined_actions
    
    def _extract_from_node(self, subject: str, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract actions from a single node.
        
        Reads complete content using line numbers and extracts in who/when/what format.
        Automatically segments long content and processes with memory.
        
        Args:
            subject: Subject name
            node: Node metadata with id, start_line, end_line
            
        Returns:
            List of actions from this node
        """
        node_id = node.get('id')
        node_title = node.get('title', 'Unknown')
        start_line = node.get('start_line')
        end_line = node.get('end_line')
        
        logger.debug(f"Starting extraction from node {node_id} ({node_title})")
        
        if not all([node_id, start_line is not None, end_line is not None]):
            logger.warning(f"Missing required metadata for node: {node_id} - id:{node_id}, start_line:{start_line}, end_line:{end_line}")
            return []
        
        # Read complete content from original file
        logger.debug(f"Reading content for node {node_id}...")
        content = self._read_full_content(node)
        
        if not content:
            logger.warning(f"No content retrieved for node {node_id} ({node_title})")
            return []
        
        logger.debug(f"Content retrieved for node {node_id}, length: {len(content)} characters")
        
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
        
        if actions:
            logger.info(f"Successfully extracted {len(actions)} actions from node {node_id}")
        else:
            logger.warning(f"No actions extracted from node {node_id} ({node_title})")
        
        return actions
    
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
        
        # Validate required metadata
        if not node_id:
            logger.warning("Node missing 'id' field")
            return ""
        
        if start_line is None or end_line is None:
            logger.warning(f"Node {node_id} missing line range information")
            return ""
        
        # Try to get source path from node first
        source_path = node.get('source')
        
        # If not in node, query graph to get document source by traversing relationships
        if not source_path:
            logger.debug(f"Source path not in node metadata for {node_id}, querying graph...")
            
            # Query graph to get document source by following relationships from node
            source_path = self._get_document_source_from_node(node_id)
            
            if not source_path:
                logger.error(f"Could not find source path for node: {node_id}")
                return ""
        
        # Read content directly from file using line numbers
        try:
            logger.debug(f"Reading content from {source_path} lines {start_line}-{end_line}")
            content = DocumentParser.get_content_by_lines(source_path, start_line, end_line)
            
            if content:
                logger.debug(f"Successfully read {len(content)} characters for node {node_id}")
            else:
                logger.warning(f"No content retrieved for node {node_id}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error reading content for node {node_id} from {source_path}: {e}")
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
            logger.debug(f"Sending extraction request to LLM for node {node_id}")
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            logger.debug(f"LLM response type: {type(result)}")
            
            if isinstance(result, dict) and "actions" in result:
                actions = result["actions"]
                logger.info(f"Extracted {len(actions)} actions from node {node_id}")
                
                # Add full_context field
                for action in actions:
                    action['full_context'] = content[:500]  # First 500 chars as context
                    action['subject'] = subject
                
                return actions
            elif isinstance(result, list):
                # If LLM returned list directly
                logger.info(f"Extracted {len(result)} actions from node {node_id} (list format)")
                for action in result:
                    action['full_context'] = content[:500]
                    action['subject'] = subject
                return result
            else:
                logger.warning(f"Unexpected extraction result format for node {node_id}: {type(result)}")
                logger.debug(f"Result content: {str(result)[:200]}")
                return []
                
        except Exception as e:
            logger.error(f"Error in LLM extraction for node {node_id}: {e}", exc_info=True)
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
    
    def _refine_actions(self, subject: str, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Refine and deduplicate actions for a subject.
        
        Args:
            subject: Subject name
            actions: Raw extracted actions
            
        Returns:
            Refined and deduplicated actions
        """
        if not actions:
            return []
        
        # Simple deduplication based on action text similarity
        unique_actions = []
        seen_actions = set()
        
        for action in actions:
            action_text = action.get('action', '').lower().strip()
            
            # Simple deduplication check
            if action_text and action_text not in seen_actions:
                seen_actions.add(action_text)
                unique_actions.append(action)
        
        logger.debug(f"Refined {len(actions)} actions to {len(unique_actions)} unique actions for subject '{subject}'")
        
        return unique_actions
    
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
