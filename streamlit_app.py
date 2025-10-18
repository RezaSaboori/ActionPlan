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
        initial_sidebar_state="expanded"
    )
    
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    UIStateManager.initialize()
    
    # Check system status on first load
    if st.session_state.system_status.get('last_check') is None:
        check_all_connections()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
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
        
        **First Time Setup:**
        - Click "Init DB" in sidebar
        - Upload markdown documents
        - Start generating plans!
        """)
    
    st.divider()
    
    # Database statistics
    render_database_stats()
    
    st.divider()
    
    # Recent activity / tips
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💡 Tips")
        st.markdown("""
        - **Be specific** with your subject for better results
        - **Guidelines vs Protocols**: Files are auto-tagged based on filename
        - **Quality scores**: Plans with score < 0.7 may need review
        - **Graph Explorer**: Visualize document structure and relationships
        - **Live Progress**: Watch agents work in real-time during generation
        """)
    
    with col2:
        st.subheader("📖 Documentation")
        st.markdown("""
        - **System Architecture**: Multi-agent orchestration with LangGraph
        - **RAG Strategy**: Hybrid graph + vector retrieval
        - **7 Specialized Agents**: Orchestrator, Analyzer, Extractor, Prioritizer, Assigner, Quality Checker, Formatter
        - **Output Format**: WHO/CDC-compliant action plans
        - **Source Traceability**: Every action linked to source documents
        """)


def render_settings():
    """Render settings page."""
    st.header("⚙️ Settings")
    
    st.markdown("""
    Configure system parameters. Settings are loaded from `.env` file and applied during generation.
    """)
    
    settings = st.session_state.ui_settings
    
    # LLM Settings
    with st.expander("🤖 LLM Configuration", expanded=True):
        st.markdown("**Ollama Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Ollama URL", value=settings.ollama_base_url, disabled=True)
            st.text_input("Model", value=settings.ollama_model, disabled=True)
            st.number_input("Temperature", value=float(settings.ollama_temperature), disabled=True)
        
        with col2:
            st.text_input("Embedding Model", value=settings.ollama_embedding_model, disabled=True)
            st.number_input("Timeout (s)", value=settings.ollama_timeout, disabled=True)
            st.number_input("Max Tokens", value=2000, disabled=True)
        
        st.info("ℹ️ LLM settings are loaded from `.env` file. Edit the file and restart to apply changes.")
    
    # RAG Settings
    with st.expander("🔍 RAG Configuration"):
        st.markdown("**Retrieval Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.number_input("Chunk Size", value=settings.chunk_size, disabled=True)
            st.number_input("Chunk Overlap", value=settings.chunk_overlap, disabled=True)
        
        with col2:
            st.number_input("Top K Results", value=settings.top_k_results, disabled=True)
            st.number_input("Max Section Tokens", value=settings.max_section_tokens, disabled=True)
        
        st.markdown("**Retrieval Modes by Agent**")
        st.text(f"Analyzer: {settings.analyzer_retrieval_mode}")
        st.text(f"Prioritizer: {settings.prioritizer_retrieval_mode}")
        st.text(f"Assigner: {settings.assigner_retrieval_mode}")
    
    # Workflow Settings
    with st.expander("🔄 Workflow Configuration"):
        st.markdown("**Quality Control**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.number_input("Max Retries", value=settings.max_retries, disabled=True)
            st.number_input("Quality Threshold", value=float(settings.quality_threshold), disabled=True)
        
        with col2:
            st.number_input("Analyzer D Score Threshold", value=float(settings.analyzer_d_score_threshold), disabled=True)
            st.number_input("Analyzer D Max Depth", value=settings.analyzer_d_max_depth, disabled=True)
    
    # Database Settings
    with st.expander("🗄️ Database Configuration"):
        st.markdown("**Neo4j**")
        st.text_input("URI", value=settings.neo4j_uri, disabled=True, type="default")
        st.text_input("User", value=settings.neo4j_user, disabled=True)
        
        st.markdown("**ChromaDB**")
        st.text_input("Storage Path", value=settings.chroma_path, disabled=True)
        st.text_input("Documents Collection", value=settings.documents_collection, disabled=True)
    
    # Document Settings
    with st.expander("📄 Document Configuration"):
        st.text_input("Documents Directory", value=settings.docs_dir, disabled=True)
        st.text_input("Graph Prefix", value=settings.graph_prefix, disabled=True)
        
        st.markdown("**Rule Document Names (for auto-tagging as guidelines):**")
        st.text(", ".join(settings.rule_document_names))
    
    st.divider()
    
    st.warning("""
    ⚠️ **Note:** Settings are read from the `.env` file. 
    To modify settings, edit the `.env` file in the project root and restart the application.
    """)
    
    # Show .env file location
    env_path = os.path.abspath(".env")
    st.code(f"Config file: {env_path}", language="bash")


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

