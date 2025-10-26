"""Workflow execution with real-time Streamlit updates."""

import streamlit as st
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class StreamlitWorkflowCallback:
    """Capture workflow events and display in Streamlit."""
    
    def __init__(self, status_container):
        """
        Initialize callback handler.
        
        Args:
            status_container: Streamlit container for status updates
        """
        self.container = status_container
        self.stages = {}
        self.current_stage = None
        
    def on_stage_start(self, stage_name: str):
        """Called when a stage starts."""
        self.current_stage = stage_name
        self.stages[stage_name] = {
            'status': 'in_progress',
            'output': None,
            'retries': 0
        }
        self._update_display()
    
    def on_stage_complete(self, stage_name: str, output: Any):
        """Called when a stage completes."""
        if stage_name in self.stages:
            self.stages[stage_name]['status'] = 'completed'
            self.stages[stage_name]['output'] = output
        self._update_display()
    
    def on_stage_error(self, stage_name: str, error: str):
        """Called when a stage fails."""
        if stage_name in self.stages:
            self.stages[stage_name]['status'] = 'failed'
            self.stages[stage_name]['error'] = error
        self._update_display()
    
    def on_stage_retry(self, stage_name: str, retry_count: int):
        """Called when a stage is retried."""
        if stage_name in self.stages:
            self.stages[stage_name]['retries'] = retry_count
            self.stages[stage_name]['status'] = 'retry'
        self._update_display()
    
    def _update_display(self):
        """Update the Streamlit display with current progress."""
        with self.container:
            for stage_name, stage_info in self.stages.items():
                status = stage_info['status']
                
                if status == 'in_progress':
                    st.write(f"⏳ **{self._format_stage_name(stage_name)}** - In Progress...")
                elif status == 'completed':
                    st.write(f"✅ **{self._format_stage_name(stage_name)}** - Completed")
                    if stage_info.get('output'):
                        self._display_output(stage_name, stage_info['output'])
                elif status == 'retry':
                    st.write(f"🔄 **{self._format_stage_name(stage_name)}** - Retry {stage_info['retries']}")
                elif status == 'failed':
                    st.write(f"❌ **{self._format_stage_name(stage_name)}** - Failed")
                    if stage_info.get('error'):
                        st.error(stage_info['error'])
    
    def _display_output(self, stage_name: str, output: Any):
        """Display stage-specific output."""
        # This will be expanded to show detailed outputs
        if isinstance(output, dict):
            with st.expander(f"View {self._format_stage_name(stage_name)} Output"):
                st.json(output)
    
    @staticmethod
    def _format_stage_name(stage: str) -> str:
        """Format stage name for display."""
        names = {
            'orchestrator': 'Orchestrator',
            'analyzer': 'Analyzer',
            'phase3': 'Deep Analysis',
            'extractor': 'Extractor',
            'deduplicator': 'Deduplicator',
            'selector': 'Selector',
            'timing': 'Timing',
            'assigner': 'Assigner',
            'quality_checker': 'Quality Check',
            'formatter': 'Formatter'
        }
        return names.get(stage, stage.replace('_', ' ').title())

