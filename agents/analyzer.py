"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List, Tuple
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        initial_query, section_candidates = self._generate_initial_query(problem_statement, all_documents)
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Generated Initial Query for Introduction Nodes",
                {"initial_query": initial_query, "section_candidates": section_candidates}
            )
        
        # Step 2.5: Retrieve nodes for section candidates if any
        section_nodes = []
        if section_candidates:
            logger.info(f"Step 2.5: Retrieving nodes for {len(section_candidates)} section candidates")
            for candidate in section_candidates:
                if isinstance(candidate, list) and len(candidate) >= 2:
                    doc_name = str(candidate[0]).strip()
                    section_title = str(candidate[1]).strip()
                    try:
                        matching_nodes = self.graph_rag.find_nodes_by_section_title(doc_name, section_title)
                        if matching_nodes:
                            section_nodes.extend(matching_nodes)
                            logger.info(f"Found {len(matching_nodes)} nodes for '{section_title}' in '{doc_name}'")
                        else:
                            logger.warning(f"No nodes found for '{section_title}' in '{doc_name}'")
                    except Exception as e:
                        logger.warning(f"Error searching for section '{section_title}' in '{doc_name}': {e}")
                        continue
        
        # Step 3: Query introduction-level nodes with the focused query
        logger.info("Step 3: Querying introduction-level nodes with focused query")
        intro_nodes = self.graph_rag.query_introduction_nodes(
            initial_query,
            top_k=self.settings.analyzer_d_initial_top_k
        )
        
        logger.info(f"Found {len(intro_nodes)} introduction nodes from query")
        
        # Combine query results with section candidate nodes (deduplicate by node ID)
        if section_nodes:
            # Create a set of existing node IDs to avoid duplicates
            existing_node_ids = {node.get('id') for node in intro_nodes if node.get('id')}
            for section_node in section_nodes:
                node_id = section_node.get('id')
                if node_id and node_id not in existing_node_ids:
                    # Format section node to match intro_nodes structure
                    formatted_node = {
                        'id': section_node.get('id'),
                        'title': section_node.get('title', ''),
                        'summary': section_node.get('summary', ''),
                        'document_name': section_node.get('document_name', ''),
                        'source': section_node.get('source', ''),
                        'start_line': section_node.get('start_line'),
                        'end_line': section_node.get('end_line')
                    }
                    intro_nodes.append(formatted_node)
                    existing_node_ids.add(node_id)
            logger.info(f"Added {len(section_nodes)} section candidate nodes, total intro nodes: {len(intro_nodes)}")
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
        }
    
    def _generate_initial_query(
        self,
        problem_statement: str,
        all_documents: List[Dict[str, Any]]
    ) -> Tuple[str, List[List[str]]]:
        """
        Generate a focused initial query from the problem statement.
        
        This method extracts key concepts and generates a concise, targeted query
        for the initial introduction-level node search, instead of using the entire
        (potentially lengthy) problem statement.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            all_documents: All document summaries for context
            
        Returns:
            Tuple of (focused query string, list of intro_section_candidates)
            where each candidate is [document_name, section_name]
        """
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "query" in result:
                query = str(result["query"]).strip()
                if query:
                    logger.info(f"Generated initial query: {query}")
                    
                    # Extract intro_section_candidates if present
                    section_candidates = result.get("intro_section_candidates", [])
                    if section_candidates:
                        logger.info(f"Found {len(section_candidates)} section candidates from LLM")
                    return query, section_candidates
            
            logger.warning("Unexpected LLM result format for initial query, using fallback")
        except Exception as e:
            logger.error(f"Error generating initial query: {e}")
        
        # Fallback: Extract first few significant words from problem statement
        words = problem_statement.split()
        # Filter out common words and take first 8 significant words
        significant_words = [w for w in words if len(w) > 4][:8]
        fallback_query = " ".join(significant_words)
        logger.info(f"Using fallback initial query: {fallback_query}")
        return fallback_query, []
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)

        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List, Tuple
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from config.prompts import (
    get_prompt,
    get_analyzer_query_generation_prompt,
    get_analyzer_problem_statement_refinement_prompt,
    get_analyzer_refined_queries_prompt,
    get_analyzer_node_evaluation_prompt
)
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
        agent_name: str,
        dynamic_settings,
        hybrid_rag: HybridRAG,
        graph_rag: GraphRAG,
        markdown_logger=None
    ):
        """
        Initialize Analyzer Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (required)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.sample_lines = getattr(self.settings, 'analyzer_context_sample_lines', 10)
        logger.info(f"Initialized AnalyzerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
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
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Get refined problem statement from phase1 output (or use original if not refined)
        refined_problem_statement = phase1_output.get("problem_statement", problem_statement)
        
        logger.info(f"Analyzer Phase 2: Node ID Extraction")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2: Node ID Extraction",
                {"refined_queries": phase1_output.get("refined_queries", []),
                 "problem_statement": refined_problem_statement[:100] + "..." if len(refined_problem_statement) > 100 else refined_problem_statement}
            )
        
        # Phase 2 Step 1: Action Extraction (Node ID collection) - use refined problem statement
        phase = context.get("phase", "")
        level = context.get("level", "")
        node_ids, all_candidate_nodes = self.phase2_action_extraction(
            phase1_output.get("refined_queries", []),
            refined_problem_statement,
            phase,
            level
        )
        
        logger.info(f"Analyzer Phase 2 Step 1 extracted {len(node_ids)} node IDs")
        
        # Phase 2 Step 2: Sibling Expansion
        additional_node_ids = self.phase2_sibling_expansion(
            selected_node_ids=node_ids,
            all_candidate_nodes=all_candidate_nodes,
            problem_statement=refined_problem_statement,
            phase=phase,
            level=level
        )
        
        # Merge results and deduplicate
        if additional_node_ids:
            node_ids = list(set(node_ids + additional_node_ids))
            logger.info(f"After sibling expansion: {len(node_ids)} total node IDs (+{len(additional_node_ids)} from siblings)")
        else:
            logger.info(f"No additional nodes from sibling expansion")
        
        logger.info(f"Analyzer Phase 2 complete: {len(node_ids)} total node IDs")
        
        return {
            "all_documents": phase1_output.get("all_documents", []),
            "refined_queries": phase1_output.get("refined_queries", []),
            "node_ids": node_ids,
            "problem_statement": refined_problem_statement  # Return refined problem statement for workflow
        }
    
    def phase1_context_building(self, problem_statement: str) -> Dict[str, Any]:
        """
        Phase 1: Document discovery and query refinement.
        
        Steps:
        1. Get ALL parent Document nodes from graph (for global context)
        2. Generate a focused initial query from the problem statement (using LLM)
        3. Query introduction-level nodes using the focused query
        4. Analyze and refine problem statement if needed (using LLM with intro_context and TOC)
        5. Generate refined set of specific Graph RAG queries (using LLM with combined information)
        
        Args:
            problem_statement: Problem statement from Orchestrator
            
        Returns:
            Dictionary with:
                - all_documents: All document summaries for global context
                - initial_rag_results: Results from initial introduction query
                - refined_queries: LLM-generated specific queries for Phase 2
                - problem_statement: Refined problem statement (or original if not refined)
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
        
        # Step 4: Refine problem statement if needed
        logger.info("Step 4: Analyzing and refining problem statement if needed")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Step 4: Problem Statement Refinement Analysis",
                {"original_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement}
            )
        
        # Build intro_context for refinement
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        # Refine problem statement
        refined_problem_statement = self._refine_problem_statement(problem_statement, intro_context)
        
        if refined_problem_statement:
            logger.info("Problem statement was refined - using refined version for downstream steps")
            problem_statement = refined_problem_statement
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refined",
                    {
                        "refinement_status": "modified",
                        "refined_problem_statement": problem_statement[:200] + "..." if len(problem_statement) > 200 else problem_statement
                    }
                )
        else:
            logger.info("No modification needed for problem statement - using original")
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Problem Statement Refinement Complete",
                    {
                        "refinement_status": "no_modification_needed",
                        "original_problem_statement_retained": True
                    }
                )
        
        # Step 5: Use LLM to analyze and generate refined queries
        logger.info("Step 5: Generating refined queries using LLM")
        refined_queries = self._generate_refined_queries(
            all_documents,
            intro_nodes,
            problem_statement
        )
        
        return {
            "all_documents": all_documents,
            "initial_rag_results": intro_nodes,
            "refined_queries": refined_queries,
            "problem_statement": problem_statement  # Return the (potentially refined) problem statement
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        prompt = get_analyzer_query_generation_prompt(problem_statement, "", doc_toc)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
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
    
    def _refine_problem_statement(
        self,
        problem_statement: str,
        intro_context: str
    ) -> str:
        """
        Analyze and optionally refine the problem statement using LLM.
        
        Args:
            problem_statement: Original problem statement from Orchestrator
            intro_context: Initial findings from introduction-level nodes
            
        Returns:
            Refined problem statement if modification needed, empty string if no change,
            or original problem statement on error
        """
        prompt = get_analyzer_problem_statement_refinement_prompt(problem_statement, intro_context)
        
        schema = {
            "type": "object",
            "properties": {
                "modified_problem_statement": {
                    "type": "string"
                }
            },
            "required": ["modified_problem_statement"]
        }
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase1"),
                schema=schema,
                temperature=0.2
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
            
            if isinstance(result, dict) and "modified_problem_statement" in result:
                modified = result["modified_problem_statement"]
                
                # Validate and normalize the output
                if not modified or not isinstance(modified, str):
                    logger.info("LLM returned empty or invalid modified_problem_statement, using original")
                    return ""
                
                # Strip whitespace
                modified = modified.strip()
                
                # Check for explanatory text that should be normalized to empty string
                explanatory_phrases = [
                    "i don't have any modification",
                    "no modification",
                    "no changes",
                    "no change",
                    "no modification needed",
                    "no changes needed",
                    "i don't have",
                    "no modification is needed",
                    "no changes are needed"
                ]
                
                modified_lower = modified.lower()
                if not modified or any(phrase in modified_lower for phrase in explanatory_phrases):
                    logger.info("LLM indicated no modification needed, using original problem statement")
                    return ""
                
                # Return the refined problem statement
                logger.info("Problem statement was refined by LLM")
                return modified
            
            logger.warning("Unexpected LLM result format for problem statement refinement, using original")
            return ""
            
        except Exception as e:
            logger.error(f"Error refining problem statement: {e}")
            return ""  # Return empty string on error to use original
    
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
        # Retrieve TOC (direct children) for each document
        doc_toc_entries = []
        for doc in all_documents[:10]:  # Limit to top 10 for efficiency
            doc_name = doc.get('name')
            if doc_name:
                try:
                    toc_nodes = self.graph_rag.get_document_toc(doc_name)
                    if toc_nodes:
                        # Format each document's TOC with clear structure
                        toc_sections = []
                        for idx, node in enumerate(toc_nodes[:15], 1):  # Limit to 15 sections per doc
                            section_title = node.get('title', 'Untitled')
                            toc_sections.append(f"  {idx}. {section_title}")
                        
                        if toc_sections:
                            doc_entry = f"**{doc_name}**\n" + "\n".join(toc_sections)
                            doc_toc_entries.append(doc_entry)
                except Exception as e:
                    logger.warning(f"Error retrieving TOC for document {doc_name}: {e}")
                    continue
        
        # Join with double newlines for clear separation between documents
        doc_toc = "\n\n".join(doc_toc_entries) if doc_toc_entries else "No TOC information available."
        
        intro_context = "\n".join([
            f"- [{node.get('document_name', 'Unknown')}] {node.get('title', 'Untitled')}: {(node.get('summary') or '')[:150]}"
            for node in intro_nodes[:10]  # Limit to top 10
        ])
        
        prompt = get_analyzer_refined_queries_prompt(problem_statement, doc_toc, intro_context)
        
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
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Phase 2 Step 1: Execute refined queries and extract relevant node IDs.
        
        Process:
        1. Segment refined queries into batches of 6
        2. Execute each batch of queries against Graph RAG
        3. Examine summaries of returned nodes
        4. Use LLM to identify nodes containing actionable recommendations
        5. Handle batch processing if results exceed threshold
        6. Return cumulative list of node IDs and all candidate nodes
        
        Args:
            refined_queries: List of refined queries from Phase 1
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            Tuple of (selected node IDs, all candidate nodes examined)
        """
        if not refined_queries:
            logger.warning("No refined queries provided, cannot extract node IDs")
            return [], []
        
        all_node_ids = []
        all_candidate_nodes = []  # Track all nodes examined
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        query_segment_size = 6  # Process 6 queries at a time
        
        # Segment queries into batches of 6
        total_queries = len(refined_queries)
        num_segments = (total_queries + query_segment_size - 1) // query_segment_size
        
        logger.info(f"Phase 2 Step 1: Processing {total_queries} queries in {num_segments} segment(s) of {query_segment_size}")
        
        # Process each segment of queries
        for segment_idx in range(num_segments):
            start_idx = segment_idx * query_segment_size
            end_idx = min(start_idx + query_segment_size, total_queries)
            query_segment = refined_queries[start_idx:end_idx]
            
            logger.info(f"Processing query segment {segment_idx + 1}/{num_segments}: queries {start_idx + 1}-{end_idx} ({len(query_segment)} queries)")
            
            # Execute each refined query in this segment
            for local_idx, query in enumerate(query_segment, 1):
                global_idx = start_idx + local_idx
                logger.info(f"Executing refined query {global_idx}/{total_queries}: {query[:100]}...")
                
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
                            # Prioritize actual summary from metadata, fallback to text content
                            summary = metadata.get('summary', result.get('text', ''))
                            node_dict = {
                                'id': node_id,
                                'title': metadata.get('title', 'Unknown'),
                                'summary': summary[:5000] if summary else 'No summary',
                                'score': result.get('score', 0.0)
                            }
                            nodes.append(node_dict)
                            all_candidate_nodes.append(node_dict)  # Track all candidates
                    
                    # Process nodes (with batching if needed)
                    if len(nodes) > batch_threshold:
                        logger.info(f"Batch processing {len(nodes)} nodes in batches of {batch_size}")
                        relevant_ids = self._process_nodes_in_batches(
                            nodes,
                            problem_statement,
                            batch_size,
                            phase,
                            level
                        )
                    else:
                        relevant_ids = self._identify_relevant_nodes(
                            nodes,
                            problem_statement,
                            phase,
                            level
                        )
                    
                    all_node_ids.extend(relevant_ids)
                    logger.info(f"Query {global_idx} yielded {len(relevant_ids)} relevant node IDs")
                    
                except Exception as e:
                    logger.error(f"Error executing query {global_idx}: {e}")
                    continue
            
            logger.info(f"Query segment {segment_idx + 1}/{num_segments} complete")
        
        # Deduplicate node IDs
        unique_node_ids = list(set(all_node_ids))
        logger.info(f"Phase 2 Step 1 complete: {len(unique_node_ids)} unique node IDs (from {len(all_node_ids)} total)")
        
        return unique_node_ids, all_candidate_nodes
    
    def _identify_relevant_nodes(
        self,
        nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Use LLM to identify which nodes contain actionable recommendations.
        
        Args:
            nodes: List of node dictionaries with id, title, summary
            problem_statement: Context for relevance assessment
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = get_analyzer_node_evaluation_prompt(problem_statement, node_context, phase, level)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=get_prompt("analyzer_phase2"),
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
        batch_size: int,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Process large node sets in batches to avoid overwhelming the LLM.
        
        Args:
            nodes: List of all nodes to process
            problem_statement: Context for relevance
            batch_size: Number of nodes per batch
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of all relevant node IDs from all batches
        """
        all_relevant_ids = []
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
            
            try:
                relevant_ids = self._identify_relevant_nodes(batch, problem_statement, phase, level)
                all_relevant_ids.extend(relevant_ids)
            except Exception as e:
                logger.error(f"Error processing batch starting at {i}: {e}")
                continue
        
        return all_relevant_ids
    
    def phase2_sibling_expansion(
        self,
        selected_node_ids: List[str],
        all_candidate_nodes: List[Dict[str, Any]],
        problem_statement: str,
        phase: str = "",
        level: str = ""
    ) -> List[str]:
        """
        Phase 2 Step 2: Analyze same-parent siblings of selected nodes.
        
        Recovers potentially relevant nodes that weren't surfaced by RAG by examining
        siblings (same-parent, same-level nodes) of the nodes selected in Step 1.
        
        Process:
        1. Segment selected node IDs into batches of 6
        2. For each batch, navigate upward to find parents
        3. Get all children (siblings) of each parent
        4. Filter out already-analyzed nodes (selected + rejected)
        5. Fetch full content for unanalyzed siblings
        6. Analyze using same evaluation method as Step 1
        7. Return additional relevant node IDs
        
        Args:
            selected_node_ids: Node IDs selected in Phase 2 Step 1
            all_candidate_nodes: All nodes examined in Step 1 (for filtering)
            problem_statement: Original problem statement for context
            phase: Phase context for node evaluation
            level: Level context for node evaluation
            
        Returns:
            List of additional relevant node IDs from sibling analysis
        """
        if not selected_node_ids:
            logger.info("Phase 2 Step 2: No selected nodes, skipping sibling expansion")
            return []
        
        logger.info(f"Phase 2 Step 2: Starting sibling expansion for {len(selected_node_ids)} selected nodes")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Phase 2 Step 2: Sibling Expansion",
                {"selected_nodes_count": len(selected_node_ids)}
            )
        
        # Create sets for efficient filtering
        selected_set = set(selected_node_ids)
        all_candidate_ids = {node['id'] for node in all_candidate_nodes if 'id' in node}
        rejected_set = all_candidate_ids - selected_set
        
        logger.info(f"Filtering: {len(selected_set)} selected, {len(rejected_set)} rejected from Step 1")
        
        node_segment_size = 6  # Process 6 nodes at a time
        total_nodes = len(selected_node_ids)
        num_segments = (total_nodes + node_segment_size - 1) // node_segment_size
        
        logger.info(f"Phase 2 Step 2: Processing {total_nodes} selected nodes in {num_segments} segment(s) of {node_segment_size}")
        
        all_sibling_candidates = []
        seen_sibling_ids = set()
        
        # Process each segment of selected nodes
        for segment_idx in range(num_segments):
            start_idx = segment_idx * node_segment_size
            end_idx = min(start_idx + node_segment_size, total_nodes)
            node_segment = selected_node_ids[start_idx:end_idx]
            
            logger.info(f"Processing node segment {segment_idx + 1}/{num_segments}: nodes {start_idx + 1}-{end_idx} ({len(node_segment)} nodes)")
            
            # Track siblings found in this segment
            segment_sibling_count_before = len(all_sibling_candidates)
            
            # Find unique parents for this segment of nodes
            parent_node_map = {}  # parent_id -> parent metadata
            for node_id in node_segment:
                try:
                    parents = self.graph_rag.navigate_upward(node_id, levels=1)
                    for parent in parents:
                        parent_id = parent.get('id')
                        if parent_id:
                            parent_node_map[parent_id] = parent
                            logger.debug(f"Found parent '{parent.get('title', 'Unknown')}' for node {node_id}")
                except Exception as e:
                    logger.warning(f"Error navigating upward from node {node_id}: {e}")
                    continue
            
            logger.info(f"Segment {segment_idx + 1}: Found {len(parent_node_map)} unique parent nodes")
            
            # Gather siblings from these parents
            for parent_id, parent_info in parent_node_map.items():
                try:
                    children = self.graph_rag.get_children(parent_id)
                    logger.debug(f"Parent '{parent_info.get('title', 'Unknown')}' has {len(children)} children")
                    
                    for child in children:
                        child_id = child.get('id')
                        # Filter: exclude already selected, rejected, or already processed siblings
                        if child_id and child_id not in selected_set and child_id not in rejected_set and child_id not in seen_sibling_ids:
                            seen_sibling_ids.add(child_id)
                            all_sibling_candidates.append(child)
                            logger.debug(f"  + Sibling candidate: {child.get('title', 'Unknown')} ({child_id})")
                except Exception as e:
                    logger.warning(f"Error getting children for parent {parent_id}: {e}")
                    continue
            
            segment_sibling_count_after = len(all_sibling_candidates)
            new_siblings_in_segment = segment_sibling_count_after - segment_sibling_count_before
            logger.info(f"Segment {segment_idx + 1} complete: found {new_siblings_in_segment} new sibling candidates")
        
        logger.info(f"Found {len(all_sibling_candidates)} total unanalyzed sibling nodes to evaluate")
        
        if not all_sibling_candidates:
            logger.info("Phase 2 Step 2: No new sibling candidates found")
            return []
        
        # Fetch full content for each sibling
        sibling_nodes_with_content = []
        for sibling in all_sibling_candidates:
            node_id = sibling.get('id')
            source = sibling.get('source')
            start_line = sibling.get('start_line')
            end_line = sibling.get('end_line')
            
            if not all([node_id, source, start_line is not None, end_line is not None]):
                logger.warning(f"Sibling {node_id} missing required fields for content fetch")
                continue
            
            try:
                # Read full content like Phase 3 does
                content = self.graph_rag.read_node_content(
                    node_id=node_id,
                    file_path=source,
                    start_line=start_line,
                    end_line=end_line
                )
                
                if content:
                    sibling_nodes_with_content.append({
                        'id': node_id,
                        'title': sibling.get('title', 'Unknown'),
                        'summary': content,  # Use full content as summary for analysis
                        'score': 0.0  # No RAG score for siblings
                    })
                    logger.debug(f"Fetched content for sibling: {sibling.get('title', 'Unknown')} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Error reading content for sibling {node_id}: {e}")
                continue
        
        logger.info(f"Successfully fetched content for {len(sibling_nodes_with_content)} siblings")
        
        if not sibling_nodes_with_content:
            logger.info("Phase 2 Step 2: No sibling content available for analysis")
            return []
        
        # Analyze siblings using same method as Step 1
        batch_threshold = self.settings.analyzer_phase2_batch_threshold
        batch_size = self.settings.analyzer_phase2_batch_size
        
        try:
            if len(sibling_nodes_with_content) > batch_threshold:
                logger.info(f"Batch processing {len(sibling_nodes_with_content)} siblings in batches of {batch_size}")
                relevant_sibling_ids = self._process_nodes_in_batches(
                    sibling_nodes_with_content,
                    problem_statement,
                    batch_size,
                    phase,
                    level
                )
            else:
                relevant_sibling_ids = self._identify_relevant_nodes(
                    sibling_nodes_with_content,
                    problem_statement,
                    phase,
                    level
                )
            
            logger.info(f"Phase 2 Step 2 complete: {len(relevant_sibling_ids)} additional relevant nodes from siblings")
            
            if self.markdown_logger:
                self.markdown_logger.log_processing_step(
                    "Phase 2 Step 2: Results",
                    {
                        "siblings_analyzed": len(sibling_nodes_with_content),
                        "additional_relevant": len(relevant_sibling_ids)
                    }
                )
            
            return relevant_sibling_ids
            
        except Exception as e:
            logger.error(f"Error analyzing sibling nodes: {e}")
            return []

