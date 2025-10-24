"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """
    Analyzer agent with 2-phase workflow:
    - Phase 1: Context Building (understand document structure)
    - Phase 2: Subject Identification (determine specific subjects for deep analysis)
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            llm_client: Ollama client instance
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info("Initialized AnalyzerAgent with 2-phase workflow")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute 2-phase analyzer workflow.
        
        Args:
            context: Context from orchestrator with:
                - problem_statement: Focused problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: List of all document summaries
                - refined_queries: List of refined Graph RAG queries  
                - node_ids: List of relevant node IDs from Phase 2
        """
        problem_statement = context.get("problem_statement", "")
        
        if not problem_statement:
            logger.error("No problem statement provided to Analyzer")
            raise ValueError("problem_statement is required")
        
        logger.info(f"Analyzer Phase 1: Document Discovery and Query Refinement")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 1: Document Discovery", 
                {"problem_statement": problem_statement}
            )
        
        # Phase 1: Context Building & Query Refinement
        phase1_output = self.phase1_context_building(problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", [])}
            )
        
        # Phase 2: Action Extraction (Node ID collection)
        node_ids = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            problem_statement
        )
        
        logger.info(f"Analyzer extracted {len(node_ids)} node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze combined information with LLM
        5. Generate refined set of specific Graph RAG queries
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
        """
        # Step 1: Get ALL document nodes for global context
        logger.info("Step 1: Retrieving all document summaries for global context")
        all_documents = self.graph_rag.get_all_document_nodes()
        
        if not all_documents:
            logger.warning("No documents found in knowledge graph")
            return {
                "all_documents": [],
                "initial_rag_results": [],
                "refined_queries": []
            }
        
        logger.info(f"Retrieved {len(all_documents)} document summaries")
        
        # Step 2: Generate focused initial query from problem statement
        logger.info("Step 2: Generating focused initial query from problem statement")
        initial_query = self._generate_initial_query(problem_statement, all_documents)
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Generated Initial Query for Introduction Nodes",
                {"initial_query": initial_query}
            )
        
        # Step 3: Query introduction-level nodes with the focused query
        logger.info("Step 3: Querying introduction-level nodes with focused query")
        intro_nodes = self.graph_rag.query_introduction_nodes(
            initial_query,
            top_k=self.settings.analyzer_d_initial_top_k
        )
        
        logger.info(f"Found {len(intro_nodes)} introduction nodes")
        
        # Step 4: Use LLM to analyze and generate refined queries
        logger.info("Step 4: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries
        }
    
    def _generate_initial_query(
        self,
        problem_statement: str,
        all_documents: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a focused initial query from the problem statement.
        
        This method extracts key concepts and generates a concise, targeted query
        for the initial introduction-level node search, instead of using the entire
        (potentially lengthy) problem statement.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            all_documents: All document summaries for context
            
        Returns:
            Focused query string for initial RAG search
        """
        # Prepare document context (abbreviated)
        doc_list = ", ".join([doc['name'] for doc in all_documents[:10]])
        
        prompt = f"""Based on the following problem statement, generate a focused, concise search query (3-10 keywords) that will help find relevant introduction-level sections in the knowledge base.

**Problem Statement:**
{problem_statement}

**Available Documents:**
{doc_list}

**Your Task:**
Extract the core concepts and generate a focused search query. The query should:
1. Be concise (3-10 key terms or a short phrase)
2. Focus on the main subject and context
3. Be suitable for finding introduction-level sections
4. Avoid overly specific details that would be better for deeper searches

**Output Format:**
Return a JSON object with the query string:
{{
  "query": "your focused search query here"
}}

Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert at extracting key concepts and generating focused search queries for health emergency planning documents.",
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "query" in result:
                query = str(result["query"]).strip()
                if query:
                    logger.info(f"Generated initial query: {query}")
                    return query
            
            logger.warning("Unexpected LLM result format for initial query, using fallback")
        except Exception as e:
            logger.error(f"Error generating initial query: {e}")
        
        # Fallback: Extract first few significant words from problem statement
        words = problem_statement.split()
        # Filter out common words and take first 8 significant words
        significant_words = [w for w in words if len(w) > 4][:8]
        fallback_query = " ".join(significant_words)
        logger.info(f"Using fallback initial query: {fallback_query}")
        return fallback_query
    
    def _generate_refined_queries(
        self,
        all_documents: List[Dict[str, Any]],
        intro_nodes: List[Dict[str, Any]],
        problem_statement: str
    ) -> List[str]:
        """
        Use LLM to generate refined Graph RAG queries.
        
        Args:
            all_documents: All document summaries
            intro_nodes: Initial RAG results from introduction nodes
            problem_statement: Original problem statement
            
        Returns:
            List of refined query strings
        """
        # Prepare context for LLM
        doc_context = "\n".join([
            f"- {doc['name']}: {(doc.get('summary') or 'No summary')[:200]}"
            for doc in all_documents[:20]  # Limit to top 20 for token efficiency
        ])
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = f"""Based on the problem statement and available document context, generate 3-5 specific, targeted queries for deeper document analysis.

**Problem Statement:**
{problem_statement}

**Available Documents (Global Context):**
{doc_context}

**Initial Findings (Introduction-Level Nodes):**
{intro_context}

**Your Task:**
Generate 3-5 specific queries that will help find actionable recommendations and protocols for this problem. Each query should:
1. Be focused and specific (not too broad)
2. Target concrete actions, procedures, or protocols
3. Align with the available document structure
4. Help identify nodes containing implementable guidance

**Output Format:**
Return a JSON object with a list of query strings:
{{
  "queries": [
    "query 1 focusing on specific aspect",
    "query 2 focusing on another aspect",
    ...
  ]
}}

Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                temperature=0.3
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.3)
            
            if isinstance(result, dict) and "queries" in result:
                queries = result["queries"]
                if isinstance(queries, list) and len(queries) > 0:
                    logger.info(f"Generated {len(queries)} refined queries")
                    return [str(q) for q in queries if q]
            
            logger.warning("Unexpected LLM result format, using fallback")
            return [problem_statement]  # Fallback to problem statement
            
        except Exception as e:
            logger.error(f"Error generating refined queries: {e}")
            return [problem_statement]  # Fallback
    
    def phase2_action_extraction(
        self,
        refined_queries: List[str],
        problem_statement: str
    ) -> List[str]:
        """
        Phase 2: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Execute each refined query against Graph RAG
        2. Examine summaries of returned nodes
        3. Use LLM to identify nodes containing actionable recommendations
        4. Handle batch processing if results exceed threshold
        5. Return cumulative list of node IDs
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            
        Returns:
            List of relevant node IDs
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return []
        
        all_node_ids = []
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        # Execute each refined query
        for idx, query in enumerate(refined_queries, 1):
            logger.info(f"Executing refined query {idx}/{len(refined_queries)}: {query[:100]}...")
            
            # Query graph using hybrid RAG
            try:
                results = self.unified_rag.query(
                    query,
                    strategy="hybrid",
                    top_k=self.settings.top_k_results * 2  # Get more results for filtering
                )
                
                logger.info(f"Query returned {len(results)} results")
                
                # Extract nodes from results
                nodes = []
                for result in results:
                    metadata = result.get('metadata', {})
                    node_id = metadata.get('node_id')
                    if node_id:
                        nodes.append({
                            'id': node_id,
                            'title': metadata.get('title', 'Unknown'),
                            'summary': result.get('text', '')[:500],  # Limit summary length
                            'score': result.get('score', 0.0)
                        })
                
                # Process nodes (with batching if needed)
                if len(nodes) > batch_threshold:
                    logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                    relevant_ids = self._process_nodes_in_batches(
                        nodes,
                        problem_statement,
                        batch_size
                    )
                else:
                    relevant_ids = self._identify_relevant_nodes(
                        nodes,
                        problem_statement
                    )
                
                all_node_ids.extend(relevant_ids)
                logger.info(f"Query {idx} yielded {len(relevant_ids)} relevant node IDs")
                
            except Exception as e:
                logger.error(f"Error executing query {idx}: {e}")
                continue
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            
        Returns:
            List of relevant node IDs
        """
        if not nodes:
            return []
        
        # Prepare node summaries for LLM
        node_context = "\n\n".join([
            f"Node ID: {node['id']}\n"
            f"Title: {node.get('title', 'Untitled')}\n"
            f"Summary: {(node.get('summary') or 'No summary')[:300]}"
            for node in nodes[:30]  # Limit to avoid token overflow
        ])
        
        prompt = f"""Analyze the following document nodes and identify which ones contain **actionable recommendations** relevant to the problem statement.

**Problem Statement:**
{problem_statement}

**Document Nodes:**
{node_context}

**Your Task:**
Identify node IDs that contain:
- Concrete actions, procedures, or protocols
- Implementation guidance
- Specific steps or checklists
- Operational recommendations

**Output Format:**
Return a JSON object with a list of relevant node IDs:
{{
  "relevant_node_ids": ["node_id_1", "node_id_2", ...]
}}

Respond with valid JSON only."""

        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert at identifying actionable content in health policy documents.",
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "relevant_node_ids" in result:
                node_ids = result["relevant_node_ids"]
                if isinstance(node_ids, list):
                    return [str(nid) for nid in node_ids if nid]
            
            logger.warning("Unexpected LLM result format")
            # Fallback: return top-scored nodes
            return [node['id'] for node in nodes[:5]]
            
        except Exception as e:
            logger.error(f"Error identifying relevant nodes: {e}")
            return [node['id'] for node in nodes[:5]]  # Fallback
    
    def _process_nodes_in_batches(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        batch_size: int
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
