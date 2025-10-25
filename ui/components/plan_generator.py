"""Action plan generation component with live progress tracking."""

import streamlit as st
from datetime import datetime
from pathlib import Path
import time
import os
from workflows.orchestration import create_workflow
from workflows.graph_state import ActionPlanState
from ui.utils.state_manager import UIStateManager
from ui.utils.formatting import render_quality_scores, render_action_table, render_timeline_visualization
import logging
import json

logger = logging.getLogger(__name__)


def execute_workflow_with_tracking(workflow, initial_state, container):
    """
    Execute workflow and display each stage's progress.
    
    Args:
        workflow: Compiled LangGraph workflow
        initial_state: Initial workflow state
        container: Streamlit container for displaying progress
        
    Returns:
        Final workflow state
    """
    # Execute the workflow
    with st.spinner("🔄 Executing workflow..."):
        final_state = workflow.invoke(initial_state, config={"recursion_limit": 50})
    
    # Now display all the captured outputs
    st.success("✅ Workflow execution complete!")
    
    with st.expander("📋 Detailed Execution Log", expanded=True):
        # Display retry information
        if final_state.get("retry_count"):
            st.markdown("### 🔄 Retry Information")
            retry_info = final_state["retry_count"]
            if any(count > 0 for count in retry_info.values()):
                for stage, count in retry_info.items():
                    if count > 0:
                        st.warning(f"**{stage}**: {count} retries")
            else:
                st.success("No retries needed - all stages passed on first attempt! ✅")
        
        st.divider()
        
        # Display each stage's output
        display_stage_details("Orchestrator", final_state)
        display_stage_details("Analyzer", final_state)
        display_stage_details("phase3", final_state)
        display_stage_details("Extractor", final_state)
        display_stage_details("Prioritizer", final_state)
        display_stage_details("Assigner", final_state)
        display_stage_details("Formatter", final_state)
        
        # Display quality checks
        if final_state.get("quality_scores"):
            st.markdown("### 📊 Quality Checks")
            render_quality_scores(final_state["quality_scores"])
        
        # Option to view raw state
        with st.expander("🔍 View Raw State Data (Advanced)"):
            st.json({
                "subject": final_state.get("subject"),
                "current_stage": final_state.get("current_stage"),
                "errors": final_state.get("errors", []),
                "retry_count": final_state.get("retry_count", {}),
                "metadata": final_state.get("metadata", {})
            })
    
    return final_state


