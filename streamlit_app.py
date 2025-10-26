"""Main Streamlit application for Health Policy Action Plan Generator."""

import streamlit as st
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.utils.state_manager import UIStateManager
from ui.components.sidebar import render_sidebar, check_all_connections
from ui.components.database_stats import render_database_stats
from ui.components.graph_viz import render_graph_explorer
from ui.components.document_manager import render_document_manager
from ui.components.plan_generator import render_plan_generator
from ui.components.plan_viewer import render_plan_viewer
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    # Page config
    st.set_page_config(
        page_title="Health Policy Action Plan Generator",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"  # Hide sidebar by default
    )
    
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    UIStateManager.initialize()
    
    # Check system status on first load
    if st.session_state.system_status.get('last_check') is None:
        check_all_connections()
    
    # Main content area (no sidebar)
    render_main_content()
    
    # Footer
    render_footer()


def load_custom_css():
    """Load custom CSS styling."""
    css_file = "ui/styles/custom.css"
    
    if os.path.exists(css_file):
        with open(css_file, 'r') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        # Inline CSS if file doesn't exist
        st.markdown("""
        <style>
        /* Custom styling for the app */
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1E88E5;
            margin-bottom: 1rem;
        }
        
        .sub-header {
            font-size: 1.5rem;
            color: #424242;
            margin-top: 1rem;
        }
        
        .metric-card {
            background-color: #F5F5F5;
            padding: 1rem;
            border-radius: 0.5rem;
            border-left: 4px solid #1E88E5;
        }
        
        .status-connected {
            color: #4CAF50;
            font-weight: bold;
        }
        
        .status-disconnected {
            color: #F44336;
            font-weight: bold;
        }
        
        .stage-completed {
            color: #4CAF50;
        }
        
        .stage-in-progress {
            color: #FF9800;
        }
        
        .stage-failed {
            color: #F44336;
        }
        
        /* Better expander styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            background-color: #F8F9FA;
        }
        
        /* Button styling */
        .stButton > button {
            border-radius: 0.25rem;
            font-weight: 500;
        }
        
        /* Progress bar styling */
        .stProgress > div > div {
            background-color: #1E88E5;
        }
        </style>
        """, unsafe_allow_html=True)


def render_main_content():
    """Render main content area with tabs."""
        
    # Main tabs
    tabs = st.tabs([
        "🏠 Overview",
        "📊 Graph Explorer",
        "📁 Documents",
        "✨ Generate Plan",
        "📚 Plan History",
        "⚙️ Settings"
    ])
    
    with tabs[0]:
        render_overview()
    
    with tabs[1]:
        render_graph_explorer()
    
    with tabs[2]:
        render_document_manager()
    
    with tabs[3]:
        render_plan_generator()
    
    with tabs[4]:
        render_plan_viewer()
    
    with tabs[5]:
        render_settings()


def render_overview():
    """Render overview/dashboard page."""
    st.header("🏠 System Overview")
    
    # System status overview
    col1, col2, col3 = st.columns(3)
    
    status = st.session_state.system_status
    
    with col1:
        st.subheader("🔌 System Health")
        
        ollama_icon = "🟢" if status.get('ollama') else "🔴"
        neo4j_icon = "🟢" if status.get('neo4j') else "🔴"
        chroma_icon = "🟢" if status.get('chromadb') else "🔴"
        
        st.markdown(f"""
        - {ollama_icon} Ollama LLM
        - {neo4j_icon} Neo4j Graph DB
        - {chroma_icon} ChromaDB Vector Store
        """)
        
        connected = sum([status.get('ollama', False), status.get('neo4j', False), status.get('chromadb', False)])
        health_pct = int((connected / 3) * 100)
        
        if health_pct == 100:
            st.success(f"System Health: {health_pct}% ✅")
        elif health_pct >= 66:
            st.warning(f"System Health: {health_pct}% ⚠️")
        else:
            st.error(f"System Health: {health_pct}% ❌")
    
    with col2:
        st.subheader("📊 Database Stats")
        
        stats = st.session_state.db_stats
        neo4j_stats = stats.get('neo4j', {})
        chroma_stats = stats.get('chromadb', {})
        
        st.metric("Neo4j Nodes", neo4j_stats.get('nodes', 0))
        st.metric("Relationships", neo4j_stats.get('relationships', 0))
        st.metric("Vector Documents", chroma_stats.get('documents', 0))
    
    with col3:
        st.subheader("🚀 Quick Start")
        
        st.markdown("""
        **Get Started:**
        1. Check system status
        2. Upload documents
        3. Generate action plan
        """)
    
    st.divider()
    
    # Database statistics
    render_database_stats()


