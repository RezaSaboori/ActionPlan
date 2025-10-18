"""UI formatting helpers and utilities."""

import streamlit as st
from typing import Any, Dict, List
import json


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_datetime(dt) -> str:
    """
    Format datetime for display.
    
    Args:
        dt: Datetime object
        
    Returns:
        Formatted string
    """
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render_metric_card(title: str, value: Any, delta: Any = None, help_text: str = None):
    """
    Render a metric card.
    
    Args:
        title: Metric title
        value: Metric value
        delta: Optional delta value
        help_text: Optional help text
    """
    st.metric(
        label=title,
        value=value,
        delta=delta,
        help=help_text
    )


def render_status_badge(status: bool, true_text: str = "Connected", false_text: str = "Disconnected"):
    """
    Render a status badge.
    
    Args:
        status: Boolean status
        true_text: Text to show when True
        false_text: Text to show when False
    """
    if status:
        st.success(f"🟢 {true_text}")
    else:
        st.error(f"🔴 {false_text}")


def render_quality_scores(scores: Dict[str, float], threshold: float = 0.7):
    """
    Render quality scores with progress bars.
    
    Args:
        scores: Dictionary of score names and values
        threshold: Passing threshold
    """
    st.subheader("📊 Quality Scores")
    
    # Calculate overall score
    if scores:
        overall = sum(scores.values()) / len(scores)
        
        # Overall score
        col1, col2 = st.columns([3, 1])
        with col1:
            st.progress(overall, text=f"Overall Score: {overall:.2f}")
        with col2:
            if overall >= threshold:
                st.success("✅ Pass")
            else:
                st.error("❌ Fail")
        
        st.divider()
        
        # Individual scores
        for name, score in scores.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(score, text=f"{name.replace('_', ' ').title()}")
            with col2:
                st.caption(f"{score:.2f}")


def render_action_table(actions: List[Dict[str, Any]]):
    """
    Render actions in a table format.
    
    Args:
        actions: List of action dictionaries
    """
    if not actions:
        st.info("No actions to display")
        return
    
    for i, action in enumerate(actions, 1):
        with st.expander(f"Action {i}: {action.get('action', 'Unnamed action')[:80]}..."):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Action:** {action.get('action', 'N/A')}")
                st.markdown(f"**Who:** {action.get('who', 'N/A')}")
                st.markdown(f"**When:** {action.get('when', 'N/A')}")
            
            with col2:
                st.markdown(f"**Priority:** {action.get('priority_level', 'N/A')}")
                st.markdown(f"**Category:** {action.get('category', 'N/A')}")
                
                if 'sources' in action:
                    st.markdown(f"**Sources:** {len(action['sources'])} citation(s)")


def render_json_viewer(data: Any, title: str = "Data"):
    """
    Render JSON data in an expandable viewer.
    
    Args:
        data: Data to display
        title: Title for the expander
    """
    with st.expander(f"📄 {title}"):
        st.json(data)


def show_success(message: str):
    """Show success message."""
    st.success(f"✅ {message}")


def show_error(message: str):
    """Show error message."""
    st.error(f"❌ {message}")


def show_warning(message: str):
    """Show warning message."""
    st.warning(f"⚠️ {message}")


def show_info(message: str):
    """Show info message."""
    st.info(f"ℹ️ {message}")


def render_timeline_visualization(actions: List[Dict[str, Any]]):
    """
    Render timeline visualization for actions.
    
    Args:
        actions: List of prioritized actions
    """
    # Group by priority level
    immediate = [a for a in actions if a.get('priority_level') == 'immediate']
    short_term = [a for a in actions if a.get('priority_level') == 'short-term']
    long_term = [a for a in actions if a.get('priority_level') == 'long-term']
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🔴 Immediate")
        st.caption(f"{len(immediate)} actions")
        for action in immediate[:5]:  # Show first 5
            st.markdown(f"- {action.get('action', '')[:60]}...")
    
    with col2:
        st.markdown("### 🟡 Short-term")
        st.caption(f"{len(short_term)} actions")
        for action in short_term[:5]:
            st.markdown(f"- {action.get('action', '')[:60]}...")
    
    with col3:
        st.markdown("### 🟢 Long-term")
        st.caption(f"{len(long_term)} actions")
        for action in long_term[:5]:
            st.markdown(f"- {action.get('action', '')[:60]}...")

