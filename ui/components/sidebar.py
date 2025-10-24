"""Sidebar component with system status and quick actions."""

import streamlit as st
from datetime import datetime
from ui.utils.state_manager import UIStateManager
from ui.utils.formatting import format_datetime
from utils.llm_client import LLMClient
from utils.db_init import get_database_statistics, initialize_all_databases, clear_neo4j_database, clear_chromadb
import logging

logger = logging.getLogger(__name__)


def render_sidebar():
    """Render the sidebar with system status and controls."""
    with st.sidebar:
        st.title("🏥 Action Plan Generator")
        st.divider()
        
        # System Status Section
        render_system_status()
        
        st.divider()
        
        # Quick Stats
        render_quick_stats()
        
        st.divider()
        
        # Quick Actions
        render_quick_actions()
        
        st.divider()
        
        # Configuration Panel
        render_configuration()


def render_system_status():
    """Render system status indicators."""
    st.subheader("🔌 System Status")
    
    # Check connections
    if st.button("🔄 Refresh Status", use_container_width=True):
        check_all_connections()
    
    status = st.session_state.system_status
    last_check = status.get('last_check')
    
    if last_check:
        st.caption(f"Last checked: {format_datetime(last_check)}")
    
    # Status indicators
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.text("Ollama")
        st.text("Neo4j")
        st.text("ChromaDB")
    
    with col2:
        st.text("🟢" if status.get('ollama') else "🔴")
        st.text("🟢" if status.get('neo4j') else "🔴")
        st.text("🟢" if status.get('chromadb') else "🔴")
    
    # Health score



def render_quick_stats():
    """Render quick statistics."""
    st.subheader("📊 Quick Stats")
    
    stats = st.session_state.db_stats
    
    # Neo4j stats
    neo4j_stats = stats.get('neo4j', {})
    st.metric("Neo4j Nodes", neo4j_stats.get('nodes', 0))
    st.metric("Relationships", neo4j_stats.get('relationships', 0))
    
    # ChromaDB stats
    chroma_stats = stats.get('chromadb', {})
    st.metric("Collections", chroma_stats.get('collections', 0))
    st.metric("Documents", chroma_stats.get('documents', 0))


def render_quick_actions():
    """Render quick action buttons."""
    st.subheader("⚡ Quick Actions")
    
    
    # Clear databases with confirmation
    with st.expander("🗑️ Clear Databases"):
        st.warning("⚠️ This will delete all data!")
        
        db_choice = st.selectbox(
            "Select database:",
            ["neo4j", "chromadb", "both"]
        )
        
        confirm = st.text_input("Type 'yes' to confirm:")
        
        if st.button("Clear Database", type="primary"):
            if confirm.lower() == 'yes':
                with st.spinner(f"Clearing {db_choice}..."):
                    try:
                        if db_choice in ["neo4j", "both"]:
                            success, msg = clear_neo4j_database()
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")
                        
                        if db_choice in ["chromadb", "both"]:
                            success, msg = clear_chromadb()
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")
                        
                        # Refresh stats
                        refresh_stats()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            else:
                st.warning("Please type 'yes' to confirm")


def render_configuration():
    """Render configuration panel."""
    st.subheader("⚙️ Configuration")
    
    settings = st.session_state.ui_settings
    
    # Model selection
    model = st.selectbox(
        "Model",
        ["gpt-oss:20b", "cogito:8b", "llama3.1:70b"],
        index=0,
        help="Select Ollama model"
    )
    
    # Temperature
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=float(settings.ollama_temperature),
        step=0.1,
        help="Controls randomness in generation"
    )
    
    # Top K results
    top_k = st.slider(
        "Top K Results",
        min_value=1,
        max_value=20,
        value=settings.top_k_results,
        help="Number of retrieval results"
    )
    
    # Max retries
    max_retries = st.slider(
        "Max Retries",
        min_value=1,
        max_value=5,
        value=settings.max_retries,
        help="Maximum retry attempts per agent"
    )
    
    # Quality threshold
    quality_threshold = st.slider(
        "Quality Threshold",
        min_value=0.5,
        max_value=1.0,
        value=float(settings.quality_threshold),
        step=0.05,
        help="Minimum quality score to pass"
    )
    
    # Update settings in session state
    st.session_state.temp_model = model
    st.session_state.temp_temperature = temperature
    st.session_state.temp_top_k = top_k
    st.session_state.temp_max_retries = max_retries
    st.session_state.temp_quality_threshold = quality_threshold
    
    st.caption("ℹ️ Settings will be applied to next generation")


def check_all_connections():
    """Check all system connections."""
    # Check Ollama
    try:
        llm_client = LLMClient()
        ollama_status = llm_client.check_connection()
        UIStateManager.update_system_status('ollama', ollama_status)
    except Exception as e:
        logger.error(f"Ollama check failed: {e}")
        UIStateManager.update_system_status('ollama', False)
    
    # Check databases
    try:
        stats = get_database_statistics()
        UIStateManager.update_system_status('neo4j', stats['neo4j']['status'] == 'connected')
        UIStateManager.update_system_status('chromadb', stats['chromadb']['status'] == 'connected')
        UIStateManager.update_db_stats(stats)
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        UIStateManager.update_system_status('neo4j', False)
        UIStateManager.update_system_status('chromadb', False)


def refresh_stats():
    """Refresh database statistics."""
    try:
        stats = get_database_statistics()
        UIStateManager.update_db_stats(stats)
    except Exception as e:
        logger.error(f"Stats refresh failed: {e}")
        st.error(f"Failed to refresh stats: {e}")

