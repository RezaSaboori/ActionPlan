"""Plan history viewer component."""

import streamlit as st
from pathlib import Path
from datetime import datetime
import os
import re
import time
from ui.utils.formatting import format_file_size, format_datetime


def render_plan_viewer():
    """Render plan history and viewer."""
    st.header("📚 Plan History")
    
    st.markdown("""
    Browse and view previously generated action plans. 
    Plans are stored in the `action_plans/` directory.
    """)
    
    # Get list of plans
    plans = get_plan_files()
    
    if not plans:
        st.info("No action plans found. Generate your first plan to get started!")
        return
    
    # Search and filter
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "🔍 Search Plans",
            placeholder="Search by subject or filename..."
        )
    
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Date (Newest)", "Date (Oldest)", "Name (A-Z)", "Size"]
        )
    
    # Filter and sort plans
    filtered_plans = filter_and_sort_plans(plans, search_query, sort_by)
    
    st.caption(f"Showing {len(filtered_plans)} of {len(plans)} plans")
    
    st.divider()
    
    # Display plans
    render_plan_list(filtered_plans)


def get_plan_files():
    """Get list of plan files from action_plans directory."""
    plans_dir = Path("action_plans")
    
    if not plans_dir.exists():
        return []
    
    plans = []
    
    for file_path in plans_dir.glob("*.md"):
        try:
            stat = file_path.stat()
            
            # Extract subject from filename
            subject = extract_subject_from_filename(file_path.name)
            
            plans.append({
                'path': file_path,
                'name': file_path.name,
                'subject': subject,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime)
            })
        except Exception as e:
            continue
    
    return plans


def extract_subject_from_filename(filename: str) -> str:
    """Extract subject from auto-generated filename."""
    # Remove timestamp and extension
    # Format: subject_YYYYMMDD_HHMMSS.md
    name = filename.replace('.md', '')
    
    # Try to split by timestamp pattern
    match = re.match(r'(.+)_\d{8}_\d{6}$', name)
    if match:
        subject = match.group(1)
        # Replace underscores with spaces
        subject = subject.replace('_', ' ')
        return subject.title()
    
    return name.replace('_', ' ').title()


def filter_and_sort_plans(plans, search_query, sort_by):
    """Filter and sort plans based on criteria."""
    # Filter
    if search_query:
        query = search_query.lower()
        plans = [
            p for p in plans
            if query in p['name'].lower() or query in p['subject'].lower()
        ]
    
    # Sort
    if sort_by == "Date (Newest)":
        plans.sort(key=lambda x: x['modified'], reverse=True)
    elif sort_by == "Date (Oldest)":
        plans.sort(key=lambda x: x['modified'])
    elif sort_by == "Name (A-Z)":
        plans.sort(key=lambda x: x['name'])
    elif sort_by == "Size":
        plans.sort(key=lambda x: x['size'], reverse=True)
    
    return plans


def render_plan_list(plans):
    """Render list of plans."""
    for plan in plans:
        with st.expander(f"📄 {plan['subject']}", expanded=False):
            # Metadata
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**File:** `{plan['name']}`")
                st.markdown(f"**Modified:** {format_datetime(plan['modified'])}")
            
            with col2:
                st.markdown(f"**Size:** {format_file_size(plan['size'])}")
            
            with col3:
                # Actions
                if st.button("👁️ View Plan", key=f"view_{plan['name']}", use_container_width=True):
                    st.session_state.viewing_plan = plan
                    st.rerun()
                
                if st.button("📥 Download", key=f"dl_{plan['name']}", use_container_width=True):
                    with open(plan['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    st.download_button(
                        "Download",
                        data=content,
                        file_name=plan['name'],
                        mime="text/markdown",
                        key=f"dlbtn_{plan['name']}"
                    )
                
                if st.button("🗑️ Delete", key=f"del_{plan['name']}", use_container_width=True):
                    if st.session_state.get(f"confirm_del_{plan['name']}", False):
                        try:
                            os.remove(plan['path'])
                            st.success(f"Deleted {plan['name']}")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete: {e}")
                    else:
                        st.session_state[f"confirm_del_{plan['name']}"] = True
                        st.warning("Click again to confirm")
    
    # View selected plan
    if st.session_state.get('viewing_plan'):
        render_plan_viewer_modal()


def render_plan_viewer_modal():
    """Render plan viewer in a modal-like display."""
    plan = st.session_state.viewing_plan
    
    st.divider()
    st.subheader(f"📄 {plan['subject']}")
    
    # Close button
    if st.button("← Back to List"):
        del st.session_state.viewing_plan
        st.rerun()
    
    st.markdown(f"**File:** `{plan['name']}`")
    st.markdown(f"**Modified:** {format_datetime(plan['modified'])}")
    st.markdown(f"**Size:** {format_file_size(plan['size'])}")
    
    st.divider()
    
    # Load and display plan
    try:
        with open(plan['path'], 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Display markdown content
        st.markdown(content)
        
        st.divider()
        
        # Actions
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.download_button(
                "📥 Download Markdown",
                data=content,
                file_name=plan['name'],
                mime="text/markdown",
                use_container_width=True
            )
        
        with col2:
            if st.button("📋 Copy to Clipboard", use_container_width=True):
                st.code(content, language='markdown')
                st.info("Plan content displayed above - use your browser to copy")
        
        with col3:
            if st.button("🔄 Re-generate", use_container_width=True):
                st.session_state.regenerate_subject = plan['subject']
                del st.session_state.viewing_plan
                # Switch to generate tab
                st.info(f"Go to Generate tab and use subject: {plan['subject']}")
        
        with col4:
            if st.button("🗑️ Delete Plan", use_container_width=True, type="secondary"):
                if st.session_state.get(f"confirm_delete_viewing", False):
                    try:
                        os.remove(plan['path'])
                        st.success("Plan deleted")
                        del st.session_state.viewing_plan
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")
                else:
                    st.session_state.confirm_delete_viewing = True
                    st.warning("Click again to confirm deletion")
        
    except Exception as e:
        st.error(f"Failed to load plan: {e}")


def export_to_pdf(content: str, output_path: str):
    """
    Export plan to PDF (placeholder - requires additional implementation).
    
    Args:
        content: Markdown content
        output_path: Output PDF path
    """
    # This would require markdown to PDF conversion
    # Could use: reportlab, weasyprint, or markdown -> HTML -> PDF
    pass


def export_to_docx(content: str, output_path: str):
    """
    Export plan to DOCX (placeholder - requires additional implementation).
    
    Args:
        content: Markdown content
        output_path: Output DOCX path
    """
    # This would require markdown to DOCX conversion
    # Could use: python-docx with markdown parsing
    pass