def display_stage_details(stage_name: str, state: dict):
    """Display detailed output for a specific stage."""
    st.markdown(f"### {get_stage_icon(stage_name)} {stage_name}")
    
    # Orchestrator output
    if stage_name == "Orchestrator":
        if state.get("problem_statement"):
            st.write("**Problem Statement Generated**")
            with st.expander("View Problem Statement"):
                st.markdown(state["problem_statement"])
        if state.get("user_config"):
            config = state["user_config"]
            st.write(f"**Configuration:** {config.get('level')} | {config.get('phase')} | {config.get('subject')}")
    
    # Analyzer output
    elif stage_name == "Analyzer":
        if state.get("all_document_summaries"):
            st.write(f"**Documents Scanned:** {len(state['all_document_summaries'])} documents")
        if state.get("refined_queries"):
            st.write(f"**Refined Queries Generated:** {len(state['refined_queries'])} queries")
            with st.expander("View Queries"):
                for i, query in enumerate(state['refined_queries'], 1):
                    st.caption(f"{i}. {query}")
        if state.get("node_ids"):
            st.write(f"**Relevant Nodes Identified:** {len(state['node_ids'])} nodes")
    
    # phase3 output
    elif stage_name == "phase3" and state.get("subject_nodes"):
        st.write(f"**Deep Analysis Complete:** {len(state['subject_nodes'])} relevant nodes found")
        total_nodes = sum(len(sn.get('nodes', [])) for sn in state['subject_nodes'])
        st.write(f"**Total Document Sections:** {total_nodes}")
    
    # Extractor output
    elif stage_name == "Extractor":
        if state.get("refined_actions"):
            st.write(f"**Actions Extracted:** {len(state['refined_actions'])} actions")
            with st.expander("View Sample Actions"):
                render_action_table(state['refined_actions'][:10])
        if state.get("subject_actions"):
            st.write(f"**Organized by Subject:** {len(state['subject_actions'])} subjects")
    
    # Prioritizer output
    elif stage_name == "Prioritizer" and state.get("prioritized_actions"):
        actions = state['prioritized_actions']
        st.write(f"**Actions Prioritized:** {len(actions)} actions")
        
        # Count by priority
        immediate = len([a for a in actions if a.get('priority_level') == 'immediate'])
        short_term = len([a for a in actions if a.get('priority_level') == 'short-term'])
        long_term = len([a for a in actions if a.get('priority_level') == 'long-term'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔴 Immediate", immediate)
        with col2:
            st.metric("🟡 Short-term", short_term)
        with col3:
            st.metric("🟢 Long-term", long_term)
        
        with st.expander("View Timeline"):
            render_timeline_visualization(actions)
    
    # Assigner output
    elif stage_name == "Assigner" and state.get("assigned_actions"):
        actions = state['assigned_actions']
        st.write(f"**Responsibilities Assigned:** {len(actions)} actions")
        
        # Extract unique roles
        roles = set()
        for action in actions:
            if action.get('who'):
                roles.add(action['who'])
        
        st.write(f"**Roles Involved:** {len(roles)} roles")
        with st.expander("View Roles"):
            for role in sorted(roles)[:20]:
                st.caption(f"• {role}")
    
    # Formatter output
    elif stage_name == "Formatter" and state.get("final_plan"):
        st.write("**Final Plan Formatted**")
        plan_length = len(state['final_plan'])
        st.write(f"**Plan Length:** {plan_length:,} characters")
        st.write(f"**Estimated Pages:** {plan_length // 3000} pages")
    
    st.divider()


def get_stage_icon(stage_name: str) -> str:
    """Get icon for stage."""
    icons = {
        'Orchestrator': '🎯',
        'Analyzer': '🔍',
        'phase3': '🔬',
        'Extractor': '📑',
        'Prioritizer': '⚖️',
        'Assigner': '👥',
        'Formatter': '📝',
        'Quality Checker': '✓'
    }
    return icons.get(stage_name, '▶️')


def render_plan_generator():
    """Render action plan generation interface."""
    st.header("✨ Generate Action Plan")
    
    st.markdown("""
    Generate a comprehensive, evidence-based action plan by providing a health policy subject.
    The system will orchestrate multiple AI agents to extract, refine, prioritize, and assign actions.
    """)
    
    # Input section
    render_input_section()
    
    st.divider()
    
    # Show completed generation if available
    if st.session_state.get('generation_complete'):
        render_completed_generation()


def render_input_section():
    """Render input section for plan generation."""
    st.subheader("📝 Subject Input")
    
    # Example titles
    with st.expander("💡 Example Action Plan Titles"):
        st.markdown("""
        - Emergency Triage Protocol for Mass Casualty Events
        - Hand Hygiene Implementation in Critical Care Units
        - Infection Control Measures During Wartime Operations
        - Medical Supply Chain Management Under Sanctions
        - Hospital Surge Capacity Preparedness Protocol
        - PPE Distribution and Management During Crisis
        """)
    
    # Required fields
    st.markdown("### 📝 Required Information")
    
    # Action plan title
    name = st.text_area(
        "Action Plan Title *",
        placeholder="E.g., Emergency Triage Protocol for Mass Casualty Events",
        height=80,
        help="Enter the title of your action plan (5-200 characters)"
    )

    description = st.text_area(
        "Description (Optional)",
        placeholder="Provide a detailed description of the action plan's goals and scope. This will guide the problem statement generation.",
        height=150,
        help="A detailed description for the orchestrator to define the problem statement."
    )
    
    # Timing
    timing = st.text_input(
        "Timing/Trigger *",
        placeholder="E.g., Immediate activation upon Code Orange declaration",
        help="Specify when this action plan will be activated"
    )
    
    # Organizational level, phase, and subject in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        level = st.selectbox(
            "Organizational Level *",
            options=["ministry", "university", "center"],
            help="Select the organizational level for this action plan"
        )
    
    with col2:
        phase = st.selectbox(
            "Plan Phase *",
            options=["preparedness", "response"],
            help="Select whether this is a preparedness or response plan"
        )
    
    with col3:
        subject = st.selectbox(
            "Crisis Subject *",
            options=["war", "sanction"],
            help="Select the type of crisis this plan addresses"
        )
    
    # Optional output filename
    st.markdown("### Output Settings")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        output_filename = st.text_input(
            "Output Filename (optional)",
            placeholder="Leave empty for auto-generated name",
            help="Custom filename for the generated plan"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        use_custom_name = st.checkbox("Use custom name", value=False)
    
    # Generate button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("🚀 Generate Plan", type="primary", use_container_width=True):
            # Validate required fields
            if not name or not name.strip():
                st.error("❌ Please enter an action plan title")
            elif len(name.strip()) < 5:
                st.error("❌ Action plan title must be at least 5 characters")
            elif not timing or not timing.strip():
                st.error("❌ Please enter timing/trigger information")
            else:
                # Collect all parameters
                generation_params = {
                    "name": name.strip(),
                    "timing": timing.strip(),
                    "level": level,
                    "phase": phase,
                    "subject": subject,
                    "description": description.strip() if description else None,
                    "output_filename": output_filename if use_custom_name else None,
                    "document_filter": None,
                    "trigger": None,
                    "responsible_party": None,
                    "process_owner": None
                }
                start_generation(**generation_params)
    
    with col2:
        if st.button("🗑️ Clear", use_container_width=True):
            UIStateManager.reset_progress()
            if 'generation_complete' in st.session_state:
                del st.session_state.generation_complete
            if 'generation_result' in st.session_state:
                del st.session_state.generation_result
            st.rerun()


def start_generation(
    name: str,
    timing: str,
    level: str,
    phase: str,
    subject: str,
    description: str = None,
    output_filename: str = None,
    document_filter: list = None,
    trigger: str = None,
    responsible_party: str = None,
    process_owner: str = None
):
    """
    Start action plan generation.
    
    Args:
        name: Action plan title
        timing: Timing/trigger information
        level: Organizational level (ministry/university/center)
        phase: Plan phase (preparedness/response)
        subject: Crisis subject (war/sanction)
        output_filename: Optional custom filename
        document_filter: Optional list of documents to query
        trigger: Optional additional activation trigger
        responsible_party: Optional responsible party
        process_owner: Optional process owner
    """
    # Initialize progress tracking
    UIStateManager.reset_progress()
    st.session_state.current_subject = name  # Use name as display subject
    st.session_state.current_output = output_filename
    
    # Run generation directly (synchronous)
    run_generation_workflow(
        name,
        timing,
        level,
        phase,
        subject,
        description,
        output_filename,
        document_filter,
        trigger,
        responsible_party,
        process_owner
    )


def run_generation_workflow(
    name: str,
    timing: str,
    level: str,
    phase: str,
    subject: str,
    description: str = None,
    output_filename: str = None,
    document_filter: list = None,
    trigger: str = None,
    responsible_party: str = None,
    process_owner: str = None
):
    """
    Run the workflow and display detailed progress.
    
    Args:
        name: Action plan title
        timing: Timing/trigger information
        level: Organizational level (ministry/university/center)
        phase: Plan phase (preparedness/response)
        subject: Crisis subject (war/sanction)
        output_filename: Optional output filename
        document_filter: Optional list of documents to query
        trigger: Optional additional activation trigger
        responsible_party: Optional responsible party
        process_owner: Optional process owner
    """
    try:
        logger.info(f"Starting workflow for: {name}")
        
        # Create expandable progress section
        st.subheader("⏳ Workflow Execution Progress")
        
        # Create containers for each stage
        progress_placeholder = st.empty()
        details_container = st.container()
        
        with progress_placeholder.container():
            st.write("📝 Initializing workflow...")
            
        # Get dynamic settings from session state
        dynamic_settings = st.session_state.get('dynamic_settings')
        
        # Create workflow WITHOUT markdown logger (no log file for UI)
        workflow = create_workflow(markdown_logger=None, dynamic_settings=dynamic_settings)
        
        # No separate guideline documents - treat all documents equally
        guideline_documents = []
        
        # Build user configuration dict
        user_config = {
            "name": name,
            "timing": timing,
            "level": level,
            "phase": phase,
            "subject": subject,
            "description": description
        }
        
        # Initial state with new parameters
        initial_state: ActionPlanState = {
            "user_config": user_config,
            "subject": name,  # For backward compatibility
            "current_stage": "start",
            "retry_count": {},
            "errors": [],
            "metadata": {},
            "documents_to_query": document_filter,
            "guideline_documents": guideline_documents,
            "timing": timing,
            "trigger": trigger,
            "responsible_party": responsible_party,
            "process_owner": process_owner
        }
        
        # Track stages
        stages_status = {}
        stage_outputs = {}
        
        # Execute workflow with manual state tracking
        with details_container:
            st.markdown("### 🔄 Agent Execution")
            
            # Progress tracking
            current_state = initial_state
            
            # Manually invoke each stage and capture outputs
            final_state = execute_workflow_with_tracking(
                workflow,
                initial_state,
                details_container
            )
            
        # Check for errors
        if final_state.get("errors"):
            logger.warning(f"Workflow completed with errors: {final_state['errors']}")
            st.warning(f"⚠️ Completed with {len(final_state['errors'])} warning(s)")
            for error in final_state['errors']:
                st.caption(f"- {error}")
        
        # Get final plans (English and Persian)
        final_plan = final_state.get("final_plan", "")
        final_persian_plan = final_state.get("final_persian_plan", "")
        
        if not final_plan:
            logger.error("No action plan generated")
            st.error("❌ No action plan was generated")
            return
        
        with progress_placeholder:
            st.success("💾 Saving action plans...")
        
        # Generate output paths
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)
            safe_name = safe_name.replace(' ', '_')[:50]
            output_filename = f"action_plans/{safe_name}_{timestamp}.md"
        else:
            if not output_filename.endswith('.md'):
                output_filename = f"{output_filename}.md"
            output_filename = f"action_plans/{output_filename}"
        
        # Ensure directory exists
        Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
        
        # Save English plan
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_plan)
        
        logger.info(f"English plan saved to: {output_filename}")
        
        # Save Persian plan
        if final_persian_plan:
            persian_filename = output_filename.replace('.md', '_fa.md')
            with open(persian_filename, 'w', encoding='utf-8') as f:
                f.write(final_persian_plan)
            logger.info(f"Persian plan saved to: {persian_filename}")
        
        with progress_placeholder:
            st.success("✅ Action Plan Generated Successfully!")
        
        # Store results
        st.session_state.generation_result = {
            'final_state': final_state,
            'output_file': output_filename,
            'subject': subject
        }
        
        # Mark complete
        st.session_state.generation_complete = True
        
        # Display success message
        if final_persian_plan:
            persian_filename = output_filename.replace('.md', '_fa.md')
            st.success(f"✅ Action plans generated and saved:\n- English: `{output_filename}`\n- Persian: `{persian_filename}`")
        else:
            st.success(f"✅ Action plan generated and saved to `{output_filename}`")
        
        # Show the generated plan
        st.subheader("📄 Generated Action Plan")
        
        # Display the plan content directly from state (avoid re-reading file)
        st.markdown(final_plan)
        
        # Also provide file content for download
        plan_content = final_plan
        
        st.divider()
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                "📥 Download Plan",
                data=plan_content,
                file_name=Path(output_filename).name,
                mime="text/markdown",
                use_container_width=True
            )
        
        with col2:
            if st.button("📚 View in History", use_container_width=True):
                st.session_state.selected_plan = output_filename
                st.info("Switch to 'Plan History' tab to browse all plans")
        
        with col3:
            if st.button("🔄 Generate Another", use_container_width=True):
                if 'generation_result' in st.session_state:
                    del st.session_state.generation_result
                if 'generation_complete' in st.session_state:
                    del st.session_state.generation_complete
                st.rerun()
        
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        st.error(f"❌ Generation failed: {str(e)}")
        st.exception(e)


def render_completed_generation():
    """Render completed generation results - simple summary."""
    result = st.session_state.get('generation_result', {})
    
    if not result:
        return
    
    st.info("💡 **Tip:** Your generated plan is displayed above. Use the download button to save it, or switch to the 'Plan History' tab to view all plans.")

