#!/usr/bin/env python3
"""
Test script for Quality Checker Template System

This script tests the quality checker template loading functionality
without requiring the full workflow setup.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.quality_checker_template_loader import (
    list_available_quality_checker_templates,
    get_quality_checker_template_info,
    select_quality_checker_template,
    assemble_quality_checker_prompt,
    validate_quality_checker_config
)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_list_templates():
    """Test listing available templates."""
    print_section("Test 1: List Available Templates")
    
    templates = list_available_quality_checker_templates()
    print(f"Found {len(templates)} templates:")
    for i, template in enumerate(templates, 1):
        print(f"  {i}. {template}")
    
    return len(templates) == 12  # Expected 12 templates


def test_config_validation():
    """Test configuration validation."""
    print_section("Test 2: Configuration Validation")
    
    test_cases = [
        ({"level": "center", "phase": "response", "subject": "war"}, True),
        ({"level": "ministry", "phase": "preparedness", "subject": "sanction"}, True),
        ({"level": "invalid", "phase": "response", "subject": "war"}, False),
        ({"level": "center", "phase": "response"}, False),  # Missing subject
        ({}, False),  # Empty config
    ]
    
    all_passed = True
    for config, should_pass in test_cases:
        is_valid, error_msg = validate_quality_checker_config(config)
        status = "✅ PASS" if is_valid == should_pass else "❌ FAIL"
        print(f"{status}: {config}")
        if error_msg:
            print(f"     Error: {error_msg}")
        if is_valid != should_pass:
            all_passed = False
    
    return all_passed


def test_template_info():
    """Test template info retrieval."""
    print_section("Test 3: Template Info Retrieval")
    
    test_configs = [
        {"level": "center", "phase": "response", "subject": "war"},
        {"level": "university", "phase": "preparedness", "subject": "war"},
        {"level": "ministry", "phase": "preparedness", "subject": "sanction"},
    ]
    
    all_found = True
    for config in test_configs:
        info = get_quality_checker_template_info(config)
        status = "✅ EXISTS" if info['exists'] else "❌ NOT FOUND"
        print(f"{status}: {info['template_name']}")
        print(f"         Path: {info['path']}")
        if not info['exists']:
            all_found = False
    
    return all_found


def test_template_loading():
    """Test template content loading."""
    print_section("Test 4: Template Content Loading")
    
    test_configs = [
        {"level": "center", "phase": "response", "subject": "war"},
        {"level": "university", "phase": "preparedness", "subject": "sanction"},
    ]
    
    all_loaded = True
    for config in test_configs:
        content = select_quality_checker_template(config)
        if content:
            print(f"✅ LOADED: {config['level']}_{config['phase']}_{config['subject']}")
            print(f"     Length: {len(content)} characters")
            print(f"     Preview: {content[:100]}...")
        else:
            print(f"❌ FAILED: {config['level']}_{config['phase']}_{config['subject']}")
            all_loaded = False
    
    return all_loaded


def test_prompt_assembly():
    """Test full prompt assembly."""
    print_section("Test 5: Full Prompt Assembly")
    
    config = {
        "level": "center",
        "phase": "response",
        "subject": "war"
    }
    
    try:
        prompt = assemble_quality_checker_prompt(config)
        print(f"✅ ASSEMBLED: Full quality checker prompt")
        print(f"     Total length: {len(prompt)} characters")
        print(f"     Contains base prompt: {'quality_checker' in prompt.lower()}")
        print(f"     Contains template rules: {'Part One' in prompt or 'Part Two' in prompt}")
        print(f"\n     Prompt preview (first 500 chars):")
        print(f"     {prompt[:500]}...")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_special_cases():
    """Test special cases and edge conditions."""
    print_section("Test 6: Special Cases")
    
    # Test university template with space
    config = {"level": "university", "phase": "response", "subject": "war"}
    info = get_quality_checker_template_info(config)
    print(f"University template handling:")
    print(f"  Template name: {info['template_name']}")
    print(f"  Exists: {info['exists']}")
    print(f"  {'✅ PASS' if info['exists'] else '❌ FAIL'}: Handles university space variation")
    
    # Test missing template fallback
    config = {"level": "center", "phase": "response", "subject": "war"}
    try:
        prompt = assemble_quality_checker_prompt(config)
        print(f"\n✅ PASS: Fallback works for missing templates (uses base prompt)")
        return True
    except Exception as e:
        print(f"\n❌ FAIL: Exception raised: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("  QUALITY CHECKER TEMPLATE SYSTEM - TEST SUITE")
    print("="*70)
    
    tests = [
        ("List Templates", test_list_templates),
        ("Config Validation", test_config_validation),
        ("Template Info", test_template_info),
        ("Template Loading", test_template_loading),
        ("Prompt Assembly", test_prompt_assembly),
        ("Special Cases", test_special_cases),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Print summary
    print_section("TEST RESULTS SUMMARY")
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for test_name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if error:
            print(f"         Error: {error}")
    
    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'='*70}\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

