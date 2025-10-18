"""Orchestrator Agent for workflow coordination."""

import logging
import json
from typing import Dict, Any
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator agent coordinating the workflow."""
    
    def __init__(
        self,
        llm_client: OllamaClient,
        hybrid_rag: HybridRAG,
        graph_rag=None,
        markdown_logger=None
    ):
        """
        Initialize Orchestrator Agent.
        
        Args:
            llm_client: Ollama client instance
            hybrid_rag: Unified hybrid RAG tool
            graph_rag: Graph RAG for hierarchical queries (optional)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.unified_rag = hybrid_rag
        self.graph_rag = graph_rag
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("orchestrator")
        logger.info("Initialized OrchestratorAgent with unified RAG")
    
    def execute(self, user_subject: str) -> Dict[str, Any]:
        """
        Execute orchestrator logic.
        
        Args:
            user_subject: User's action plan subject
            
        Returns:
            Dictionary with plan structure and context
        """
        logger.info(f"Orchestrator processing subject: {user_subject}")
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step("Querying plan structure guidelines")
        
        # Query rules documents for action plan guidelines
        plan_guidelines = self._query_plan_structure()
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step("Defining plan structure with LLM")
        
        # Create initial context
        context = {
            "subject": user_subject,
            "plan_guidelines": plan_guidelines,
            "structure": self._define_plan_structure(user_subject, plan_guidelines)
        }
        
        logger.info("Orchestrator completed initial analysis")
        return context
    
    def _query_plan_structure(self) -> str:
        """Query unified knowledge base for action plan structure guidelines."""
        query = "Response plan structure guidelines "
        
        try:
            results = self.unified_rag.query(query, strategy="hybrid", top_k=5)
            
            # Combine results with hierarchical context for guidelines
            guidelines = []
            for result in results:
                metadata = result.get('metadata', {})
                title = metadata.get('title', 'Unknown')
                
                # Get hierarchy if this is from a rule document and graph_rag is available
                if self.graph_rag and metadata.get('node_id'):
                    try:
                        hierarchy = self.graph_rag.get_section_hierarchy_string(metadata['node_id'])
                        if hierarchy:
                            guidelines.append(f"[{hierarchy}]: {result['text']}")
                        else:
                            guidelines.append(f"[{title}]: {result['text']}")
                    except:
                        guidelines.append(f"[{title}]: {result['text']}")
                else:
                    guidelines.append(f"[{title}]: {result['text']}")
            
            return "\n\n".join(guidelines)
        
        except Exception as e:
            logger.error(f"Error querying plan structure: {e}")
            return "Standard action plan structure with problem statement, goals, actions, timeline, responsibilities, monitoring."
    
    def _define_plan_structure(self, subject: str, guidelines: str) -> Dict[str, Any]:
        """Define the plan structure using LLM."""
        prompt = f"""Based on the subject and guidelines, define the action plan structure.

Subject: {subject}

Guidelines:
{guidelines}

Provide a JSON structure with these sections:
- problem_statement: Brief description of the problem
- goals: Key objectives
- action_categories: List of action categories needed (e.g., preparedness, response, recovery)
- required_roles: Key roles/stakeholders involved
- timeline_phases: Time phases for the plan

Respond with only valid JSON."""
        
        try:
            structure = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(prompt[:300], structure, temperature=0.3)
            
            return structure
        
        except Exception as e:
            logger.error(f"Error defining structure: {e}")
            # Fallback structure
            return {
                "problem_statement": f"Developing action plan for: {subject}",
                "goals": ["Implement effective protocols", "Ensure stakeholder coordination"],
                "action_categories": ["preparedness", "response", "recovery"],
                "required_roles": ["Emergency Operations Center", "Healthcare Providers"],
                "timeline_phases": ["immediate", "short-term", "long-term"]
            }
    
    def decide_next_step(self, current_stage: str, quality_feedback: Dict[str, Any]) -> str:
        """
        Decide workflow routing based on quality feedback.
        
        Args:
            current_stage: Current workflow stage
            quality_feedback: Feedback from quality checker
            
        Returns:
            Next stage name
        """
        if quality_feedback.get("status") == "pass":
            # Progress to next stage
            stage_sequence = [
                "orchestrator", "analyzer", "extractor", 
                "prioritizer", "assigner", "formatter"
            ]
            
            try:
                current_idx = stage_sequence.index(current_stage)
                if current_idx < len(stage_sequence) - 1:
                    return stage_sequence[current_idx + 1]
                else:
                    return "complete"
            except ValueError:
                return "analyzer"  # Default next step
        
        else:
            # Retry current stage
            return current_stage

