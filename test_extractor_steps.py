#!/usr/bin/env python3
"""Temporary tester for dependency-to-action conversion and formula integration steps."""

import sys
import logging
from typing import Dict, Any, List

# Setup logging to see all output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project root to path
sys.path.insert(0, '/storage03/Saboori/ActionPlan/Agents')

from agents.extractor import ExtractorAgent, create_action_schema, create_dependency_schema, create_formula_schema, create_reference
from utils.llm_client import LLMClient
from utils.markdown_logger import MarkdownLogger
from config.settings import get_settings
from config.dynamic_settings import DynamicSettingsManager

# Mock markdown logger for testing
class TestMarkdownLogger:
    """Simple markdown logger for testing."""
    def __init__(self):
        self.content = []
    
    def add_text(self, text: str, bold: bool = False):
        prefix = "**" if bold else ""
        self.content.append(f"{prefix}{text}{prefix}")
    
    def add_list_item(self, text: str, level: int = 0):
        indent = "  " * level
        self.content.append(f"{indent}- {text}")
    
    def log_processing_step(self, title: str, data: Dict[str, Any]):
        self.content.append(f"### {title}")
        for key, value in data.items():
            self.content.append(f"- {key}: {value}")
    
    def get_output(self) -> str:
        return "\n".join(self.content)
    
    def print_output(self):
        print("\n" + "="*80)
        print("MARKDOWN LOGGER OUTPUT:")
        print("="*80)
        print(self.get_output())
        print("="*80 + "\n")


def create_test_dependencies() -> List[Dict[str, Any]]:
    """Create sample dependencies for testing."""
    reference = create_reference(
        document="test_document.md",
        line_range="100-150",
        node_id="test_node_1",
        node_title="Test Node"
    )
    
    return [
        create_dependency_schema(
            dependency_title="Emergency Medical Supplies",
            category="resource",
            description="Trauma kits (50 units), IV fluids (200 bags), bandages (500 units), pain medications",
            reference=reference
        ),
        create_dependency_schema(
            dependency_title="Triage Equipment Budget",
            category="budget",
            description="$25,000 for portable triage stations, $10,000 for communication equipment",
            reference=reference
        ),
        create_dependency_schema(
            dependency_title="Trained Triage Personnel",
            category="requirement",
            description="Minimum 5 certified triage nurses, 2 emergency physicians with mass casualty training",
            reference=reference
        ),
    ]


def create_test_formulas() -> List[Dict[str, Any]]:
    """Create sample formulas for testing."""
    reference = create_reference(
        document="test_document.md",
        line_range="200-250",
        node_id="test_node_2",
        node_title="Test Node"
    )
    
    return [
        create_formula_schema(
            formula="Staff Required = Total Patients / Staff-to-Patient Ratio",
            formula_context="Calculate minimum staffing needed for triage operations",
            variables_definition={
                "Total Patients": "Number of patients arriving at triage",
                "Staff-to-Patient Ratio": "Recommended ratio of 1:5 for mass casualty events"
            },
            reference=reference
        ),
        create_formula_schema(
            formula="Bed Capacity = Available Beds × Utilization Rate",
            formula_context="Determine effective bed capacity during surge",
            variables_definition={
                "Available Beds": "Total beds in emergency department",
                "Utilization Rate": "Expected utilization percentage (typically 0.85)"
            },
            reference=reference
        ),
    ]


def create_test_actions() -> List[Dict[str, Any]]:
    """Create sample actions for testing."""
    reference = create_reference(
        document="test_document.md",
        line_range="50-100",
        node_id="test_node_3",
        node_title="Test Node"
    )
    
    return [
        create_action_schema(
            action="Calculate minimum staffing requirements for triage operations based on expected patient volume",
            who="Emergency Department Manager",
            when="Within 1 hour of Code Orange activation",
            reference=reference
        ),
        create_action_schema(
            action="Determine effective bed capacity in emergency department during mass casualty surge",
            who="Hospital Operations Manager",
            when="During initial triage phase",
            reference=reference
        ),
        create_action_schema(
            action="Set up triage stations in designated areas",
            who="Triage Team Leader",
            when="Immediately upon Code Orange declaration",
            reference=reference
        ),
    ]


