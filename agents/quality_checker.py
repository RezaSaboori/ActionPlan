"""Quality Checker Agent for validating outputs."""

import logging
import json
from typing import Dict, Any
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import (
    get_prompt,
    get_quality_checker_evaluation_prompt,
    get_comprehensive_validation_prompt,
    get_root_cause_diagnosis_user_prompt,
    get_quality_repair_user_prompt
)

logger = logging.getLogger(__name__)


class QualityCheckerAgent:
    """Quality checker agent for validation and feedback."""
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        rules_rag: HybridRAG,
        markdown_logger=None
    ):
        """
        Initialize Quality Checker Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            rules_rag: RAG tool for rules documents
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.rules_rag = rules_rag
        self.markdown_logger = markdown_logger
        self.quality_threshold = 0.65
        logger.info(f"Initialized QualityCheckerAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(
        self,
        data: Dict[str, Any],
        stage: str,
        user_config: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Execute quality check.
        
        Args:
            data: Data to check (from any agent)
            stage: Current workflow stage
            user_config: Optional user configuration dict containing level, phase, subject
                        for loading context-specific quality checker templates
            
        Returns:
            Quality feedback dictionary
        """
        logger.info(f"Quality checking stage: {stage}")
        
        # Load context-specific system prompt with templates if config provided
        if user_config:
            logger.info(
                f"Loading quality checker with templates for "
                f"{user_config.get('level')}/{user_config.get('phase')}/{user_config.get('subject')}"
            )
            system_prompt = get_prompt("quality_checker", include_examples=True, config=user_config)
        else:
            logger.warning("No user_config provided, using base quality checker prompt")
            system_prompt = get_prompt("quality_checker", include_examples=True)
        
        # Get quality standards from rules
        standards = self._get_quality_standards(stage)
        
        # Evaluate data
        feedback = self._evaluate(data, standards, stage, system_prompt)
        
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
        stage: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Evaluate data against standards using provided system prompt."""
        data_text = json.dumps(data, indent=2)
        
        prompt = get_quality_checker_evaluation_prompt(stage, data_text, standards)
        
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


class ComprehensiveQualityValidator:
    """
    End-to-end quality validator with supervisor authority.
    Validates final checklist, diagnoses root causes, and initiates repairs.
    """
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Comprehensive Quality Validator.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("comprehensive_quality_validator")
        self.repair_prompt = get_prompt("quality_repair")
        self.diagnosis_prompt = get_prompt("root_cause_diagnosis")
        logger.info(f"Initialized ComprehensiveQualityValidator with agent_name='{agent_name}', model={self.llm.model}")
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive validation of final checklist.
        
        Input data must include:
        - final_plan: The English markdown checklist from formatter
        - subject: Original user subject
        - orchestrator_context: Rules context, guidelines, requirements
        - assigned_actions: The structured actions from assigner
        - original_input: User's original request parameters
        
        Returns:
            Dictionary with status and validation results
        """
        logger.info("Executing comprehensive quality validation")
        
        # Step 1: Validate completeness and quality
        validation_result = self._validate_checklist(data)
        
        if validation_result["status"] == "pass":
            logger.info(f"Validation passed with score {validation_result['overall_score']}")
            return {
                "status": "approve",
                "validated_plan": data["final_plan"],
                "quality_score": validation_result["overall_score"],
                "validation_report": validation_result
            }
        
        # Step 2: Perform root cause analysis
        diagnosis = self._diagnose_issues(data, validation_result)
        
        # Step 3: Decide on repair strategy
        if self._can_self_repair(diagnosis):
            logger.info("Attempting self-repair of minor issues")
            repaired_plan = self._self_repair(data, diagnosis)
            return {
                "status": "self_repair",
                "repaired_plan": repaired_plan,
                "repairs_made": diagnosis.get("repair_actions", []),
                "quality_score": validation_result["overall_score"],
                "diagnosis": diagnosis,
                "validation_report": validation_result
            }
        else:
            logger.warning(f"Major issues found, requesting {diagnosis.get('responsible_agent', 'agent')} re-run")
            return {
                "status": "agent_rerun",
                "responsible_agent": diagnosis.get("responsible_agent", "formatter"),
                "issue_description": diagnosis.get("issue_description", "Quality issues found"),
                "targeted_feedback": diagnosis.get("feedback_for_agent", "Please review output"),
                "retry_count": data.get("validator_retry_count", 0) + 1,
                "diagnosis": diagnosis,
                "validation_report": validation_result
            }
    
    def _validate_checklist(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Holistic validation against multiple criteria.
        
        Returns:
            Dictionary with validation results
        """
        final_plan = data.get("final_plan", "")
        orchestrator_context = data.get("orchestrator_context", {})
        subject = data.get("subject", "")
        
        validation_prompt = get_comprehensive_validation_prompt(subject, orchestrator_context, final_plan)
        
        try:
            response = self.llm.generate_json(
                prompt=validation_prompt,
                system_prompt=self.system_prompt,
                temperature=0.1
            )
            
            # Ensure proper structure
            if not isinstance(response, dict):
                response = {"status": "fail", "overall_score": 0.5}
            
            # Calculate overall score if not provided
            if "overall_score" not in response:
                criteria_scores = response.get("criteria_scores", {})
                if criteria_scores:
                    response["overall_score"] = sum(criteria_scores.values()) / len(criteria_scores)
                else:
                    response["overall_score"] = 0.5
            
            # Determine status based on threshold
            if response["overall_score"] >= 0.8:
                response["status"] = "pass"
            else:
                response["status"] = "fail"
            
            return response
        
        except Exception as e:
            logger.error(f"Error in checklist validation: {e}")
            return {
                "status": "fail",
                "overall_score": 0.5,
                "criteria_scores": {},
                "issues_found": [f"Validation error: {str(e)}"],
                "strengths": [],
                "detailed_report": "Validation failed due to technical error"
            }
    
    def _diagnose_issues(
        self, 
        data: Dict[str, Any], 
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Root cause analysis: identify which agent caused which issues.
        
        Returns:
            Dictionary with diagnosis results
        """
        issues = validation_result.get("issues_found", [])
        orchestrator_context = data.get("orchestrator_context", {})
        assigned_actions = data.get("assigned_actions", [])
        validation_scores = validation_result.get("criteria_scores", {})
        
        diagnosis_prompt_text = get_root_cause_diagnosis_user_prompt(
            issues=issues,
            validation_scores=validation_scores,
            orchestrator_context=orchestrator_context,
            assigned_actions=assigned_actions
        )
        
        try:
            response = self.llm.generate_json(
                prompt=diagnosis_prompt_text,
                system_prompt=self.diagnosis_prompt,
                temperature=0.2
            )
            
            if not isinstance(response, dict):
                response = {
                    "responsible_agent": "formatter",
                    "issue_description": "Unable to diagnose",
                    "severity": "major",
                    "can_self_repair": False
                }
            
            return response
        
        except Exception as e:
            logger.error(f"Error in diagnosis: {e}")
            return {
                "responsible_agent": "formatter",
                "issue_description": f"Diagnosis error: {str(e)}",
                "severity": "major",
                "feedback_for_agent": "Review output quality",
                "can_self_repair": False,
                "repair_actions": []
            }
    
    def _can_self_repair(self, diagnosis: Dict[str, Any]) -> bool:
        """
        Determine if validator can fix issues autonomously.
        
        Returns:
            Boolean indicating if self-repair is possible
        """
        return (
            diagnosis.get("can_self_repair", False) and
            diagnosis.get("severity") == "minor"
        )
    
    def _self_repair(
        self, 
        data: Dict[str, Any], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        Autonomous repair of minor formatting/content issues.
        
        Returns:
            Repaired checklist markdown
        """
        final_plan = data.get("final_plan", "")
        repair_actions = diagnosis.get("repair_actions", [])
        
        repair_prompt_text = get_quality_repair_user_prompt(final_plan, repair_actions)
        
        try:
            repaired = self.llm.generate(
                prompt=repair_prompt_text,
                system_prompt=self.repair_prompt,
                temperature=0.1
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_agent_step(
                    agent="ComprehensiveQualityValidator",
                    action="Self-Repair",
                    details=f"Applied repairs: {repair_actions}"
                )
            
            return repaired
        
        except Exception as e:
            logger.error(f"Error in self-repair: {e}")
            return final_plan  # Return original if repair fails

