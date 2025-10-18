#!/usr/bin/env python3
"""Example usage of the LLM Agent Orchestration System."""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from workflows.orchestration import create_workflow
from workflows.graph_state import ActionPlanState
from config.settings import get_settings


def setup_logging():
    """Setup logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def example_simple_plan():
    """Generate a simple action plan."""
    print("\n" + "="*60)
    print("Example 1: Simple Action Plan Generation")
    print("="*60 + "\n")
    
    # Create workflow
    workflow = create_workflow()
    
    # Define subject
    subject = "hand hygiene protocol implementation"
    
    print(f"Generating action plan for: {subject}")
    print("This may take several minutes...\n")
    
    # Initialize state
    initial_state: ActionPlanState = {
        "subject": subject,
        "current_stage": "start",
        "retry_count": {},
        "errors": [],
        "metadata": {}
    }
    
    # Execute workflow
    final_state = workflow.invoke(initial_state)
    
    # Display results
    if final_state.get("final_plan"):
        print("\n✓ Action plan generated successfully!")
        print(f"\nPreview (first 500 chars):")
        print("-" * 60)
        print(final_state["final_plan"][:500] + "...")
        print("-" * 60)
        
        # Save to file
        output_path = "action_plans/example_hand_hygiene.md"
        Path(output_path).parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(final_state["final_plan"])
        print(f"\nFull plan saved to: {output_path}")
    
    if final_state.get("errors"):
        print("\n⚠ Warnings/Errors:")
        for error in final_state["errors"]:
            print(f"  - {error}")
    
    return final_state


def example_with_metadata():
    """Generate plan with custom metadata."""
    print("\n" + "="*60)
    print("Example 2: Action Plan with Custom Metadata")
    print("="*60 + "\n")
    
    workflow = create_workflow()
    
    initial_state: ActionPlanState = {
        "subject": "emergency triage during mass casualty incident",
        "current_stage": "start",
        "retry_count": {},
        "errors": [],
        "metadata": {
            "user": "Health Manager",
            "organization": "Regional Hospital",
            "date_requested": "2024-01-15"
        }
    }
    
    print("Generating action plan with metadata...")
    print(f"Subject: {initial_state['subject']}")
    print(f"Metadata: {initial_state['metadata']}\n")
    
    final_state = workflow.invoke(initial_state)
    
    if final_state.get("final_plan"):
        print("✓ Plan generated with custom context")
        output_path = "action_plans/example_triage_with_metadata.md"
        Path(output_path).parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(final_state["final_plan"])
        print(f"Saved to: {output_path}")
    
    return final_state


def example_batch_generation():
    """Generate multiple action plans."""
    print("\n" + "="*60)
    print("Example 3: Batch Action Plan Generation")
    print("="*60 + "\n")
    
    subjects = [
        "cholera outbreak response",
        "hospital infection control",
        "disaster supply management"
    ]
    
    workflow = create_workflow()
    results = []
    
    for idx, subject in enumerate(subjects, 1):
        print(f"\n[{idx}/{len(subjects)}] Generating plan for: {subject}")
        
        initial_state: ActionPlanState = {
            "subject": subject,
            "current_stage": "start",
            "retry_count": {},
            "errors": [],
            "metadata": {"batch_id": idx}
        }
        
        try:
            final_state = workflow.invoke(initial_state)
            
            if final_state.get("final_plan"):
                safe_subject = subject.replace(' ', '_')
                output_path = f"action_plans/example_batch_{safe_subject}.md"
                Path(output_path).parent.mkdir(exist_ok=True)
                with open(output_path, 'w') as f:
                    f.write(final_state["final_plan"])
                print(f"  ✓ Saved to: {output_path}")
                results.append((subject, "success", output_path))
            else:
                print(f"  ✗ Failed to generate plan")
                results.append((subject, "failed", None))
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append((subject, "error", str(e)))
    
    print("\n" + "="*60)
    print("Batch Generation Summary:")
    print("="*60)
    for subject, status, detail in results:
        print(f"{status.upper():10} - {subject}")
    
    return results


def example_inspect_workflow_state():
    """Inspect intermediate workflow states."""
    print("\n" + "="*60)
    print("Example 4: Inspecting Workflow States")
    print("="*60 + "\n")
    
    workflow = create_workflow()
    
    initial_state: ActionPlanState = {
        "subject": "vaccine cold chain management",
        "current_stage": "start",
        "retry_count": {},
        "errors": [],
        "metadata": {}
    }
    
    print("Executing workflow with state inspection...\n")
    
    final_state = workflow.invoke(initial_state)
    
    # Inspect stages
    print("Workflow Execution Summary:")
    print("-" * 60)
    
    if final_state.get("extracted_actions"):
        print(f"✓ Extracted Actions: {len(final_state['extracted_actions'])}")
    
    if final_state.get("refined_actions"):
        print(f"✓ Refined Actions: {len(final_state['refined_actions'])}")
    
    if final_state.get("prioritized_actions"):
        print(f"✓ Prioritized Actions: {len(final_state['prioritized_actions'])}")
    
    if final_state.get("assigned_actions"):
        print(f"✓ Assigned Actions: {len(final_state['assigned_actions'])}")
    
    if final_state.get("quality_feedback"):
        feedback = final_state["quality_feedback"]
        print(f"\nQuality Feedback:")
        print(f"  Status: {feedback.get('status', 'N/A')}")
        print(f"  Score: {feedback.get('overall_score', 0):.2f}")
    
    if final_state.get("retry_count"):
        print(f"\nRetries by Stage: {final_state['retry_count']}")
    
    print("-" * 60)
    
    return final_state


def main():
    """Run examples."""
    setup_logging()
    
    print("\n" + "="*60)
    print("LLM Agent Orchestration - Usage Examples")
    print("="*60)
    
    # Check configuration
    settings = get_settings()
    print(f"\nConfiguration:")
    print(f"  Ollama URL: {settings.ollama_base_url}")
    print(f"  Model: {settings.ollama_model}")
    print(f"  Neo4j URI: {settings.neo4j_uri}")
    print(f"  Rules Docs: {settings.rules_docs_dir}")
    print(f"  Protocols Docs: {settings.protocols_docs_dir}")
    
    # Menu
    print("\nSelect example to run:")
    print("  1. Simple action plan generation")
    print("  2. Action plan with custom metadata")
    print("  3. Batch generation (multiple plans)")
    print("  4. Inspect workflow states")
    print("  5. Run all examples")
    print("  0. Exit")
    
    choice = input("\nEnter choice (1-5, 0 to exit): ").strip()
    
    if choice == "1":
        example_simple_plan()
    elif choice == "2":
        example_with_metadata()
    elif choice == "3":
        example_batch_generation()
    elif choice == "4":
        example_inspect_workflow_state()
    elif choice == "5":
        print("\nRunning all examples sequentially...\n")
        example_simple_plan()
        example_with_metadata()
        example_batch_generation()
        example_inspect_workflow_state()
    elif choice == "0":
        print("Exiting...")
        return
    else:
        print("Invalid choice. Exiting...")
        return
    
    print("\n" + "="*60)
    print("Examples Complete!")
    print("="*60)
    print("\nCheck the 'action_plans/' directory for generated plans.")
    print("See 'action_plan_orchestration.log' for detailed logs.\n")


if __name__ == "__main__":
    main()

