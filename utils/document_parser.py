"""Document parsing utilities for markdown files."""

import re
import logging
from typing import List, Tuple, Dict, Any
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse markdown documents to extract structure and content."""
    
    @staticmethod
    def extract_headings(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract headings from markdown file with metadata.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            List of heading dictionaries with id, title, level, line_start, line_end
        """
        headings = []
        doc_name = Path(file_path).stem
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            heading_counters = defaultdict(int)
            total_heading_count = 0
            prev_heading_idx = -1
            
            for idx, line in enumerate(lines):
                # Match markdown headings (# through ######)
                match = re.match(r'^(#{1,6})\s+(.*)', line)
                if match:
                    level = len(match.group(1))
                    title = match.group(2).strip()
                    total_heading_count += 1
                    
                    # Generate unique ID using a simple counter for the file
                    heading_id = f"{doc_name}_h{total_heading_count}"
                    
                    # Update previous heading's end line
                    if prev_heading_idx != -1:
                        headings[prev_heading_idx]['line_end'] = idx - 1
                    
                    # Create heading entry
                    heading = {
                        'id': heading_id,
                        'title': title,
                        'level': level,
                        'line_start': idx,
                        'line_end': len(lines) - 1,  # Will be updated by next heading
                        'content_lines': []
                    }
                    headings.append(heading)
                    prev_heading_idx = len(headings) - 1
            
            logger.info(f"Extracted {len(headings)} headings from {file_path}")
            return headings
            
        except Exception as e:
            logger.error(f"Error extracting headings from {file_path}: {e}")
            return []
    
    @staticmethod
    def get_content_by_lines(file_path: str, start_line: int, end_line: int) -> str:
        """
        Extract content from file by line range.
        
        Args:
            file_path: Path to file
            start_line: Starting line number (0-indexed)
            end_line: Ending line number (0-indexed, inclusive)
            
        Returns:
            Content as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            content_lines = lines[start_line:end_line + 1]
            return ''.join(content_lines).strip()
            
        except Exception as e:
            logger.error(f"Error getting content from {file_path}: {e}")
            return ""
    
    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 400,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Chunk text into overlapping segments.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in tokens (approximate)
            chunk_overlap: Overlap between chunks in tokens
            
        Returns:
            List of text chunks
        """
        # Simple word-based chunking (approximation)
        words = text.split()
        chunks = []
        
        # Approximate tokens as words (rough estimate)
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunks.append(' '.join(chunk_words))
            start += (chunk_size - chunk_overlap)
        
        return chunks if chunks else [text]
    
    @staticmethod
    def build_hierarchy(headings: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """
        Build parent-child relationships from heading list.
        
        Args:
            headings: List of heading dictionaries
            
        Returns:
            List of (parent_id, child_id) tuples
        """
        edges = []
        parent_stack = []
        
        for heading in headings:
            level = heading['level']
            heading_id = heading['id']
            
            # Pop stack until we find the appropriate parent
            while parent_stack and parent_stack[-1]['level'] >= level:
                parent_stack.pop()
            
            # Add edge if there's a parent
            if parent_stack:
                parent_id = parent_stack[-1]['id']
                edges.append((parent_id, heading_id))
            
            # Add current heading to stack
            parent_stack.append({'level': level, 'id': heading_id})
        
        return edges
    
    @staticmethod
    def get_document_summary(file_path: str, max_length: int = 500) -> str:
        """
        Get a summary of the document from first few paragraphs.
        
        Args:
            file_path: Path to document
            max_length: Maximum length of summary
            
        Returns:
            Summary text
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(max_length * 2)
            
            # Remove markdown syntax for cleaner summary
            content = re.sub(r'#+\s+', '', content)  # Remove headings
            content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Remove links
            content = re.sub(r'[*_`]', '', content)  # Remove formatting
            
            # Take first paragraph or max_length
            paragraphs = content.split('\n\n')
            summary = paragraphs[0][:max_length] if paragraphs else content[:max_length]
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error getting document summary: {e}")
            return ""

