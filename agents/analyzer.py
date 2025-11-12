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
        
        prompt = f"""You are a search query optimization specialist. Your task is to transform a problem statement into a high-precision search query for retrieving relevant introduction-level documents.

## Problem Statement
{problem_statement}

## Available Document Collection
{doc_list}

## Query Generation Guidelines

**Objective:** Create a search query that maximizes precision while maintaining sufficient recall for introduction-level content.

**Query Composition Strategy:**
1. **Extract Core Concepts** (3-5 terms)
   - Identify the PRIMARY subject domain (e.g., "emergency logistics", "triage systems", "supply chain")
   - Include the operational context (e.g., "mass casualty", "urban warfare", "disaster response")
   - Add specificity markers if present (e.g., "protocol", "framework", "planning")

2. **Prioritize Distinctive Terms**
   - Select terms that are SPECIFIC to the problem domain
   - Avoid generic administrative terms (e.g., "management", "system", "implementation")
   - Include technical terminology when present
   - Prefer compound concepts over single words (e.g., "resource allocation" over "resources")

3. **Optimize for Introduction-Level Retrieval**
   - Focus on high-level concepts rather than detailed procedures
   - Include terms likely to appear in document titles, executive summaries, and overview sections
   - Balance breadth (to find all relevant docs) with precision (to avoid irrelevant matches)

4. **Contextual Adaptation**
   - If problem mentions specific frameworks/standards, include them
   - If problem specifies organizational level (ministry/facility/etc), consider including it
   - If problem mentions phases (preparedness/response/recovery), include the primary phase

**Quality Criteria:**
- ✓ Query length: 3-10 terms (optimal: 5-7)
- ✓ Distinctiveness: Each term adds meaningful specificity
- ✓ Relevance: All terms directly relate to the problem's core domain
- ✗ Avoid: Action verbs (identify, develop, implement, establish)
- ✗ Avoid: Generic qualifiers (effective, comprehensive, systematic)
- ✗ Avoid: Overly narrow technical details

**Output Format:**
Return a JSON object with a single, optimized query string:
{{
  "query": "domain-specific term 1 operational context term 2 specificity marker"
}}

**Example Transformations:**
- "Develop a protocol for emergency triage in mass casualty events" → "emergency triage mass casualty protocol"
- "Implement supply chain management during urban warfare" → "supply chain urban warfare logistics disaster"
- "Establish coordination mechanisms for multi-agency response" → "multi-agency coordination emergency response mechanisms"

Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are a search optimization expert specializing in information retrieval for policy and operational planning domains. You excel at distilling complex problems into precise, high-recall search queries while filtering noise and generic terminology.",
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
        
        prompt = f"""You are a strategic query designer for document retrieval systems. Your task is to generate multiple targeted queries that decompose a complex problem into retrievable, actionable knowledge components.

## Problem Statement
{problem_statement}

## Available Knowledge Base
**Document Collection:**
{doc_context}

**Initial Findings (Introduction-Level Context):**
{intro_context}

## Query Generation Strategy

**Objective:** Create 3-5 complementary queries that collectively cover all actionable dimensions of the problem while maintaining high retrieval precision.

### Step 1: Decompose the Problem
Analyze the problem statement to identify:
- **Primary operational needs** (what must be done)
- **Key decision points** (what must be determined)
- **Resource/capability requirements** (what is needed)
- **Process/procedure gaps** (how to execute)
- **Stakeholder/organizational considerations** (who is involved)

### Step 2: Map to Document Content
Based on the available documents and initial findings:
- Identify which documents likely contain guidance for each dimension
- Note document structure patterns (sections, protocols, frameworks, checklists)
- Consider terminology used in the document titles

### Step 3: Design Complementary Queries
Generate 3-5 queries following these principles:

**Query Design Rules:**
1. **Specificity**: Each query targets a distinct operational dimension
   - ✓ "resource allocation protocols emergency triage mass casualty"
   - ✗ "emergency management procedures"

2. **Actionability Focus**: Prioritize terms indicating implementable content
   - Include: "protocol", "procedure", "framework", "checklist", "guideline", "criteria", "steps"
   - Avoid: "overview", "introduction", "background", "theory"

3. **Document Alignment**: Reference specific document names when relevant
   - ✓ "supply chain protocols urban warfare logistics guideline"
   - ✓ "incident command communication architecture emergency operations"

4. **Non-Redundancy**: Each query explores a different aspect
   - Query 1 might focus on decision frameworks
   - Query 2 might focus on resource allocation
   - Query 3 might focus on coordination mechanisms
   - Query 4 might focus on training/competencies
   - Query 5 might focus on data/reporting systems

5. **Precision over Breadth**: Target 10-15 highly relevant results rather than 100 mixed results
   - Use specific compound terms: "multi-agency coordination protocols"
   - Combine domain + context + artifact type: "triage criteria mass casualty emergency"

**Coverage Requirements:**
- Collectively cover all critical operational dimensions from Step 1
- Each query should retrieve different but complementary content
- Prioritize queries for the most critical operational gaps

### Step 4: Optimize Query Language
For each query:
- Use terminology from the document collection
- Combine domain-specific technical terms
- Include 5-10 words per query (optimal: 6-8)
- Balance specificity with retrievability

