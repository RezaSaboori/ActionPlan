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


class ComprehensiveQualityValidator:
    """
    End-to-end quality validator with supervisor authority.
    Validates final checklist, diagnoses root causes, and initiates repairs.
    """
    
    def __init__(self, llm_client: OllamaClient, markdown_logger=None):
        """
        Initialize Comprehensive Quality Validator.
        
        Args:
            llm_client: Ollama client instance
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("comprehensive_quality_validator")
        self.repair_prompt = get_prompt("quality_repair")
        self.diagnosis_prompt = get_prompt("root_cause_diagnosis")
        logger.info("Initialized ComprehensiveQualityValidator")
        
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
        
        validation_prompt = f"""You are validating a final health emergency action checklist.

**Original Subject:** {subject}

**Orchestrator Context (Guidelines/Requirements):**
{json.dumps(orchestrator_context, indent=2)}

**Final Checklist to Validate:**
{final_plan}

**Validation Criteria (score 0-1 each):**
1. **Structural Completeness**: All required sections present (Specifications, Executive Steps, Checklist Content, Approval)
2. **Action Traceability**: Every action has clear WHO, WHEN, WHAT with source citations
3. **Logical Sequencing**: Actions ordered correctly (immediate → urgent → continuous)
4. **Guideline Compliance**: Actions aligned with orchestrator's guideline context
5. **Formatting Quality**: Proper markdown tables, no broken formatting
6. **Actionability**: Actions are specific, measurable, implementable
7. **Metadata Completeness**: All specification fields populated appropriately

**Output JSON format:**
{{
  "status": "pass" | "fail",
  "overall_score": 0.0-1.0,
  "criteria_scores": {{
    "structural_completeness": 0.0-1.0,
    "action_traceability": 0.0-1.0,
    "logical_sequencing": 0.0-1.0,
    "guideline_compliance": 0.0-1.0,
    "formatting_quality": 0.0-1.0,
    "actionability": 0.0-1.0,
    "metadata_completeness": 0.0-1.0
  }},
  "issues_found": ["List specific issues"],
  "strengths": ["List strong points"],
  "detailed_report": "Comprehensive analysis"
}}

Pass threshold: overall_score >= 0.8
"""
        
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
        
        diagnosis_prompt_text = f"""You are a diagnostic agent analyzing quality failures in a multi-agent pipeline.

**Pipeline:**
Orchestrator → Analyzer → Analyzer_D → Extractor → Prioritizer → Assigner → Formatter

**Agent Responsibilities:**
- Orchestrator: Provides guidelines, context, requirements
- Analyzer: Extracts actions from protocols with citations (2 phases)
- phase3: Deep analysis scoring relevance of document nodes
- Extractor: Refines and deduplicates actions with WHO, WHEN, WHAT
- Prioritizer: Assigns timelines and urgency
- Assigner: Maps WHO and WHEN to actions
- Formatter: Compiles final checklist markdown

**Identified Issues:**
{json.dumps(issues, indent=2)}

**Validation Scores:**
{json.dumps(validation_result.get("criteria_scores", {}), indent=2)}

**Orchestrator Context (what was provided):**
{json.dumps(orchestrator_context, indent=2)}

**Assigned Actions (input to formatter):**
{json.dumps(assigned_actions, indent=2)}

**Diagnosis Task:**
For each issue, identify:
1. Which agent is responsible
2. What specifically went wrong
3. Whether issue is minor (self-repairable) or major (requires agent re-run)

**Output JSON:**
{{
  "responsible_agent": "orchestrator|analyzer|phase3|extractor|prioritizer|assigner|formatter",
  "issue_description": "Precise description of root cause",
  "issue_severity": "minor|major",
  "feedback_for_agent": "Specific corrective instructions",
  "can_self_repair": true|false,
  "repair_actions": ["List specific repairs if self-repairable"]
}}

**Severity Guidelines:**
- Minor: Formatting errors, missing metadata fields, typos → self-repairable
- Major: Missing actions, wrong sequencing, no sources, incorrect assignments → agent re-run
"""
        
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
                    "issue_severity": "major",
                    "can_self_repair": False
                }
            
            return response
        
        except Exception as e:
            logger.error(f"Error in diagnosis: {e}")
            return {
                "responsible_agent": "formatter",
                "issue_description": f"Diagnosis error: {str(e)}",
                "issue_severity": "major",
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
            diagnosis.get("issue_severity") == "minor"
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
        
        repair_prompt_text = f"""You are repairing minor issues in a health emergency checklist.

**Original Checklist:**
{final_plan}

**Issues to Fix:**
{json.dumps(repair_actions, indent=2)}

**Repair Guidelines:**
- Fix formatting errors (broken tables, missing headers)
- Fill in missing metadata fields with appropriate placeholders ("TBD", "...")
- Correct typos or grammatical errors
- Ensure all tables have proper markdown syntax
- DO NOT change action content, sequencing, or assignments
- DO NOT add or remove actions
- Preserve all source citations exactly

**Output:** Return the complete repaired markdown checklist.
"""
        
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

