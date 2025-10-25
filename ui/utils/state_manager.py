"""Streamlit session state management."""

import streamlit as st
from datetime import datetime
from typing import Any, Dict, Optional
from config.settings import get_settings
from config.dynamic_settings import DynamicSettingsManager


class UIStateManager:
    """Manage Streamlit session state for the application."""
    
    @staticmethod
    def initialize():
        """Initialize all session state variables."""
        # Workflow state
        if 'workflow_state' not in st.session_state:
            st.session_state.workflow_state = {}
        
        # Progress tracking
        if 'generation_progress' not in st.session_state:
            st.session_state.generation_progress = {}
        
        # Current generation
        if 'current_generation' not in st.session_state:
            st.session_state.current_generation = None
        
        # Settings
        if 'ui_settings' not in st.session_state:
            st.session_state.ui_settings = get_settings()
        
        # Dynamic LLM settings
        if 'dynamic_settings' not in st.session_state:
            st.session_state.dynamic_settings = DynamicSettingsManager()
        
        # Flag to track if workflow needs reload
        if 'workflow_reload_needed' not in st.session_state:
            st.session_state.workflow_reload_needed = False
        
        # System status
        if 'system_status' not in st.session_state:
            st.session_state.system_status = {
                'ollama': False,
                'neo4j': False,
                'chromadb': False,
                'last_check': None
            }
        
        # Database statistics
        if 'db_stats' not in st.session_state:
            st.session_state.db_stats = {
                'neo4j': {'nodes': 0, 'relationships': 0},
                'chromadb': {'collections': 0, 'documents': 0}
            }
        
        # Selected plan for viewing
        if 'selected_plan' not in st.session_state:
            st.session_state.selected_plan = None
        
        # Upload state
        if 'uploaded_files_data' not in st.session_state:
            st.session_state.uploaded_files_data = []
        
        # Graph visualization state
        if 'selected_node' not in st.session_state:
            st.session_state.selected_node = None
    
    @staticmethod
    def update_progress(stage: str, status: str, output: Any):
        """
        Update workflow progress for a specific stage.
        
        Args:
            stage: Name of the workflow stage
            status: Status (pending, in_progress, completed, failed)
            output: Output data from the stage
        """
        st.session_state.generation_progress[stage] = {
            'status': status,
            'output': output,
            'timestamp': datetime.now()
        }
    
    @staticmethod
    def reset_progress():
        """Reset generation progress."""
        st.session_state.generation_progress = {}
        st.session_state.current_generation = None
    
    @staticmethod
    def update_system_status(component: str, status: bool):
        """
        Update system component status.
        
        Args:
            component: Component name (ollama, neo4j, chromadb)
            status: Connection status (True/False)
        """
        st.session_state.system_status[component] = status
        st.session_state.system_status['last_check'] = datetime.now()
    
    @staticmethod
    def update_db_stats(stats: Dict[str, Any]):
        """
        Update database statistics.
        
        Args:
            stats: Statistics dictionary from backend
        """
        st.session_state.db_stats = stats
    
    @staticmethod
    def get_workflow_stages():
        """Get list of workflow stages in order."""
        return [
            'orchestrator',
            'analyzer',
            'analyzer_d',
            'quality_checker_analyzer',
            'extractor',
            'quality_checker_extractor',
            'prioritizer',
            'quality_checker_prioritizer',
            'assigner',
            'quality_checker_assigner',
            'formatter'
        ]
    
    @staticmethod
    def get_stage_display_name(stage: str) -> str:
        """Get human-readable stage name."""
        stage_names = {
            'orchestrator': 'Orchestrator',
            'analyzer': 'Analyzer (Phase 1 & 2)',
            'analyzer_d': 'Analyzer D (Deep Analysis)',
            'quality_checker_analyzer': 'Quality Check: Analyzer',
            'extractor': 'Extractor',
            'quality_checker_extractor': 'Quality Check: Extractor',
            'prioritizer': 'Prioritizer',
            'quality_checker_prioritizer': 'Quality Check: Prioritizer',
            'assigner': 'Assigner',
            'quality_checker_assigner': 'Quality Check: Assigner',
            'formatter': 'Formatter'
        }
        return stage_names.get(stage, stage.title())
    
    @staticmethod
    def get_stage_icon(status: str) -> str:
        """Get icon for stage status."""
        icons = {
            'pending': '⏺️',
            'in_progress': '⏳',
            'completed': '✅',
            'failed': '❌',
            'retry': '🔄'
        }
        return icons.get(status, '⏺️')

