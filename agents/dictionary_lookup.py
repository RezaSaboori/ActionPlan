"""Dictionary Lookup Agent for validating technical term translations."""

import logging
from typing import Dict, Any, List
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class DictionaryLookupAgent:
    """Dictionary lookup agent for term validation using Dictionary.md."""
    
    def __init__(self, llm_client: OllamaClient, hybrid_rag: HybridRAG, markdown_logger=None):
        """
        Initialize Dictionary Lookup Agent.
        
        Args:
            llm_client: Ollama client instance
            hybrid_rag: HybridRAG instance for dictionary queries
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.hybrid_rag = hybrid_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.system_prompt = get_prompt("dictionary_lookup")
        logger.info("Initialized DictionaryLookupAgent")
    
    def execute(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute dictionary lookup logic.
        
        Args:
            data: Dictionary containing identified_terms
            
        Returns:
            List of corrections from dictionary validation
        """
        logger.info("Dictionary Lookup validating terms")
        
        identified_terms = data.get("identified_terms", [])
        
        if not identified_terms:
            logger.warning("No identified terms provided for dictionary lookup")
            return []
        
        corrections = []
        
        for term in identified_terms:
            term_persian = term.get("term_persian", "")
            term_english = term.get("term_english", "")
            context = term.get("context", "")
            
            # Query dictionary for this term
            dictionary_entry = self._query_dictionary(term_persian, term_english, context)
            
            if dictionary_entry:
                correction = self._validate_term(term, dictionary_entry, context)
                if correction:
                    corrections.append(correction)
        
        logger.info(f"Dictionary lookup completed: {len(corrections)} corrections suggested")
        return corrections
    
    def _query_dictionary(
        self,
        persian_term: str,
        english_term: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Query dictionary using hybrid search.
        
        Tries:
        1. Exact match on Persian term
        2. Exact match on English term
        3. Semantic search with context
        """
        # Build query combining Persian, English, and context
        query = f"{persian_term} {english_term}"
        
        try:
            # Use hybrid RAG to search dictionary
            results = self.hybrid_rag.query(
                query_text=query,
                top_k=3,
                strategy="automatic"
            )
            
            if not results:
                return None
            
            # Get the best matching result
            best_match = results[0]
            
            # Extract dictionary entry details
            entry = {
                "title": best_match.get("metadata", {}).get("heading", ""),
                "content": best_match.get("content", ""),
                "score": best_match.get("score", 0.0),
                "node_id": best_match.get("metadata", {}).get("node_id", "")
            }
            
            return entry
            
        except Exception as e:
            logger.error(f"Dictionary query error: {e}")
            return None
    
    def _validate_term(
        self,
        term: Dict[str, Any],
        dictionary_entry: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Validate term against dictionary entry using LLM.
        
        Returns correction object if term needs correction, None otherwise.
        """
        # Extract term components
        term_persian = term.get("term_persian", "")
        term_english = term.get("term_english", "")
        
        # Extract dictionary entry info
        dict_title = dictionary_entry.get("title", "")
        dict_content = dictionary_entry.get("content", "")
        dict_score = dictionary_entry.get("score", 0.0)
        
        # Parse dictionary title to get standard Persian and English
        # Format: "Persian_term English_term"
        dict_parts = dict_title.split()
        dict_persian = ""
        dict_english = ""
        
        # Find where English starts (first all-ASCII word)
        for i, word in enumerate(dict_parts):
            if all(ord(c) < 128 for c in word if c.isalpha()):
                dict_english = ' '.join(dict_parts[i:])
                dict_persian = ' '.join(dict_parts[:i])
                break
        
        # If no match found, return None
        if dict_score < 0.6:
            return None
        
        # Check if correction needed
        requires_correction = False
        confidence = dict_score
        
        # Check Persian term match
        if dict_persian and dict_persian != term_persian:
            requires_correction = True
        
        # Check English term match
        if dict_english and dict_english.lower() != term_english.lower():
            requires_correction = True
        
        if not requires_correction:
            return None
        
        # Build correction object
        correction = {
            "original_persian": term_persian,
            "original_english": term_english,
            "suggested_persian": dict_persian or term_persian,
            "suggested_english": dict_english or term_english,
            "confidence": confidence,
            "source": dict_title,
            "reasoning": f"Dictionary match (score: {dict_score:.2f})",
            "requires_correction": requires_correction,
            "position": term.get("position", {})
        }
        
        return correction

