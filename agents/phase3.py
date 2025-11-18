"""phase3 Agent: Deep Analysis with Graph Traversal."""

import logging
from typing import Dict, Any, List
from rag_tools.graph_rag import GraphRAG

logger = logging.getLogger(__name__)


class Phase3Agent:
    """
    Deep Analysis Agent with graph traversal for child expansion.
    
    Workflow:
    1. Receive node IDs from Analyzer Phase 2
    2. Expand nodes by adding their children (subsections)
    3. Consolidate and deduplicate results
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        hybrid_rag,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize phase3 Agent.
        
        Args:
            agent_name: Name of this agent (kept for compatibility)
            dynamic_settings: DynamicSettingsManager (kept for compatibility)
            hybrid_rag: Unified hybrid RAG tool (kept for compatibility, not used)
            graph_rag: Graph RAG for navigation
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        
        logger.info(f"Initialized Phase3Agent with agent_name='{agent_name}'")

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
        
        # 2. Expand node set using graph traversal
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
        Expand node set using graph traversal with child expansion.
        
        Strategy:
        1. For each initial node, get all children (subsections)
        2. Add children to expand coverage of selected topics
        3. Use consolidation to avoid duplicates
        
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
            
            # Get children and add them
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

