"""phase3 Agent: Deep Analysis with LLM-based Graph Traversal and Scoring."""

import logging
import json
from typing import Dict, Any, List, Set
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class Phase3Agent:
    """
    Deep Analysis Agent with sophisticated hybrid RAG and graph traversal.
    
    Workflow:
    1. Initial Node Selection: Query RAG, navigate upward, consolidate branches
    2. Branch Traversal & Scoring: LLM-based recursive scoring with threshold-based traversal
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize phase3 Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for navigation
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.hybrid_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        
        # Configuration
        self.score_threshold = getattr(self.settings, 'phase3_score_threshold', 0.5)
        self.max_depth = getattr(self.settings, 'phase3_max_depth', 3)
        self.initial_top_k = getattr(self.settings, 'phase3_initial_top_k', 10)
        self.min_nodes_per_subject = getattr(self.settings, 'phase3_min_nodes_per_subject', 3)
        
        logger.info(
            f"Initialized Phase3Agent with agent_name='{agent_name}', model={self.llm.model}, "
            f"threshold={self.score_threshold}, max_depth={self.max_depth}"
        )

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute deep analysis workflow using graph traversal.

        Args:
            context: Context with:
                - node_ids: List of node IDs from Analyzer Phase 2

        Returns:
            Dictionary with:
                - nodes: List[Dict] with complete metadata (id, title, start_line, end_line, source)
        """
        node_ids = context.get("node_ids", [])
        
        if not node_ids:
            logger.warning("No node IDs provided for deep analysis")
            return {"nodes": []}
            
        logger.info(f"Phase3 starting deep analysis with {len(node_ids)} initial node IDs")
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase3 Deep Analysis Start",
                {"initial_node_ids": len(node_ids), "sample_ids": node_ids[:5]}
            )
            
        # 1. Fetch initial nodes with complete metadata
        initial_nodes = self.fetch_nodes_with_metadata(node_ids)
        
        if not initial_nodes:
            logger.warning("No valid nodes found for provided IDs")
            return {"nodes": []}
        
        logger.info(f"Fetched {len(initial_nodes)} valid nodes with metadata")
        
        # 2. Expand node set using graph traversal with LLM scoring
        expanded_nodes = self.expand_via_graph_traversal(initial_nodes)
        
        # 3. Deduplicate and consolidate
        final_nodes = self.graph_rag.consolidate_branches(expanded_nodes)
        
        logger.info(f"Phase3 complete: {len(final_nodes)} nodes after expansion and deduplication")
        
        # Log to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase3 Analysis Complete",
                {
                    "initial_nodes": len(initial_nodes),
                    "expanded_nodes": len(expanded_nodes),
                    "final_unique_nodes": len(final_nodes),
                    "sample_node_titles": [n.get('title', 'Unknown') for n in final_nodes[:5]]
                }
            )
            
        return {"nodes": final_nodes}

    def fetch_nodes_with_metadata(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch nodes from Neo4j with complete metadata using ONLY graph queries.
        
        Args:
            node_ids: List of node IDs from Analyzer
            
        Returns:
            List of nodes with complete metadata: id, title, start_line, end_line, source
        """
        logger.info(f"Fetching metadata for {len(node_ids)} nodes via graph traversal")
        
        nodes_with_metadata = []
        
        for node_id in node_ids:
            try:
                # Query Neo4j directly to get node with metadata and document source
                query = """
                MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: $node_id})
                RETURN h.id as id, h.title as title, h.summary as summary,
                       h.start_line as start_line, h.end_line as end_line,
                       doc.source as source, doc.name as doc_name
                LIMIT 1
                """
                
                with self.graph_rag.driver.session() as session:
                    result = session.run(query, node_id=node_id)
                    record = result.single()
                    
                    if record:
                        node = {
                            'id': record['id'],
                            'title': record['title'],
                            'summary': record.get('summary', ''),
                            'start_line': record['start_line'],
                            'end_line': record['end_line'],
                            'source': record['source'],
                            'doc_name': record['doc_name']
                        }
                        nodes_with_metadata.append(node)
                        logger.debug(f"✓ Fetched node {node_id}: {node['title']} (lines {node['start_line']}-{node['end_line']})")
                    else:
                        logger.warning(f"✗ Node {node_id} not found in graph")
                        
            except Exception as e:
                logger.error(f"Error fetching node {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched {len(nodes_with_metadata)} nodes with complete metadata")
        return nodes_with_metadata
    
    def expand_via_graph_traversal(self, initial_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Expand node set using graph traversal with LLM-based relevance scoring.
        
        Strategy:
        1. For each initial node, navigate upward to get parent context
        2. Score relevance of parent and siblings using LLM
        3. Recursively expand children of high-scoring nodes
        4. Use consolidation to avoid duplicates
        
        Args:
            initial_nodes: Nodes with complete metadata
            
        Returns:
            Expanded list of relevant nodes
        """
        logger.info(f"Expanding {len(initial_nodes)} initial nodes via graph traversal")
        
        all_relevant_nodes = []
        visited = set()
        
        # Add initial nodes to result
        for node in initial_nodes:
            node_id = node.get('id')
            if node_id:
                visited.add(node_id)
                all_relevant_nodes.append(node)
        
        # Process each initial node
        for idx, node in enumerate(initial_nodes, 1):
            node_id = node.get('id')
            node_title = node.get('title', 'Unknown')
            
            logger.info(f"[{idx}/{len(initial_nodes)}] Expanding node: {node_title}")
            
            # Navigate upward to get parent context
            parent_nodes = self.graph_rag.navigate_upward(node_id, levels=1)
            
            if parent_nodes:
                logger.debug(f"  Found {len(parent_nodes)} parent(s)")
                # Fetch complete metadata for parents
                parent_ids = [p.get('id') for p in parent_nodes if p.get('id')]
                parents_with_metadata = self.fetch_nodes_with_metadata(parent_ids)
                
                # Add relevant parents (score implicitly high since they're parents of selected nodes)
                for parent in parents_with_metadata:
                    parent_id = parent.get('id')
                    if parent_id not in visited:
                        visited.add(parent_id)
                        all_relevant_nodes.append(parent)
                        logger.debug(f"  + Added parent: {parent.get('title', 'Unknown')}")
            
            # Get children and score them
            children = self.graph_rag.get_children(node_id)
            
            if children:
                logger.debug(f"  Found {len(children)} children")
                # Fetch complete metadata for children
                child_ids = [c.get('id') for c in children if c.get('id')]
                children_with_metadata = self.fetch_nodes_with_metadata(child_ids)
                
                # Add children (they're subsections of selected nodes, so include them)
                for child in children_with_metadata:
                    child_id = child.get('id')
                    if child_id not in visited:
                        visited.add(child_id)
                        all_relevant_nodes.append(child)
                        logger.debug(f"  + Added child: {child.get('title', 'Unknown')}")
        
        logger.info(f"Expansion complete: {len(all_relevant_nodes)} total nodes (from {len(initial_nodes)} initial)")
        
        return all_relevant_nodes
    
    # ========================================================================
    # DEPRECATED METHODS (kept for backward compatibility, but not used)
    # ========================================================================
    
    def initial_node_selection_deprecated(self, subject: str) -> List[Dict[str, Any]]:
        """
        Step 1: Initial Node Selection.
        
        Process:
        1. Query RAG using subject-specific summary
        2. Get top-k nodes
        3. For each node: navigate 2 levels up (node → parent → grandparent)
        4. SELECT the parent node (1 level up)
        5. Consolidate branches with shared parents
        
        Args:
            subject: Specific subject to query
            
        Returns:
            Deduplicated parent nodes
        """
        logger.debug(f"Initial node selection for: {subject}")
        
        # Step 1-2: Query RAG for initial nodes
        try:
            initial_results = self.hybrid_rag.query(
                query_text=subject,
                strategy="automatic",
                top_k=self.initial_top_k
            )
        except Exception as e:
            logger.error(f"Error querying hybrid RAG: {e}")
            return []
        
        if not initial_results:
            logger.warning(f"No initial results for subject: {subject}")
            return []
        
        logger.debug(f"Retrieved {len(initial_results)} initial nodes")
        
        # Step 3-4: Navigate upward and select parent nodes
        parent_nodes = []
        
        for result in initial_results:
            # Extract node_id from metadata
            metadata = result.get('metadata', {})
            node_id = metadata.get('node_id')
            
            if not node_id:
                logger.debug("Skipping result without node_id")
                continue
            
            # Navigate 2 levels up
            try:
                # First, get the node itself to ensure it exists
                current_node = self.graph_rag.get_node_by_id(node_id)
                
                if not current_node:
                    logger.debug(f"Node {node_id} not found in graph")
                    continue
                
                # Navigate 1 level up to get parent
                parents_1_level = self.graph_rag.navigate_upward(node_id, levels=1)
                
                if parents_1_level:
                    # Add parent node (1 level up)
                    parent_nodes.extend(parents_1_level)
                else:
                    # If no parent (top-level node), use the node itself
                    parent_nodes.append(current_node)
                    
            except Exception as e:
                logger.debug(f"Error navigating from node {node_id}: {e}")
                continue
        
        # Step 5: Consolidate branches
        consolidated_nodes = self.graph_rag.consolidate_branches(parent_nodes)
        
        logger.debug(f"Initial selection: {len(consolidated_nodes)} consolidated parent nodes")
        return consolidated_nodes
    
    def branch_traversal_scoring_deprecated(
        self,
        parent_nodes: List[Dict[str, Any]],
        subject: str,
        current_depth: int = 0,
        visited: Set[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Step 2: Branch Traversal and Scoring with LLM-based relevance.
        
        Process:
        1. Score each parent node using LLM (0-1 scale)
        2. For nodes with score > threshold:
           - Get children nodes
           - Recursively score children (up to max_depth)
        3. Build final list of high-relevance nodes
        
        Args:
            parent_nodes: List of parent nodes to score
            subject: Subject for relevance scoring
            current_depth: Current recursion depth
            visited: Set of visited node IDs to avoid cycles
            
        Returns:
            Comprehensive list of relevant nodes for this subject
        """
        if visited is None:
            visited = set()
        
        if current_depth >= self.max_depth:
            logger.debug(f"Reached max depth {self.max_depth}, stopping traversal")
            return []
        
        relevant_nodes = []
        
        for node in parent_nodes:
            node_id = node.get('id')
            
            if not node_id:
                continue
            
            # Avoid cycles
            if node_id in visited:
                logger.debug(f"Skipping already visited node: {node_id}")
                continue
            
            visited.add(node_id)
            
            # Score this node
            score = self.score_node_relevance_deprecated(node, subject)
            
            logger.debug(
                f"Node '{node.get('title', 'Unknown')}' (ID: {node_id}) "
                f"scored {score:.2f} for subject '{subject}'"
            )
            
            # If score exceeds threshold, add to relevant nodes
            if score >= self.score_threshold:
                # Add score to node metadata
                node_with_score = node.copy()
                node_with_score['relevance_score'] = score
                relevant_nodes.append(node_with_score)
                
                # Recursively traverse children
                children = self.graph_rag.get_children(node_id)
                
                if children:
                    logger.debug(f"Node {node_id} has {len(children)} children, recursing...")
                    child_relevant = self.branch_traversal_scoring_deprecated(
                        children,
                        subject,
                        current_depth + 1,
                        visited
                    )
                    relevant_nodes.extend(child_relevant)
            else:
                logger.debug(f"Node {node_id} below threshold ({score:.2f} < {self.score_threshold}), pruning branch")
        
        return relevant_nodes
    
    def apply_fallback_selection_deprecated(
        self,
        parent_nodes: List[Dict[str, Any]],
        subject: str,
        min_nodes: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback mechanism: Score all nodes and take top-K even if below threshold.
        
        Args:
            parent_nodes: List of parent nodes to score
            subject: Subject for relevance scoring
            min_nodes: Minimum number of nodes to return
            
        Returns:
            Top-K scored nodes (even if below threshold)
        """
        logger.info(f"Applying fallback selection to get at least {min_nodes} nodes")
        
        scored_nodes = []
        
        for node in parent_nodes:
            node_id = node.get('id')
            if not node_id:
                continue
            
            # Score this node
            score = self.score_node_relevance_deprecated(node, subject)
            
            # Add score to node
            node_with_score = node.copy()
            node_with_score['relevance_score'] = score
            scored_nodes.append(node_with_score)
            
            logger.debug(
                f"Fallback: Node '{node.get('title', 'Unknown')}' scored {score:.2f}"
            )
        
        # Sort by score (descending) and take top min_nodes
        scored_nodes.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        selected = scored_nodes[:min_nodes]
        
        # Format scores for logging
        scores_list = [f"{n.get('relevance_score', 0):.2f}" for n in selected]
        logger.info(
            f"Fallback selected {len(selected)} nodes with scores: {scores_list}"
        )
        
        return selected
    
    def score_node_relevance_deprecated(self, node: Dict[str, Any], subject: str) -> float:
        """
        Use LLM to score node relevance to subject on 0-1 scale.
        
        Args:
            node: Node dictionary with title and summary
            subject: Subject for relevance assessment
            
        Returns:
            Float score between 0.0 and 1.0
        """
        node_title = node.get('title', 'Unknown')
        node_summary = node.get('summary', '')
        
        # Get scoring prompt
        scoring_prompt = get_prompt("phase3_scoring")
        
        # Build complete prompt
        prompt = f"""{scoring_prompt}

Subject: {subject}

Node to Score:
Title: {node_title}
Summary: {node_summary[:500]}

On a scale from 0.0 to 1.0, rate how relevant this node is to the subject "{subject}".

Scoring guidelines:
- 0.0-0.3: Not relevant or tangentially related
- 0.4-0.6: Somewhat relevant, contains related information
- 0.7-0.9: Highly relevant, directly addresses the subject
- 1.0: Extremely relevant, core information for the subject

Respond with ONLY a JSON object:
{{
  "score": <float between 0.0 and 1.0>,
  "reasoning": "<brief explanation>"
}}

Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert at assessing document relevance for health policy analysis.",
                temperature=0.1  # Low temperature for consistent scoring
            )
            
            if isinstance(result, dict) and "score" in result:
                score = float(result["score"])
                # Clamp to 0-1 range
                score = max(0.0, min(1.0, score))
                
                reasoning = result.get("reasoning", "")
                logger.debug(f"Score: {score:.2f} - Reasoning: {reasoning}")
                
                return score
            else:
                logger.warning(f"Unexpected LLM scoring result format: {type(result)}")
                return 0.5  # Default middle score
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing score from LLM: {e}")
            return 0.5  # Default middle score
        except Exception as e:
            logger.error(f"Error in LLM scoring: {e}")
            return 0.5  # Default middle score

