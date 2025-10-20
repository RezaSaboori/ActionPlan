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
    if stage_name == "Orchestrator" and state.get("rules_context"):
        st.write("**Plan Structure Defined**")
        if state.get("topics"):
            st.write(f"**Topics Identified:** {len(state['topics'])} topics")
            for i, topic in enumerate(state['topics'][:10], 1):
                st.caption(f"{i}. {topic}")
    
    # Analyzer output
    elif stage_name == "Analyzer":
        if state.get("context_map"):
            st.write(f"**Context Map Built:** {len(state['context_map'])} documents processed")
        if state.get("identified_subjects"):
            st.write(f"**Subjects Identified:** {len(state['identified_subjects'])} subjects")
            with st.expander("View Subjects"):
                for i, subj in enumerate(state['identified_subjects'][:15], 1):
                    st.caption(f"{i}. {subj}")
    
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
    
    # Example subjects
    with st.expander("💡 Example Subjects"):
        st.markdown("""
        - Hand hygiene protocol implementation
        - Emergency triage procedures during mass casualty
        - Infection control measures in healthcare facilities
        - Nutritional support in conflict zones
        - Reverse triage in wartime hospitals
        - PPE distribution and management
        """)
    
    # Subject input
    subject = st.text_area(
        "Health Policy Subject",
        placeholder="E.g., hand hygiene protocol implementation in emergency departments",
        height=100,
        help="Enter the health policy topic you want to create an action plan for"
    )
    
    # Advanced options expander
    with st.expander("⚙️ Advanced Options", expanded=False):
        st.markdown("### Document Selection")
        st.info("📘 Guideline documents are always included and cannot be deselected.")
        
        # Document selection (placeholder - will be populated from RAG in future enhancement)
        document_filter = st.multiselect(
            "Select Additional Documents (optional)",
            options=[],  # TODO: Load from RAG
            default=[],
            help="Select specific documents to query. Leave empty to include all available documents.",
            disabled=True  # Disabled for now until document list can be loaded
        )
        
        st.markdown("### Timing and Schedule")
        timing = st.text_input(
            "Timing Context (optional)",
            placeholder="E.g., yearly, seasonal, quarterly, monthly",
            help="Specify when this action plan will be used. Actions without specific timeframes will be adjusted accordingly."
        )
        
        st.markdown("### Organizational Details")
        col1, col2 = st.columns(2)
        
        with col1:
            trigger = st.text_input(
                "Activation Trigger (optional)",
                placeholder="E.g., Mass casualty incident, Disease outbreak",
                help="Specify when this checklist should be activated"
            )
            
            process_owner = st.text_input(
                "Process Owner (optional)",
                placeholder="E.g., Emergency Operations Center Director",
                help="Person or unit responsible for overall process"
            )
        
        with col2:
            responsible_party = st.text_input(
                "Responsible Party (optional)",
                placeholder="E.g., Incident Commander, Triage Team Lead",
                help="Individual or role responsible for execution"
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
            if not subject:
                st.error("❌ Please enter a subject")
            else:
                # Collect all parameters
                generation_params = {
                    "subject": subject,
                    "output_filename": output_filename if use_custom_name else None,
                    "document_filter": document_filter if document_filter else None,
                    "timing": timing if timing else None,
                    "trigger": trigger if trigger else None,
                    "responsible_party": responsible_party if responsible_party else None,
                    "process_owner": process_owner if process_owner else None
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
    subject: str,
    output_filename: str = None,
    document_filter: list = None,
    timing: str = None,
    trigger: str = None,
    responsible_party: str = None,
    process_owner: str = None
):
    """
    Start action plan generation.
    
    Args:
        subject: Health policy subject
        output_filename: Optional custom filename
        document_filter: Optional list of documents to query
        timing: Optional timing context
        trigger: Optional activation trigger
        responsible_party: Optional responsible party
        process_owner: Optional process owner
    """
    # Initialize progress tracking
    UIStateManager.reset_progress()
    st.session_state.current_subject = subject
    st.session_state.current_output = output_filename
    
    # Run generation directly (synchronous)
    run_generation_workflow(
        subject,
        output_filename,
        document_filter,
        timing,
        trigger,
        responsible_party,
        process_owner
    )


def run_generation_workflow(
    subject: str,
    output_filename: str = None,
    document_filter: list = None,
    timing: str = None,
    trigger: str = None,
    responsible_party: str = None,
    process_owner: str = None
):
    """
    Run the workflow and display detailed progress.
    
    Args:
        subject: Health policy subject
        output_filename: Optional output filename
        document_filter: Optional list of documents to query
        timing: Optional timing context
        trigger: Optional activation trigger
        responsible_party: Optional responsible party
        process_owner: Optional process owner
    """
    try:
        logger.info(f"Starting workflow for subject: {subject}")
        
        # Create expandable progress section
        st.subheader("⏳ Workflow Execution Progress")
        
        # Create containers for each stage
        progress_placeholder = st.empty()
        details_container = st.container()
        
        with progress_placeholder.container():
            st.write("📝 Initializing workflow...")
            
        # Create workflow WITHOUT markdown logger (no log file for UI)
        workflow = create_workflow(markdown_logger=None)
        
        # Get guideline documents from settings
        from config.settings import get_settings
        settings = get_settings()
        guideline_documents = settings.rule_document_names
        
        # Initial state with new parameters
        initial_state: ActionPlanState = {
            "subject": subject,
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
            safe_subject = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in subject)
            safe_subject = safe_subject.replace(' ', '_')[:50]
            output_filename = f"action_plans/{safe_subject}_{timestamp}.md"
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

