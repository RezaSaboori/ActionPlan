"""Segmentation Agent for chunking Persian text for analysis."""

import logging
import re
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class SegmentationAgent:
    """Segmentation agent for splitting Persian text into analyzable chunks."""
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Segmentation Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.system_prompt = get_prompt("segmentation")
        self.chunk_size = self.settings.segmentation_chunk_size
        logger.info(f"Initialized SegmentationAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute segmentation logic.
        
        Args:
            data: Dictionary containing translated_plan
            
        Returns:
            List of chunk objects with metadata
        """
        logger.info("Segmentation creating text chunks")
        
        translated_plan = data.get("translated_plan", "")
        
        if not translated_plan:
            logger.warning("No translated plan provided for segmentation")
            return []
        
        # Split into lines for processing
        lines = translated_plan.split('\n')
        
        chunks = []
        current_chunk = []
        current_section = "Introduction"
        chunk_id = 0
        start_line = 0
        current_length = 0
        
        for line_num, line in enumerate(lines, 1):
            # Track section headers (markdown headings)
            if line.startswith('#'):
                # Save current chunk before starting new section
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append(self._create_chunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        start_line=start_line,
                        end_line=line_num - 1,
                        section=current_section
                    ))
                    chunk_id += 1
                    current_chunk = []
                    current_length = 0
                
                # Update current section
                current_section = line.strip('#').strip()
                start_line = line_num
            
            # Add line to current chunk
            current_chunk.append(line)
            current_length += len(line)
            
            # Check if chunk is large enough and we're at sentence boundary
            if current_length >= self.chunk_size and self._is_sentence_boundary(line):
                chunk_text = '\n'.join(current_chunk)
                chunks.append(self._create_chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    start_line=start_line,
                    end_line=line_num,
                    section=current_section
                ))
                chunk_id += 1
                current_chunk = []
                current_length = 0
                start_line = line_num + 1
        
        # Add final chunk if any
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(self._create_chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                start_line=start_line,
                end_line=len(lines),
                section=current_section
            ))
        
        logger.info(f"Segmentation completed: {len(chunks)} chunks created")
        return chunks
    
    def _create_chunk(
        self,
        chunk_id: int,
        text: str,
        start_line: int,
        end_line: int,
        section: str
    ) -> Dict[str, Any]:
        """Create a chunk object with metadata."""
        # Check if chunk has English terms in parentheses
        has_technical_terms = bool(re.search(r'\([A-Za-z\s]+\)', text))
        
        return {
            "chunk_id": chunk_id,
            "text": text,
            "start_line": start_line,
            "end_line": end_line,
            "section": section,
            "has_technical_terms": has_technical_terms
        }
    
    def _is_sentence_boundary(self, line: str) -> bool:
        """Check if line ends with sentence-ending punctuation."""
        line = line.strip()
        if not line:
            return True
        
        # Persian and English sentence endings
        sentence_endings = ['.', '。', '۔', '!', '?']
        return any(line.endswith(ending) for ending in sentence_endings)