def test_dependency_conversion():
    """Test dependency-to-action conversion."""
    print("\n" + "="*80)
    print("TEST 1: Dependency-to-Action Conversion")
    print("="*80)
    
    # Setup
    settings = get_settings()
    dynamic_settings = DynamicSettingsManager(settings)
    markdown_logger = TestMarkdownLogger()
    
    extractor = ExtractorAgent(
        agent_name="extractor",
        dynamic_settings=dynamic_settings,
        markdown_logger=markdown_logger
    )
    
    # Create test data
    dependencies = create_test_dependencies()
    actions = create_test_actions()
    tables = []
    
    node = {
        'id': 'test_node_1',
        'title': 'Test Node',
        'start_line': 100,
        'end_line': 150,
        'source': 'test_document.md'
    }
    
    content = """
    This is a test document about mass casualty triage.
    The emergency department needs emergency medical supplies including trauma kits.
    Budget allocation is required for triage equipment.
    Trained personnel are essential for effective triage operations.
    """
    
    print(f"\nInput:")
    print(f"  Dependencies: {len(dependencies)}")
    for dep in dependencies:
        print(f"    - {dep['dependency_title']} ({dep['category']})")
    print(f"  Existing Actions: {len(actions)}")
    print(f"  Existing Tables: {len(tables)}")
    
    # Test conversion
    try:
        result_actions, result_tables, result_dependencies = extractor._convert_dependencies_to_actions(
            actions=actions.copy(),
            dependencies=dependencies.copy(),
            tables=tables.copy(),
            content=content,
            node=node
        )
        
        print(f"\nOutput:")
        print(f"  Actions: {len(result_actions)} (added {len(result_actions) - len(actions)})")
        print(f"  Tables: {len(result_tables)} (added {len(result_tables) - len(tables)})")
        print(f"  Dependencies: {len(result_dependencies)} (should be 0)")
        
        if len(result_actions) > len(actions):
            print(f"\n  New Actions Created:")
            for action in result_actions[len(actions):]:
                print(f"    - {action.get('action', 'N/A')[:80]}...")
                print(f"      WHO: {action.get('who', 'N/A')}")
                print(f"      WHEN: {action.get('when', 'N/A')}")
        
        if result_tables:
            print(f"\n  New Tables Created:")
            for table in result_tables:
                print(f"    - {table.get('table_title', 'Untitled')}")
        
        # Show markdown output
        markdown_logger.print_output()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_formula_integration():
    """Test formula integration into actions."""
    print("\n" + "="*80)
    print("TEST 2: Formula Integration")
    print("="*80)
    
    # Setup
    settings = get_settings()
    dynamic_settings = DynamicSettingsManager(settings)
    markdown_logger = TestMarkdownLogger()
    
    extractor = ExtractorAgent(
        agent_name="extractor",
        dynamic_settings=dynamic_settings,
        markdown_logger=markdown_logger
    )
    
    # Create test data
    formulas = create_test_formulas()
    actions = create_test_actions()
    
    print(f"\nInput:")
    print(f"  Formulas: {len(formulas)}")
    for formula in formulas:
        print(f"    - {formula['formula']}")
    print(f"  Actions: {len(actions)}")
    for action in actions:
        print(f"    - {action['action'][:60]}...")
    
    # Test integration
    try:
        result_actions, result_formulas = extractor._integrate_formulas_into_actions(
            actions=actions.copy(),
            formulas=formulas.copy()
        )
        
        print(f"\nOutput:")
        print(f"  Actions: {len(result_actions)}")
        print(f"  Formulas: {len(result_formulas)} (should be 0)")
        
        # Check if any actions were updated
        updated_count = 0
        for i, (orig, new) in enumerate(zip(actions, result_actions)):
            if orig['action'] != new['action']:
                updated_count += 1
                print(f"\n  Updated Action {i+1}:")
                print(f"    Original: {orig['action'][:80]}...")
                print(f"    Updated:  {new['action'][:120]}...")
        
        print(f"\n  Actions Updated: {updated_count}")
        print(f"  Formulas Integrated: {len(formulas) - len(result_formulas)}")
        
        if result_formulas:
            print(f"\n  Unmatched Formulas:")
            for formula in result_formulas:
                print(f"    - {formula.get('formula', 'N/A')}")
        
        # Show markdown output
        markdown_logger.print_output()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("EXTRACTOR STEPS TESTER")
    print("="*80)
    print("\nThis script tests:")
    print("  1. Dependency-to-Action Conversion (Step 7)")
    print("  2. Formula Integration (Step 8)")
    print("\nNote: This requires an active LLM connection.")
    print("="*80)
    
    # Test 1: Dependency Conversion
    test1_result = test_dependency_conversion()
    
    # Test 2: Formula Integration
    test2_result = test_formula_integration()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"  Dependency Conversion: {'✅ PASSED' if test1_result else '❌ FAILED'}")
    print(f"  Formula Integration:   {'✅ PASSED' if test2_result else '❌ FAILED'}")
    print("="*80 + "\n")
    
    if test1_result and test2_result:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

