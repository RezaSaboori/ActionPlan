"""Term Identifier Agent for extracting technical terminology from Persian text."""

import logging
import re
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class TermIdentifierAgent:
    """Term identifier agent for identifying technical terms with context."""
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Term Identifier Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.system_prompt = get_prompt("term_identifier")
        self.context_window = self.settings.term_context_window
        logger.info(f"Initialized TermIdentifierAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute term identification logic.
        
        Args:
            data: Dictionary containing segmented_chunks
            
        Returns:
            List of identified terms with context windows
        """
        logger.info("Term Identifier extracting technical terms")
        
        segmented_chunks = data.get("segmented_chunks", [])
        
        if not segmented_chunks:
            logger.warning("No segmented chunks provided for term identification")
            return []
        
        identified_terms = []
        
        for chunk in segmented_chunks:
            # Only process chunks that have technical terms
            if not chunk.get("has_technical_terms", False):
                continue
            
            chunk_text = chunk.get("text", "")
            chunk_id = chunk.get("chunk_id", 0)
            
            # Extract terms with parenthetical English
            terms = self._extract_terms_with_english(chunk_text)
            
            for term_data in terms:
                # Extract context window
                context = self._extract_context_window(
                    chunk_text,
                    term_data["position"]
                )
                
                identified_term = {
                    "term_persian": term_data["persian"],
                    "term_english": term_data["english"],
                    "context": context,
                    "position": {
                        "chunk_id": chunk_id,
                        "line_number": chunk.get("start_line", 0),
                        "char_offset": term_data["position"]
                    },
                    "is_specialized": True  # All parenthetical terms are considered specialized
                }
                
                identified_terms.append(identified_term)
        
        logger.info(f"Term identification completed: {len(identified_terms)} terms identified")
        return identified_terms
    
    def _extract_terms_with_english(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract Persian terms with English in parentheses.
        
        Pattern: Persian_text (English text)
        """
        terms = []
        
        # Pattern to match Persian followed by (English)
        # This looks for text before parentheses and English text inside parentheses
        pattern = r'([\u0600-\u06FF\s]+)\s*\(([A-Za-z\s\-]+)\)'
        
        for match in re.finditer(pattern, text):
            persian_text = match.group(1).strip()
            english_text = match.group(2).strip()
            position = match.start()
            
            # Filter out very short matches (likely noise)
            if len(persian_text) > 2 and len(english_text) > 2:
                terms.append({
                    "persian": persian_text,
                    "english": english_text,
                    "position": position
                })
        
        return terms
    
    def _extract_context_window(self, text: str, position: int) -> str:
        """
        Extract context window around a term.
        
        Gets N sentences before and after the term.
        """
        # Split text into sentences
        # Persian sentence endings: . ۔ ! ?
        sentence_pattern = r'[.۔!?]+\s+'
        sentences = re.split(sentence_pattern, text)
        
        # Find which sentence contains the position
        current_pos = 0
        target_sentence_idx = 0
        
        for idx, sentence in enumerate(sentences):
            sentence_len = len(sentence)
            if current_pos <= position < current_pos + sentence_len:
                target_sentence_idx = idx
                break
            current_pos += sentence_len + 2  # +2 for punctuation and space
        
        # Extract context window
        start_idx = max(0, target_sentence_idx - self.context_window)
        end_idx = min(len(sentences), target_sentence_idx + self.context_window + 1)
        
        context_sentences = sentences[start_idx:end_idx]
        context = '. '.join(context_sentences)
        
        return context

