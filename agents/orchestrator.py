"""Orchestrator Agent for workflow coordination."""

import logging
from typing import Dict, Any
from utils.llm_client import LLMClient
from utils.prompt_template_loader import assemble_orchestrator_prompt, validate_config
from utils.description_generator import DescriptionGenerator

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator agent coordinating the workflow."""
    
    def __init__(
        self,
        agent_name: str = "orchestrator",
        dynamic_settings=None,
        markdown_logger=None
    ):
        """
        Initialize Orchestrator Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.description_generator = DescriptionGenerator()
        logger.info(f"Initialized OrchestratorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, user_config: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute orchestrator logic using template-based prompt assembly.
        
        Args:
            user_config: Dictionary containing:
                - name: the action plan title
                - timing: time period and/or trigger
                - level: ministry | university | center
                - phase: preparedness | response
                - subject: war | sanction
            
        Returns:
            Dictionary with problem_statement for Analyzer
        """
        logger.info(f"Orchestrator processing config: {user_config.get('name', 'Unknown')}")
        
        # Validate configuration
        is_valid, error_msg = validate_config(user_config)
        if not is_valid:
            logger.error(f"Invalid user configuration: {error_msg}")
            raise ValueError(f"Invalid configuration: {error_msg}")
        
        # Generate description using Perplexity API
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Generating description using Perplexity API",
                {"name": user_config.get('name'), "level": user_config.get('level'), 
                 "phase": user_config.get('phase'), "subject": user_config.get('subject')}
            )
        
        try:
            generated_description = self.description_generator.generate_description(user_config)
            logger.info("Description generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate description: {e}")
            generated_description = "Not provided"
        
        # Combine generated description with user-provided description if exists
        user_provided_description = user_config.get("description", "").strip()
        if user_provided_description:
            # Concatenate: generated description + Important Note + user description
            combined_description = f"{generated_description}\n\n**Important Note:**\n\n{user_provided_description}"
            logger.info("Combined generated description with user-provided description")
        else:
            combined_description = generated_description
        
        # Update user_config with combined description
        user_config_with_description = user_config.copy()
        user_config_with_description["description"] = combined_description
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Assembling orchestrator prompt from template",
                {"level": user_config.get('level'), "phase": user_config.get('phase'), 
                 "subject": user_config.get('subject')}
            )
        
        # Assemble prompt from template
        try:
            assembled_prompt = assemble_orchestrator_prompt(user_config_with_description)
        except Exception as e:
            logger.error(f"Failed to assemble prompt: {e}")
            raise
        
        if self.markdown_logger:
            self.markdown_logger.log_processing_step("Generating problem statement with LLM")
        
        # Generate problem statement using LLM
        try:
            problem_statement = self.llm.generate(
                prompt=assembled_prompt,
                temperature=0.1
            )
            
            if self.markdown_logger:
                self.markdown_logger.log_llm_call(
                    assembled_prompt, 
                    problem_statement, 
                    temperature=0.1
                )
            
            logger.info("Orchestrator successfully generated problem statement")
            
            return {
                "problem_statement": problem_statement,
                "user_config": user_config_with_description
            }
            
        except Exception as e:
            logger.error(f"Error generating problem statement: {e}")
            raise
    
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
                "selector", "deduplicator", "timing",
                "assigner", "formatter"
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