**Output Format:**
Return a JSON object with 3-5 optimized queries:
{{
  "queries": [
    "specific operational dimension 1 with domain terms and artifact type",
    "specific operational dimension 2 with domain terms and artifact type",
    "specific operational dimension 3 with domain terms and artifact type",
    "specific operational dimension 4 with domain terms and artifact type",
    "specific operational dimension 5 with domain terms and artifact type"
  ]
}}

**Quality Standards:**
- Each query must be substantively different from others
- All queries must be directly derivable from the problem statement
- Queries should target actionable guidance, not background information
- Combined coverage should address all major operational requirements

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
                        # Prioritize actual summary from metadata, fallback to text content
                        summary = metadata.get('summary', result.get('text', ''))
                        nodes.append({
                            'id': node_id,
                            'title': metadata.get('title', 'Unknown'),
                            'summary': summary[:5000] if summary else 'No summary',
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
            for node in nodes[:100]  # Increased limit - batching will handle large sets
        ])
        
        prompt = f"""You are an expert document analyst specializing in policy and operational planning. Your task is to identify which document nodes contain actionable, domain-relevant recommendations for the given problem.

## Problem Statement
{problem_statement}

## Document Nodes to Evaluate
{node_context}

## Evaluation Framework

### Step 1: Understand the Core Domain
First, identify the PRIMARY domain and scope of the problem statement:
- What is the main operational area? (e.g., logistics, clinical care, policy, training, infrastructure)
- What is the specific context? (e.g., emergency response, preparedness planning, resource management)
- What are the key stakeholder groups involved?
- What is the operational scale? (e.g., facility-level, regional, national)

### Step 2: Apply Strict Relevance Criteria
For each node, assess using ALL of these criteria:

**Relevance Scoring (must pass all to be included):**
1. **Domain Match**: Does the node's subject area DIRECTLY align with the problem's primary domain?
   - ✓ Same operational domain (e.g., emergency logistics for logistics queries)
   - ✗ Different domain using similar vocabulary (e.g., clinical protocols for logistics queries)

2. **Functional Alignment**: Does the node address the same functional need?
   - ✓ Provides guidance for the SPECIFIC problem type described
   - ✗ Addresses a different problem that happens to share keywords

3. **Actionability**: Does the node contain implementable guidance?
   - ✓ Concrete procedures, steps, protocols, checklists, decision frameworks
   - ✗ Abstract concepts, background information, or definitions only

4. **Contextual Fit**: Is the operational context compatible?
   - ✓ Same setting/environment (e.g., mass casualty for triage queries)
   - ✗ Different setting (e.g., routine care protocols for emergency queries)

5. **Stakeholder Alignment**: Are the intended users/actors relevant?
   - ✓ Guidance for the same roles mentioned in the problem
   - ✗ Guidance for different professional groups or contexts

### Step 3: Apply Flexible Filtering
**Consider rejecting ONLY if ALL of these apply**:
- Node is from a completely unrelated domain (e.g., agriculture for clinical care queries)
- Node's content has zero operational overlap with the problem
- Node is purely definitional without any procedural guidance
- Node's recommendations are fundamentally incompatible with the problem's context

**Note**: Nodes from adjacent domains, different phases, or different organizational levels may still contain valuable transferable guidance.

### Step 4: Verify Potential Value
Before including a node, ask:
- "Could a practitioner working on THIS problem find THIS node useful?"
- "Does this node provide guidance that might help solve THIS problem?"
- "Is there a reasonable connection between this node and the problem?"

**If the answer to ANY question is 'Yes' or 'Maybe', INCLUDE the node. Only reject if clearly irrelevant.**

## Common False Positive Patterns to Avoid

**Pattern 1: Keyword Overlap Without Semantic Match**
- Example: Rejecting "emergency obstetric protocols" for a query about "emergency operations centers"
- Reason: Both use "emergency" but address completely different operational domains

**Pattern 2: Adjacent but Distinct Domains**
- Example: Rejecting "clinical triage protocols" for a query about "supply chain triage"
- Reason: While related, clinical and logistical triage are operationally distinct

**Pattern 3: Different Operational Levels**
- Example: Rejecting "patient-level interventions" for a query about "system-level planning"
- Reason: Individual vs. system level requires different guidance types

**Pattern 4: Generic Administrative Overlap**
- Example: Rejecting "reproductive health coordination mechanisms" for "logistics coordination"
- Reason: Coordination is generic; the substantive domain differs

## Output Requirements

Return a JSON object containing ONLY the node IDs that pass ALL criteria from Steps 1-4.

**Format:**
{{
  "relevant_node_ids": ["node_id_1", "node_id_2", ...]
}}

**Quality Standards:**
- Recall over precision: Better to include a potentially relevant node than miss an important one
- Be inclusive: Cross-domain nodes may contain valuable actionable content
- Each included node should have POTENTIAL applicability (direct or indirect)

Respond with valid JSON only. No explanations or additional text."""

        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are a senior policy analyst with expertise in document classification, operational planning, and cross-domain reasoning. You excel at distinguishing between superficially similar but fundamentally different content domains. Your analyses are precise, systematic, and follow structured evaluation frameworks.",
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
