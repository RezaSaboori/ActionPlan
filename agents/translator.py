"""Translator Agent for Persian translation of action plans."""

import logging
from typing import Dict, Any
from utils.llm_client import LLMClient
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class TranslatorAgent:
    """Translator agent for Persian translation using gemma3:27b."""
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Translator Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.translator_model = self.settings.translator_model
        self.system_prompt = get_prompt("translator")
        logger.info(f"Initialized TranslatorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> str:
        """
        Execute translator logic.
        
        Args:
            data: Dictionary containing final_plan in English
            
        Returns:
            Persian translation of the plan
        """
        logger.info("Translator creating Persian translation")
        
        final_plan = data.get("final_plan", "")
        
        if not final_plan:
            logger.warning("No final plan provided for translation")
            return ""
        
        # Generate Persian translation using translator model
        prompt = f"""Translate the following English action plan to Persian.

Follow all translation guidelines:
- Verbatim, officially-certified-grade translation
- Preserve all markdown formatting
- Add English technical terms in parentheses after Persian terms

English Action Plan:
{final_plan}"""
        
        try:
            translated_plan = self.llm.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.1,
                model_override=self.translator_model
            )
            
            logger.info(f"Translation completed: {len(translated_plan)} characters")
            return translated_plan
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise

