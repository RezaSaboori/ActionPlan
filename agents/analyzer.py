"""Analyzer Agent with 2-Phase Workflow: Context Building + Subject Identification."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import OllamaClient
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
        llm_client: OllamaClient,
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
                - subject: User's original subject
                - topics: List of topics from orchestrator
                - structure: Plan structure (optional)
            
        Returns:
            Dictionary with:
                - context_map: Document structure understanding
                - identified_subjects: List of specific subjects for phase3
        """
        subject = context.get("subject", "")
        topics = context.get("topics", [])
        
        logger.info(f"Analyzer Phase 1: Context Building for subject '{subject}' with topics {topics}")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step("Phase 1: Context Building", {"topics": topics})
        
        # Phase 1: Context Building
        context_map = self.phase1_context_building(topics)
        
        logger.info(f"Analyzer Phase 2: Subject Identification")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step("Phase 2: Subject Identification")
        
        # Phase 2: Subject Identification
        identified_subjects = self.phase2_subject_identification(context_map, subject)
        
        logger.info(f"Analyzer identified {len(identified_subjects)} subjects: {identified_subjects}")
        
        return {
            "context_map": context_map,
            "identified_subjects": identified_subjects
        }
    
    def phase1_context_building(self, topics: List[str]) -> Dict[str, Any]:
        """
        Phase 1: Build contextual understanding of document structure.
        
        Steps:
        1. Find parent Document nodes based on topics
        2. For each document, read introduction nodes
        3. Read node summaries to understand structure
        4. When needed, access full content (first/last lines)
        
        Args:
            topics: List of topics from orchestrator
            
        Returns:
            Dictionary with document structure and context
        """
        if not topics:
            logger.warning("No topics provided for context building")
            return {"documents": [], "error": "No topics provided"}
        
        context_map = {
            "documents": [],
            "topics": topics,
            "structure_summary": ""
        }
        
        # Step 1: Find parent Document nodes
        parent_documents = self.graph_rag.get_parent_documents(topics)
        
        if not parent_documents:
            logger.warning(f"No documents found for topics: {topics}")
            return context_map
        
        logger.info(f"Found {len(parent_documents)} parent documents")
        
        # Step 2-4: Process each document
        for doc in parent_documents:
            doc_name = doc.get('name')
            doc_source = doc.get('source')
            
            if not doc_name:
                continue
            
            doc_context = {
                "name": doc_name,
                "source": doc_source,
                "is_rule": doc.get('is_rule', False),
                "introduction_nodes": [],
                "structure_overview": ""
            }
            
            # Step 2: Get introduction nodes (first-level headings)
            intro_nodes = self.graph_rag.get_introduction_nodes(doc_name)
            
            for node in intro_nodes:
                node_summary = {
                    "id": node.get('id'),
                    "title": node.get('title'),
                    "summary": node.get('summary', ''),
                    "start_line": node.get('start_line'),
                    "end_line": node.get('end_line')
                }
                
                # Step 4: Sample first and last lines for context if needed
                if doc_source and node.get('start_line') is not None and node.get('end_line') is not None:
                    try:
                        # Read first few lines
                        first_lines = self.graph_rag.read_node_content(
                            node.get('id'),
                            doc_source,
                            node.get('start_line'),
                            min(node.get('start_line') + self.sample_lines, node.get('end_line'))
                        )
                        
                        # Read last few lines
                        last_lines = self.graph_rag.read_node_content(
                            node.get('id'),
                            doc_source,
                            max(node.get('end_line') - self.sample_lines, node.get('start_line')),
                            node.get('end_line')
                        )
                        
                        node_summary['first_lines'] = first_lines[:300] if first_lines else ""
                        node_summary['last_lines'] = last_lines[-300:] if last_lines else ""
                    except Exception as e:
                        logger.debug(f"Could not sample lines for node {node.get('id')}: {e}")
                
                doc_context['introduction_nodes'].append(node_summary)
            
            # Create structure overview from introduction summaries
            summaries = [n['summary'] for n in doc_context['introduction_nodes'] if n.get('summary')]
            doc_context['structure_overview'] = " | ".join(summaries[:5])  # Top 5 summaries
            
            context_map['documents'].append(doc_context)
        
        # Create overall structure summary
        doc_summaries = []
        for doc in context_map['documents']:
            doc_summaries.append(f"{doc['name']}: {doc['structure_overview']}")
        
        context_map['structure_summary'] = "\n".join(doc_summaries)
        
        logger.info(f"Context building complete: {len(context_map['documents'])} documents processed")
        return context_map
    
    def phase2_subject_identification(
        self,
        context_map: Dict[str, Any],
        user_subject: str
    ) -> List[str]:
        """
        Phase 2: Identify specific subjects for deep analysis using LLM.
        
        Uses LLM to analyze:
        - User's original subject
        - Context from Phase 1
        - Document structure
        
        Args:
            context_map: Output from Phase 1
            user_subject: Original user subject
            
        Returns:
            List of specific subjects for phase3 to process
            Example: "hand hygiene" → ["handwashing protocols", "sanitizer use", "PPE requirements"]
        """
        if not context_map.get('documents'):
            logger.warning("No document context available for subject identification")
            return [user_subject]  # Fallback to original subject
        
        # Prepare context for LLM
        structure_info = context_map.get('structure_summary', '')
        
        # Build document details
        doc_details = []
        for doc in context_map['documents']:
            intro_titles = [n['title'] for n in doc.get('introduction_nodes', [])]
            doc_details.append(
                f"Document: {doc['name']}\n"
                f"  Main sections: {', '.join(intro_titles[:10])}\n"
                f"  Overview: {doc.get('structure_overview', '')[:200]}"
            )
        
        context_text = "\n\n".join(doc_details)
        
        # Get subject identification prompt
        prompt = get_prompt("analyzer_phase2")
        
        # Build complete prompt
        full_prompt = f"""{prompt}

User's Original Subject: {user_subject}

Available Document Context:
{context_text}

Based on the user's subject and the available document structure, identify 3-8 specific SUBJECTS that should be queried for deep analysis.

Each subject should be:
- Specific and focused (not too broad)
- Relevant to the user's original subject
- Aligned with available document sections
- Actionable (suitable for extracting concrete actions)

Examples:
- User subject: "hand hygiene" → Subjects: ["handwashing protocols", "hand sanitizer usage", "PPE and glove use", "hand hygiene compliance monitoring"]
- User subject: "emergency triage" → Subjects: ["triage classification systems", "triage area setup", "patient flow management", "critical care prioritization"]

Respond with a JSON object containing a list of subjects:
{{
  "subjects": ["subject 1", "subject 2", "subject 3", ...]
}}

Respond with valid JSON only."""

        try:
            result = self.llm.generate_json(
                prompt=full_prompt,
                system_prompt="You are a health policy analyst identifying specific subjects for detailed protocol analysis.",
                temperature=0.3
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(full_prompt, result, temperature=0.3)
            
            if isinstance(result, dict) and "subjects" in result:
                subjects = result["subjects"]
                if isinstance(subjects, list) and len(subjects) > 0:
                    # Validate subjects are strings
                    subjects = [str(s) for s in subjects if s]
                    logger.info(f"LLM identified {len(subjects)} subjects")
                    return subjects
            
            logger.warning(f"Unexpected LLM result format: {type(result)}")
            return [user_subject]  # Fallback
            
        except Exception as e:
            logger.error(f"Error in subject identification: {e}")
            return [user_subject]  # Fallback to original subject
