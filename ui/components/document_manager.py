"""Document upload and management component."""

import streamlit as st
import os
import tempfile
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase
from config.settings import get_settings
from data_ingestion.enhanced_graph_builder import EnhancedGraphBuilder
from data_ingestion.graph_vector_builder import GraphVectorBuilder
from ui.utils.formatting import format_file_size, format_datetime
import logging

logger = logging.getLogger(__name__)


def render_document_manager():
    """Render document management interface."""
    st.header("📁 Document Management")
    
    tabs = st.tabs(["📤 Upload & Ingest", "📋 Manage Documents"])
    
    with tabs[0]:
        render_upload_section()
    
    with tabs[1]:
        render_documents_list()


def render_upload_section():
    """Render document upload and ingestion section."""
    st.subheader("Upload Documents")
    
    st.markdown("""
    Upload markdown files to be ingested into the knowledge base. 
    Files will be automatically tagged as guidelines or protocols based on filename.
    """)
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose markdown files",
        type=['md', 'markdown'],
        accept_multiple_files=True,
        help="Upload one or more markdown files"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
        
        # Preview uploaded files
        with st.expander("📄 Preview Uploaded Files"):
            for file in uploaded_files:
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.text(file.name)
                
                with col2:
                    # Auto-detect document type
                    is_guideline = detect_document_type(file.name)
                    doc_type = "Guideline" if is_guideline else "Protocol"
                    st.text(f"Type: {doc_type}")
                
                with col3:
                    st.text(format_file_size(file.size))
                
                # Show preview
                if st.checkbox(f"Preview {file.name}", key=f"preview_{file.name}"):
                    content = file.read().decode('utf-8')
                    st.text_area("Content", content[:500] + "...", height=150, disabled=True)
                    file.seek(0)  # Reset file pointer
        
        # Document type override
        st.subheader("Document Type Configuration")
        override_types = {}
        
        for file in uploaded_files:
            is_guideline = detect_document_type(file.name)
            override = st.checkbox(
                f"Mark '{file.name}' as guideline",
                value=is_guideline,
                key=f"type_{file.name}"
            )
            override_types[file.name] = override
        
        st.divider()
        
        # Ingest button
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🚀 Ingest Documents", type="primary", use_container_width=True):
                ingest_documents(uploaded_files, override_types)
        
        with col2:
            if st.button("🗑️ Clear Upload", use_container_width=True):
                st.rerun()


def render_documents_list():
    """Render list of ingested documents."""
    st.subheader("Ingested Documents")
    
    try:
        documents = fetch_ingested_documents()
        
        if not documents:
            st.info("No documents found. Upload and ingest documents to get started.")
            return
        
        # Search/filter
        search = st.text_input("🔍 Search documents", placeholder="Enter document name...")
        
        # Filter documents
        if search:
            documents = [d for d in documents if search.lower() in d['name'].lower()]
        
        # Display documents
        st.caption(f"Total: {len(documents)} documents")
        
        for doc in documents:
            with st.expander(f"📄 {doc['name']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Nodes:** {doc.get('node_count', 0)}")
                
                with col2:
                    st.markdown(f"**Source:** `{doc.get('source', 'N/A')}`")
                
                # Actions
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"👁️ View Details", key=f"view_{doc['name']}"):
                        st.session_state.selected_document = doc['name']
                        # Could open a modal or navigate to details page
                
                with col2:
                    if st.button(f"📊 View Graph", key=f"graph_{doc['name']}"):
                        # Switch to graph tab with this document filtered
                        st.info(f"Switch to Graph Explorer and search for: {doc['name']}")
                
                with col3:
                    if st.button(f"🗑️ Delete", key=f"del_{doc['name']}"):
                        if st.session_state.get(f"confirm_del_{doc['name']}", False):
                            delete_document(doc['name'])
                            st.success(f"Deleted {doc['name']}")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_del_{doc['name']}"] = True
                            st.warning("Click again to confirm deletion")
        
        # Statistics
        st.divider()
        render_ingestion_stats(documents)
        
    except Exception as e:
        st.error(f"❌ Failed to load documents: {e}")
        logger.error(f"Document list error: {e}", exc_info=True)


