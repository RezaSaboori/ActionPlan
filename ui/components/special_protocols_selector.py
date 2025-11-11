"""Special Protocols selector UI component."""

import streamlit as st
import logging
from typing import List, Dict, Any, Optional
from utils.document_hierarchy_loader import DocumentHierarchyLoader

logger = logging.getLogger(__name__)


def render_special_protocols_selector() -> List[str]:
    """
    Render Special Protocols selector UI.
    
    Allows users to select specific document sections that will bypass
    Analyzer, Phase3, and Selector stages.
    
    Returns:
        List of selected node IDs (empty if none selected)
    """
    st.markdown("### 🎯 Special Protocols (Optional)")
    
    # Info box
    st.info("""
    **Special Protocols** allow you to select specific document sections that will be included 
    directly in the action plan, bypassing the automatic analysis and filtering stages.
    
    **Features:**
    - Selected sections and all their subsections are automatically included
    - Special protocols are merged with normally analyzed content
    - Useful for ensuring critical protocols are always included
    """)
    
    # Initialize session state for selections
    if 'special_protocols_selections' not in st.session_state:
        st.session_state.special_protocols_selections = {}
    
    if 'special_protocols_search' not in st.session_state:
        st.session_state.special_protocols_search = {}
    
    try:
        # Load documents from Neo4j
        loader = DocumentHierarchyLoader()
        documents = loader.get_all_documents()
        
        if not documents:
            st.warning("⚠️ No documents found in the database. Please ingest documents first.")
            loader.close()
            return []
        
        # Document multi-selector
        doc_names = [doc['name'] for doc in documents]
        selected_docs = st.multiselect(
            "Select Document(s)",
            options=doc_names,
            help="Choose one or more documents to browse sections from"
        )
        
        if not selected_docs:
            loader.close()
            return []
        
        st.divider()
        
        # For each selected document, show section browser
        all_selected_node_ids = []
        
        for doc_name in selected_docs:
            with st.expander(f"📄 {doc_name}", expanded=True):
                node_ids = render_document_section_browser(doc_name, loader)
                all_selected_node_ids.extend(node_ids)
        
        # Summary
        if all_selected_node_ids:
            # Calculate total including subsections
            expanded_ids = loader.expand_node_ids_with_subsections(all_selected_node_ids)
            total_with_subsections = len(expanded_ids)
            
            st.success(f"✅ **{len(all_selected_node_ids)} sections selected** "
                      f"({total_with_subsections} total including subsections)")
            
            # Show preview of selections
            with st.expander("📋 Preview Selected Sections"):
                for node_id in all_selected_node_ids:
                    # Get node details
                    nodes = loader.format_for_extractor([node_id])
                    if nodes:
                        node = nodes[0]
                        st.caption(f"• **{node['document']}** → {node['title']}")
        
        loader.close()
        return all_selected_node_ids
        
    except Exception as e:
        logger.error(f"Error in Special Protocols selector: {e}", exc_info=True)
        st.error(f"❌ Error loading documents: {str(e)}")
        return []


def render_document_section_browser(
    doc_name: str,
    loader: DocumentHierarchyLoader
) -> List[str]:
    """
    Render section browser for a specific document.
    
    Args:
        doc_name: Document name
        loader: DocumentHierarchyLoader instance
        
    Returns:
        List of selected node IDs for this document
    """
    # Get sections for this document
    sections = loader.get_document_sections(doc_name)
    
    if not sections:
        st.warning(f"No sections found in '{doc_name}'")
        return []
    
    # Search box
    search_key = f"search_{doc_name}"
    if search_key not in st.session_state.special_protocols_search:
        st.session_state.special_protocols_search[search_key] = ""
    
    search_query = st.text_input(
        "🔍 Search sections",
        value=st.session_state.special_protocols_search[search_key],
        key=f"search_input_{doc_name}",
        placeholder="Type to filter sections..."
    )
    st.session_state.special_protocols_search[search_key] = search_query
    
    # Filter sections based on search
    if search_query:
        filtered_sections = [
            s for s in sections
            if search_query.lower() in s['title'].lower()
        ]
    else:
        filtered_sections = sections
    
    if not filtered_sections:
        st.caption("No sections match your search.")
        return []
    
    st.caption(f"Showing {len(filtered_sections)} of {len(sections)} sections")
    
    # Initialize selection state for this document
    selection_key = f"selections_{doc_name}"
    if selection_key not in st.session_state.special_protocols_selections:
        st.session_state.special_protocols_selections[selection_key] = []
    
    # Display sections with hierarchy and checkboxes
    selected_node_ids = []
    
    # Group by level for better display
    st.markdown("**Select Sections:**")
    
    for section in filtered_sections:
        level = section['level']
        indent = "  " * (level - 1)  # Indent based on level
        
        # Level indicator
        level_icon = "📌" if level == 1 else "→"
        
        # Checkbox for selection
        checkbox_key = f"section_{doc_name}_{section['node_id']}"
        is_selected = st.checkbox(
            f"{indent}{level_icon} **{section['title']}** (Level {level})",
            key=checkbox_key,
            value=section['node_id'] in st.session_state.special_protocols_selections[selection_key]
        )
        
        if is_selected:
            selected_node_ids.append(section['node_id'])
            
            # Show summary if available
            if section.get('summary'):
                with st.container():
                    st.caption(f"{indent}   ℹ️ {section['summary'][:150]}...")
    
    # Update session state
    st.session_state.special_protocols_selections[selection_key] = selected_node_ids
    
    if selected_node_ids:
        st.caption(f"✓ {len(selected_node_ids)} sections selected from this document")
    
    return selected_node_ids


def clear_special_protocols_selections():
    """Clear all special protocols selections from session state."""
    if 'special_protocols_selections' in st.session_state:
        st.session_state.special_protocols_selections = {}
    if 'special_protocols_search' in st.session_state:
        st.session_state.special_protocols_search = {}