def render_settings():
    """Render interactive settings page with per-agent LLM configuration."""
    st.header("⚙️ Settings")
    
    st.markdown("""
    Configure per-agent LLM settings. Changes apply immediately without restart.
    """)
    
    settings = st.session_state.ui_settings
    dynamic_settings = st.session_state.dynamic_settings
    
    # Bulk Actions
    st.subheader("⚡ Bulk Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Set All to Ollama", use_container_width=True):
            dynamic_settings.set_all_provider("ollama", keep_models=True)
            st.session_state.workflow_reload_needed = True
            st.success("All agents set to Ollama!")
            st.rerun()
    
    with col2:
        if st.button("☁️ Set All to GapGPT", use_container_width=True):
            dynamic_settings.set_all_provider("openai", keep_models=False)
            st.session_state.workflow_reload_needed = True
            st.success("All agents set to GapGPT!")
            st.rerun()
    
    with col3:
        if st.button("↩️ Reset to Defaults", use_container_width=True):
            dynamic_settings.reset_to_defaults()
            st.session_state.workflow_reload_needed = True
            st.success("Reset to defaults!")
            st.rerun()
    
    with col4:
        if st.button("💾 Save Changes", use_container_width=True):
            st.session_state.workflow_reload_needed = True
            st.success("Changes saved! Will apply on next generation.")
    
    st.divider()
    
    # Per-Agent LLM Configuration
    st.subheader("🤖 Per-Agent LLM Configuration")
    
    agent_configs = dynamic_settings.get_all_configs()
    agent_display_names = {
        "orchestrator": "🎯 Orchestrator",
        "analyzer": "🔍 Analyzer",
        "phase3": "🔬 Deep Analysis",
        "extractor": "🔍 Extractor",
        "selector": "🎯 Selector",
        "deduplicator": "🔗 Deduplicator",
        "timing": "⏱️ Timing",
        "assigner": "👥 Assigner",
        "quality_checker": "✅ Quality Gate",
        "formatter": "📝 Formatter",
        "translator": "🌐 Translator",
        "summarizer": "📚 Summarizer (Data Ingestion)"
    }
    
    # Create tabs for agent groups
    main_agents_tab, support_agents_tab = st.tabs(["Main Workflow Agents", "Support Agents"])
    
    main_agents = ["orchestrator", "analyzer", "phase3", "extractor", "selector", 
                   "deduplicator", "timing", "assigner", "quality_checker", "formatter"]
    support_agents = ["translator", "summarizer"]
    
    with main_agents_tab:
        for agent_name in main_agents:
            render_agent_config(agent_name, agent_display_names[agent_name], 
                              agent_configs[agent_name], dynamic_settings)
    
    with support_agents_tab:
        for agent_name in support_agents:
            render_agent_config(agent_name, agent_display_names[agent_name], 
                              agent_configs[agent_name], dynamic_settings)
    
    st.divider()
    
    # Global Settings (Read-only)
    with st.expander("🌍 Global Settings (Read-only)", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Ollama Configuration**")
            st.text_input("Base URL", value=settings.ollama_base_url, disabled=True, key="global_ollama_url")
            st.text_input("Embedding Model", value=settings.ollama_embedding_model, disabled=True, key="global_embed_model")
            
            st.markdown("**Database**")
            st.text_input("Neo4j URI", value=settings.neo4j_uri, disabled=True, key="global_neo4j")
            st.text_input("ChromaDB Path", value=settings.chroma_path, disabled=True, key="global_chroma")
        
        with col2:
            st.markdown("**RAG Configuration**")
            st.number_input("Chunk Size", value=settings.chunk_size, disabled=True, key="global_chunk")
            st.number_input("Top K Results", value=settings.top_k_results, disabled=True, key="global_topk")
            
            st.markdown("**Workflow**")
            st.number_input("Max Retries", value=settings.max_retries, disabled=True, key="global_retries")
            st.number_input("Quality Threshold", value=float(settings.quality_threshold), disabled=True, key="global_quality")


def render_agent_config(agent_name: str, display_name: str, config: dict, dynamic_settings):
    """Render configuration UI for a single agent."""
    with st.expander(display_name, expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**Configure LLM for {display_name}**")
        
        with col2:
            if st.button("↩️ Reset", key=f"reset_{agent_name}", use_container_width=True):
                dynamic_settings.reset_to_defaults(agent_name)
                st.success(f"Reset {display_name}!")
                st.rerun()
        
        # Provider selection
        provider = st.selectbox(
            "Provider",
            options=["ollama", "gapgpt"],
            index=0 if config["provider"] == "ollama" else 1,
            key=f"{agent_name}_provider"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Model selection with presets
            common_models = {
                "ollama": ["gpt-oss:20b", "gemma3:27b", "llama2:13b", "mistral:latest"],
                "gapgpt": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gemini-2.5-flash"]
            }
            
            model_options = common_models.get(provider, [])
            if config["model"] not in model_options:
                model_options.insert(0, config["model"])
            
            model = st.selectbox(
                "Model",
                options=model_options + ["Custom..."],
                index=model_options.index(config["model"]) if config["model"] in model_options else 0,
                key=f"{agent_name}_model_select"
            )
            
            if model == "Custom...":
                model = st.text_input("Custom Model Name", value=config["model"], key=f"{agent_name}_model_custom")
        
        with col2:
            # Temperature slider
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=float(config["temperature"]),
                step=0.1,
                key=f"{agent_name}_temperature"
            )
        
        # API credentials handled via .env file only
        if provider == "gapgpt":
            st.info("ℹ️ API credentials for GapGPT are configured in the .env file.")
            api_key = config.get("api_key")
            api_base = config.get("api_base")
        else:
            api_key = None
            api_base = None
        
        # Apply button
        if st.button("✅ Apply Configuration", key=f"{agent_name}_apply", use_container_width=True):
            success, error = dynamic_settings.update_agent_config(
                agent_name=agent_name,
                provider=provider,
                model=model,
                temperature=temperature,
                api_key=api_key,
                api_base=api_base
            )
            
            if success:
                st.session_state.workflow_reload_needed = True
                st.success(f"✅ Configuration applied for {display_name}!")
                st.rerun()
            else:
                st.error(f"❌ Error: {error}")


def render_footer():
    """Render footer."""
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("🏥 Health Policy Action Plan Generator")
    
    with col2:
        st.caption("Powered by LangGraph, Ollama, Neo4j, ChromaDB")
    
    with col3:
        st.caption("v2.1 - Multi-Agent Orchestration System")


if __name__ == "__main__":
    main()