def ingest_documents(uploaded_files, type_overrides):
    """
    Ingest uploaded documents into the knowledge base.
    
    Args:
        uploaded_files: List of uploaded file objects
        type_overrides: Dictionary of filename -> is_guideline mappings
    """
    settings = get_settings()
    
    # Create temporary directory for files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save uploaded files
        for file in uploaded_files:
            file_path = temp_path / file.name
            with open(file_path, 'wb') as f:
                f.write(file.read())
        
        # Progress tracking
        progress_bar = st.progress(0, text="Starting ingestion...")
        status_text = st.empty()
        log_container = st.expander("📋 Ingestion Logs", expanded=True)
        
        try:
            # Graph building
            with log_container:
                st.markdown("### 🔗 Building Neo4j Graph")
                
            status_text.text("Building graph with hierarchical summarization...")
            progress_bar.progress(0.2, text="Building graph...")
            
            graph_builder = EnhancedGraphBuilder(collection_name=settings.graph_prefix)
            
            # Process each file
            for i, file in enumerate(uploaded_files):
                file_path = temp_path / file.name
                
                with log_container:
                    st.info(f"Processing: {file.name}")
                
                status_text.text(f"Processing {file.name}...")
                
                # Build graph for this file
                graph_builder.build_from_directory(
                    str(temp_path),
                    clear_existing=False
                )
                
                progress = 0.2 + (0.4 * (i + 1) / len(uploaded_files))
                progress_bar.progress(progress, text=f"Processed {i + 1}/{len(uploaded_files)} files")
            
            # Get statistics
            stats = graph_builder.get_statistics()
            with log_container:
                st.success(f"✅ Graph built: {stats['documents']} documents, {stats['headings']} headings")
            
            graph_builder.close()
            
            # Vector building
            with log_container:
                st.markdown("### 🔍 Building Vector Store")
            
            status_text.text("Building vector embeddings...")
            progress_bar.progress(0.6, text="Building vectors...")
            
            vector_builder = GraphVectorBuilder(
                summary_collection=settings.summary_collection_name,
                content_collection=settings.content_collection_name
            )
            vector_builder.build_from_graph(str(temp_path))
            vector_builder.close()
            
            with log_container:
                st.success("✅ Vector store built")
            
            progress_bar.progress(1.0, text="Ingestion complete!")
            status_text.text("✅ Ingestion completed successfully")
            
            st.success(f"✅ Successfully ingested {len(uploaded_files)} document(s)")
            
            # Refresh database stats
            from ui.components.sidebar import refresh_stats
            refresh_stats()
            
        except Exception as e:
            st.error(f"❌ Ingestion failed: {e}")
            logger.error(f"Ingestion error: {e}", exc_info=True)
            with log_container:
                st.error(f"Error: {e}")


def fetch_ingested_documents():
    """Fetch list of ingested documents from Neo4j."""
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    documents = []
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:HAS_SUBSECTION*]->(h:Heading)
                RETURN d.name as name, d.source as source,
                       count(h) as node_count
                ORDER BY d.name
            """)
            
            for record in result:
                documents.append({
                    'name': record['name'],
                    'source': record['source'],
                    'node_count': record['node_count']
                })
    
    finally:
        driver.close()
    
    return documents


def delete_document(doc_name: str):
    """Delete a document from the knowledge base."""
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    try:
        with driver.session() as session:
            # Delete document and all its subsections
            session.run("""
                MATCH (d:Document {name: $name})
                OPTIONAL MATCH (d)-[:HAS_SUBSECTION*]->(h:Heading)
                DETACH DELETE d, h
            """, name=doc_name)
    
    finally:
        driver.close()


def detect_document_type(filename: str) -> bool:
    """
    Detect if document is a guideline based on filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        True if guideline, False if protocol
    """
    settings = get_settings()
    guideline_keywords = settings.rule_document_names
    
    filename_lower = filename.lower()
    
    for keyword in guideline_keywords:
        if keyword.lower() in filename_lower:
            return True
    
    return False


def render_ingestion_stats(documents):
    """Render ingestion statistics."""
    st.subheader("📊 Statistics")
    
    total_nodes = sum(d.get('node_count', 0) for d in documents)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Documents", len(documents))
    
    with col2:
        st.metric("Total Nodes", total_nodes)

