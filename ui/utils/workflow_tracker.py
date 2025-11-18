"""Real-time workflow tracking for live progress updates."""

import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime


class WorkflowTracker:
    """Track and visualize workflow execution in real-time."""
    
    def __init__(self, placeholder):
        """
        Initialize workflow tracker.
        
        Args:
            placeholder: Streamlit placeholder for rendering updates
        """
        self.placeholder = placeholder
        self.stages = {}
        self.start_time = datetime.now()
    
    def update_stage(self, stage_name: str, status: str, data: Optional[Dict[str, Any]] = None):
        """
        Update stage status and refresh display.
        
        Args:
            stage_name: Name of the stage
            status: Current status (pending, in_progress, completed, failed)
            data: Optional data associated with the stage
        """
        self.stages[stage_name] = {
            'status': status,
            'data': data or {},
            'timestamp': datetime.now()
        }
        self._render()
    
    def _render(self):
        """Render the workflow progress visualization."""
        with self.placeholder.container():
            st.subheader("⏳ Workflow Progress")
            
            # Calculate elapsed time
            elapsed = (datetime.now() - self.start_time).total_seconds()
            st.caption(f"Elapsed time: {elapsed:.1f}s")
            
            # Show progress for each stage
            for stage_name, stage_info in self.stages.items():
                status = stage_info['status']
                icon = self._get_icon(status)
                
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"{icon} **{self._get_display_name(stage_name)}**")
                    with col2:
                        if status == 'in_progress':
                            st.spinner()
                        elif status == 'completed':
                            st.success("Done", icon="✅")
                        elif status == 'failed':
                            st.error("Failed", icon="❌")
                    
                    # Show stage-specific data
                    if stage_info.get('data'):
                        self._render_stage_data(stage_name, stage_info['data'])
    
    def _render_stage_data(self, stage_name: str, data: Dict[str, Any]):
        """Render stage-specific data."""
        if 'message' in data:
            st.caption(f"└─ {data['message']}")
        
        if 'details' in data:
            with st.expander("Details", expanded=False):
                st.json(data['details'])
    
    @staticmethod
    def _get_icon(status: str) -> str:
        """Get icon for status."""
        icons = {
            'pending': '⏺️',
            'in_progress': '⏳',
            'completed': '✅',
            'failed': '❌',
            'retry': '🔄'
        }
        return icons.get(status, '⏺️')
    
    @staticmethod
    def _get_display_name(stage_name: str) -> str:
        """Get human-readable stage name."""
        names = {
            'orchestrator': 'Orchestrator',
            'analyzer': 'Analyzer',
            'extractor': 'Extractor',
            'phase3': 'Deep Analysis',
            'deduplicator': 'Deduplicator',
            'selector': 'Selector',
            'timing': 'Timing',
            'assigner': 'Assigner',
            'quality_checker': 'Quality Checker',
            'formatter': 'Formatter'
        }
        return names.get(stage_name, stage_name.replace('_', ' ').title())

