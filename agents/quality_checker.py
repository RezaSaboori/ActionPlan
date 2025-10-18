"""Quality Checker Agent for validating outputs."""

import logging
import json
from typing import Dict, Any
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class QualityCheckerAgent:
    """Quality checker agent for validation and feedback."""
    
    def __init__(
        self,
        llm_client: OllamaClient,
        rules_rag: HybridRAG,
        markdown_logger=None
    ):
        """
        Initialize Quality Checker Agent.
        
        Args:
            llm_client: Ollama client instance
            rules_rag: RAG tool for rules documents
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.rules_rag = rules_rag
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("quality_checker", include_examples=True)
        self.quality_threshold = 0.65
        logger.info("Initialized QualityCheckerAgent")
    
    def execute(
        self,
        data: Dict[str, Any],
        stage: str
    ) -> Dict[str, Any]:
        """
        Execute quality check.
        
        Args:
            data: Data to check (from any agent)
            stage: Current workflow stage
            
        Returns:
            Quality feedback dictionary
        """
        logger.info(f"Quality checking stage: {stage}")
        
        # Get quality standards from rules
        standards = self._get_quality_standards(stage)
        
        # Evaluate data
        feedback = self._evaluate(data, standards, stage)
        
        logger.info(f"Quality check result: {feedback['status']} (score: {feedback['overall_score']})")
        return feedback
    
    def _get_quality_standards(self, stage: str) -> str:
        """Get quality standards for the stage."""
        query = f"quality standards {stage} health policy action plan validation"
        
        try:
            results = self.rules_rag.query(query, strategy="hybrid", top_k=3)
            standards = [r['text'] for r in results]
            return "\n".join(standards)
        
        except Exception as e:
            logger.error(f"Error getting standards: {e}")
            return "Ensure accuracy, completeness, source traceability, and actionability."
    
    def _evaluate(
        self,
        data: Dict[str, Any],
        standards: str,
        stage: str
    ) -> Dict[str, Any]:
        """Evaluate data against standards."""
        data_text = json.dumps(data, indent=2)
        
        prompt = f"""Evaluate this output from the {stage} stage against health policy quality standards.

Output to Evaluate:
{data_text}

Quality Standards:
{standards}

Evaluation Criteria:
1. Accuracy (0-1): Information traceable to sources, no hallucinations
2. Completeness (0-1): All critical aspects covered, no major gaps
3. Source Traceability (0-1): Proper citations with node_id and line numbers
4. Actionability (0-1): Specific, measurable, implementable

Provide evaluation in JSON format:
{{
  "status": "pass|retry",
  "overall_score": 0.0-1.0,
  "scores": {{
    "accuracy": 0.0-1.0,
    "completeness": 0.0-1.0,
    "source_traceability": 0.0-1.0,
    "actionability": 0.0-1.0
  }},
  "feedback": "Detailed constructive feedback",
  "issues": ["Specific issues found"],
  "recommendations": ["Specific improvements needed"]
}}

Pass threshold: overall_score >= 0.65
Be thorough and constructive. Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            # Ensure proper structure
            if not isinstance(result, dict):
                result = {"status": "retry", "overall_score": 0.5, "feedback": "Invalid format"}
            
            # Calculate overall score if not provided
            if "overall_score" not in result:
                scores = result.get("scores", {})
                if scores:
                    result["overall_score"] = sum(scores.values()) / len(scores)
                else:
                    result["overall_score"] = 0.5
            
            # Determine status based on threshold
            if result["overall_score"] >= self.quality_threshold:
                result["status"] = "pass"
            else:
                result["status"] = "retry"
            
            return result
        
        except Exception as e:
            logger.error(f"Error in quality evaluation: {e}")
            return {
                "status": "retry",
                "overall_score": 0.5,
                "scores": {},
                "feedback": f"Quality check failed due to error: {str(e)}",
                "issues": ["Evaluation error"],
                "recommendations": ["Retry with valid data"]
            }

