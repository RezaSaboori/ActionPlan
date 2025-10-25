"""Translation Refinement Agent for applying dictionary corrections."""

import logging
import re
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class TranslationRefinementAgent:
    """Translation refinement agent for applying dictionary corrections."""
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Translation Refinement Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("refinement")
        logger.info(f"Initialized TranslationRefinementAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> str:
        """
        Execute refinement logic.
        
        Args:
            data: Dictionary containing translated_plan and dictionary_corrections
            
        Returns:
            Final corrected Persian translation
        """
        logger.info("Translation Refinement applying corrections")
        
        translated_plan = data.get("translated_plan", "")
        dictionary_corrections = data.get("dictionary_corrections", [])
        
        if not translated_plan:
            logger.warning("No translated plan provided for refinement")
            return ""
        
        if not dictionary_corrections:
            logger.info("No corrections to apply, returning original translation")
            return translated_plan
        
        # Apply corrections
        refined_plan = self._apply_corrections(translated_plan, dictionary_corrections)
        
        logger.info(f"Refinement completed: {len(dictionary_corrections)} corrections applied")
        return refined_plan
    
    def _apply_corrections(
        self,
        text: str,
        corrections: List[Dict[str, Any]]
    ) -> str:
        """
        Apply dictionary corrections to the translated text.
        
        Only applies corrections with confidence > 0.7.
        """
        refined_text = text
        corrections_applied = 0
        
        # Sort corrections by confidence (highest first)
        sorted_corrections = sorted(
            corrections,
            key=lambda x: x.get("confidence", 0.0),
            reverse=True
        )
        
        for correction in sorted_corrections:
            # Only apply high-confidence corrections
            if not correction.get("requires_correction", False):
                continue
            
            confidence = correction.get("confidence", 0.0)
            if confidence < 0.7:
                logger.debug(f"Skipping low-confidence correction: {confidence:.2f}")
                continue
            
            original_persian = correction.get("original_persian", "")
            original_english = correction.get("original_english", "")
            suggested_persian = correction.get("suggested_persian", "")
            suggested_english = correction.get("suggested_english", "")
            
            if not original_persian or not suggested_persian:
                continue
            
            # Build the pattern to find: "Persian (English)"
            # Escape special regex characters
            escaped_persian = re.escape(original_persian)
            escaped_english = re.escape(original_english)
            
            pattern = rf'{escaped_persian}\s*\(\s*{escaped_english}\s*\)'
            
            # Build replacement: "Suggested_Persian (Suggested_English)"
            replacement = f"{suggested_persian} ({suggested_english})"
            
            # Apply replacement
            new_text = re.sub(pattern, replacement, refined_text)
            
            if new_text != refined_text:
                corrections_applied += 1
                logger.debug(
                    f"Applied correction: '{original_persian} ({original_english})' "
                    f"→ '{suggested_persian} ({suggested_english})' "
                    f"(confidence: {confidence:.2f})"
                )
                refined_text = new_text
        
        logger.info(f"Applied {corrections_applied} corrections out of {len(corrections)} total")
        return refined_text

