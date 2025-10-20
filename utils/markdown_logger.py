"""Markdown-based logging system for agent workflow tracking."""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class MarkdownLogger:
    """
    Thread-safe markdown logger for comprehensive workflow tracking.
    
    Logs all agent inputs, outputs, RAG queries, and processing steps
    to a markdown file in chronological order.
    """
    
    def __init__(self, log_file_path: str):
        """
        Initialize MarkdownLogger.
        
        Args:
            log_file_path: Path to the log file (e.g., 'action_plans/subject_20251016_log.md')
        """
        self.log_file_path = log_file_path
        self.lock = threading.Lock()
        self._buffer = []
        self._initialized = False
        
        # Create directory if needed
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        # Initialize file
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize the log file with header."""
        with self.lock:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("# Action Plan Generation Log\n\n")
                f.write(f"**Created:** {self._get_timestamp()}\n\n")
                f.write("---\n\n")
            self._initialized = True
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _write(self, content: str):
        """
        Thread-safe write to log file.
        
        Args:
            content: Content to write
        """
        with self.lock:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(content)
    
    def _format_json(self, data: Any, max_length: int = 1000000) -> str:
        """
        Format data as JSON string with optional truncation.
        
        Args:
            data: Data to format
            max_length: Maximum length before truncation
            
        Returns:
            Formatted JSON string
        """
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + "\n  ... (truncated)"
            return json_str
        except (TypeError, ValueError):
            return str(data)
    
    def _truncate_text(self, text: str, max_length: int = 1000000) -> str:
        """
        Truncate text to specified length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            
        Returns:
            Truncated text
        """
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def log_workflow_start(self, subject: str):
        """
        Log workflow start.
        
        Args:
            subject: Subject of the action plan
        """
        content = f"## Workflow Started\n\n"
        content += f"**Subject:** {subject}\n"
        content += f"**Timestamp:** {self._get_timestamp()}\n\n"
        content += "---\n\n"
        self._write(content)
    
    def log_workflow_end(self, success: bool = True, error_msg: Optional[str] = None):
        """
        Log workflow completion.
        
        Args:
            success: Whether workflow completed successfully
            error_msg: Optional error message
        """
        content = f"## Workflow Completed\n\n"
        content += f"**Status:** {'Success' if success else 'Failed'}\n"
        content += f"**Timestamp:** {self._get_timestamp()}\n"
        if error_msg:
            content += f"\n**Error:** {error_msg}\n"
        content += "\n---\n\n"
        self._write(content)
    
    def add_section(self, title: str, level: int = 2):
        """
        Add a markdown section header.
        
        Args:
            title: Section title
            level: Header level (2-6)
        """
        header = "#" * min(max(level, 2), 6)
        content = f"{header} {title}\n\n"
        content += f"**Timestamp:** {self._get_timestamp()}\n\n"
        self._write(content)
    
    def log_agent_start(self, agent_name: str, input_data: Any):
        """
        Log agent execution start.
        
        Args:
            agent_name: Name of the agent
            input_data: Input data for the agent
        """
        content = f"## {agent_name} Agent\n\n"
        content += f"**Timestamp:** {self._get_timestamp()}\n"
        content += f"**Status:** Started\n\n"
        content += "**Input:**\n```json\n"
        content += self._format_json(input_data)
        content += "\n```\n\n"
        self._write(content)
    
    def log_agent_output(self, agent_name: str, output_data: Any):
        """
        Log agent execution output.
        
        Args:
            agent_name: Name of the agent
            output_data: Output data from the agent
        """
        content = f"**Output:**\n```json\n"
        content += self._format_json(output_data)
        content += "\n```\n\n"
        content += "---\n\n"
        self._write(content)
    
    def log_processing_step(self, description: str, details: Optional[Any] = None):
        """
        Log an intermediate processing step.
        
        Args:
            description: Description of the processing step
            details: Optional details (will be formatted as JSON if dict/list)
        """
        content = f"**Processing Step:** {description}\n"
        if details:
            if isinstance(details, (dict, list)):
                content += f"```json\n{self._format_json(details)}\n```\n"
            else:
                content += f"- {details}\n"
        content += "\n"
        self._write(content)
    
    def log_rag_query(self, query_text: str, strategy: str = "hybrid", top_k: int = 5, 
                      agent_context: Optional[str] = None):
        """
        Log RAG query parameters.
        
        Args:
            query_text: The search query
            strategy: Retrieval strategy used
            top_k: Number of results requested
            agent_context: Optional context about which agent is querying
        """
        content = f"**RAG Query:**\n"
        if agent_context:
            content += f"- Context: {agent_context}\n"
        content += f"- Query: \"{self._truncate_text(query_text, 150)}\"\n"
        content += f"- Strategy: {strategy}\n"
        content += f"- Top K: {top_k}\n\n"
        self._write(content)
    
    def log_rag_results(self, result_count: int, top_results: Optional[List[Dict[str, Any]]] = None):
        """
        Log RAG query results.
        
        Args:
            result_count: Total number of results
            top_results: Top results with text snippets and scores
        """
        content = f"**RAG Results:** {result_count} results found\n\n"
        
        if top_results:
            for i, result in enumerate(top_results[:5], 1):  # Show top 5
                score = result.get('score', result.get('combined_score', 'N/A'))
                text = result.get('text', '')
                source_type = result.get('source_type', '')
                
                content += f"{i}. "
                if score != 'N/A':
                    content += f"[Score: {score:.2f}] " if isinstance(score, (int, float)) else f"[Score: {score}] "
                if source_type:
                    content += f"[{source_type}] "
                content += f"\"{self._truncate_text(text, 200)}\"\n"
                
                # Add metadata if present
                metadata = result.get('metadata', {})
                if metadata and isinstance(metadata, dict):
                    title = metadata.get('title', '')
                    node_id = metadata.get('node_id', '')
                    if title:
                        content += f"   - Title: {title}\n"
                    if node_id:
                        content += f"   - Node ID: {node_id}\n"
            
            content += "\n"
        
        self._write(content)
    
    def log_llm_call(self, prompt: str, response: Any, model: Optional[str] = None,
                     temperature: Optional[float] = None):
        """
        Log LLM API call.
        
        Args:
            prompt: The prompt sent to LLM
            response: The response from LLM
            model: Model name
            temperature: Temperature setting
        """
        content = f"**LLM Call:**\n"
        if model:
            content += f"- Model: {model}\n"
        if temperature is not None:
            content += f"- Temperature: {temperature}\n"
        content += f"\n**Prompt:**\n```\n{self._truncate_text(prompt)}\n```\n\n"
        content += f"**Response:**\n```json\n{self._format_json(response)}\n```\n\n"
        self._write(content)
    
    def log_error(self, agent_name: str, error_message: str, traceback_info: Optional[str] = None):
        """
        Log an error.
        
        Args:
            agent_name: Name of the agent where error occurred
            error_message: Error message
            traceback_info: Optional traceback information
        """
        content = f"**⚠️ Error in {agent_name}:**\n"
        content += f"- Timestamp: {self._get_timestamp()}\n"
        content += f"- Message: {error_message}\n"
        if traceback_info:
            content += f"\n```\n{traceback_info}\n```\n"
        content += "\n"
        self._write(content)
    
    def log_retry_attempt(self, stage: str, attempt: int, max_retries: int, reason: str):
        """
        Log a retry attempt.
        
        Args:
            stage: Stage being retried
            attempt: Current attempt number
            max_retries: Maximum retry attempts
            reason: Reason for retry
        """
        content = f"**🔄 Retry Attempt:**\n"
        content += f"- Stage: {stage}\n"
        content += f"- Attempt: {attempt}/{max_retries}\n"
        content += f"- Reason: {reason}\n"
        content += f"- Timestamp: {self._get_timestamp()}\n\n"
        self._write(content)
    
    def log_quality_feedback(self, stage: str, feedback: Dict[str, Any]):
        """
        Log quality checker feedback.
        
        Args:
            stage: Stage being checked
            feedback: Quality feedback dictionary
        """
        content = f"**Quality Check:**\n"
        content += f"- Stage: {stage}\n"
        content += f"- Status: {feedback.get('status', 'unknown')}\n"
        content += f"- Score: {feedback.get('overall_score', 'N/A')}\n"
        
        if feedback.get('feedback'):
            content += f"- Feedback: {self._truncate_text(str(feedback['feedback']))}\n"
        
        content += "\n"
        self._write(content)
    
    def log_node_search(self, node_ids: List[str], description: str = ""):
        """
        Log graph node search results.
        
        Args:
            node_ids: List of found node IDs
            description: Optional description of the search
        """
        content = f"**Graph Node Search:**\n"
        if description:
            content += f"- Description: {description}\n"
        content += f"- Found Nodes: {len(node_ids)}\n"
        if node_ids and len(node_ids) <= 10:
            content += f"- Node IDs: {', '.join(node_ids)}\n"
        content += "\n"
        self._write(content)
    
    def add_text(self, text: str, bold: bool = False, italic: bool = False):
        """
        Add plain text to log.
        
        Args:
            text: Text to add
            bold: Whether to make text bold
            italic: Whether to make text italic
        """
        if bold:
            text = f"**{text}**"
        if italic:
            text = f"*{text}*"
        self._write(f"{text}\n")
    
    def add_code_block(self, code: str, language: str = ""):
        """
        Add a code block.
        
        Args:
            code: Code content
            language: Language for syntax highlighting
        """
        content = f"```{language}\n{code}\n```\n\n"
        self._write(content)
    
    def add_list_item(self, item: str, level: int = 0):
        """
        Add a list item.
        
        Args:
            item: List item text
            level: Indentation level
        """
        indent = "  " * level
        content = f"{indent}- {item}\n"
        self._write(content)
    
    def close(self):
        """Close the logger and ensure all data is written."""
        with self.lock:
            # Add final timestamp
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n**Log closed:** {self._get_timestamp()}\n")

