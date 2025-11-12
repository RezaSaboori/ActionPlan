# Assigner Agent - Quick Reference Guide

**Version:** 2.0 | **Status:** Production Ready ✅

---

## 🎯 Purpose

Assigns specific job positions to the `who` field of actions in crisis management plans using semantic extraction and validation against an organizational reference document.

---

## 🚀 Quick Start

```python
from agents.assigner import AssignerAgent
from config.dynamic_settings import DynamicSettingsManager

# Initialize
assigner = AssignerAgent("assigner", DynamicSettingsManager())

# Execute
result = assigner.execute({
    "prioritized_actions": actions,
    "user_config": {"level": "center", "phase": "response"},
    "tables": []
})

# Access results
assigned = result["assigned_actions"]
```

---

## 📊 Workflow

```
Input Actions → Batch Decision → Assignment → Validation → Retry (if needed) → Output
```

---

## ⚙️ Key Configuration

```bash
# Essential Settings
ASSIGNER_MODEL=gpt-oss:20b
ASSIGNER_TEMPERATURE=0.1
ASSIGNER_REFERENCE_DOC=assigner_tools/En/Assigner refrence.md
ASSIGNER_BATCH_SIZE=15
ASSIGNER_MAX_RETRIES=3
```

---

## 🔑 Key Features

### 1. Semantic Extraction
- Extracts job titles from action descriptions
- Example: "Emergency head activates..." → "Head of Emergency Department"

### 2. Three-Phase Assignment
- **Phase A:** Exact match in reference
- **Phase B:** Semantic similarity match
- **Phase C:** Escalate to supervisor

### 3. Organizational Level Awareness
- **Ministry:** Deputy Minister, Director of Crisis Management
- **University:** Dean of Health Affairs, University Chancellor
- **Center:** Hospital Director, Head of Emergency Department

### 4. Batch Processing
- Automatic for > 30 actions
- Configurable batch size (default: 15)

### 5. Retry Logic
- 3 attempts with exponential backoff (1s, 2s, 3s)
- Validation after each attempt
- Fallback to 'undefined' if all fail

---

## ✅ Validation Rules

### Rejects (Generic Terms):
❌ staff, team, personnel, department, unit, center, office, services, workers, employees, group, members, tbd, n/a

### Accepts (Specific Positions):
✅ Head of Emergency Department  
✅ Clinical Engineering Manager  
✅ Hospital Director  
✅ Deputy Minister of Health

---

## 📥 Input Format

```python
{
    "prioritized_actions": [
        {
            "action": "Activate triage protocols",
            "when": "Within 30 minutes",
            "priority_level": "immediate",
            "sources": ["Protocol v2.1"]
        }
    ],
    "user_config": {
        "level": "center|university|ministry",
        "phase": "preparedness|response",
        "subject": "war|mass_casualty|..."
    },
    "tables": []  # Pass-through
}
```

---

## 📤 Output Format

```python
{
    "assigned_actions": [
        {
            "action": "Activate triage protocols",
            "when": "Within 30 minutes",
            "priority_level": "immediate",
            "sources": ["Protocol v2.1"],
            "who": "Head of Emergency Department"  # ← Added
        }
    ],
    "tables": []  # Pass-through unchanged
}
```

---

## 🔍 Methods Overview

| Method | Purpose |
|--------|---------|
| `execute()` | Main entry point |
| `_assign_responsibilities_with_retry()` | Retry logic |
| `_assign_responsibilities()` | LLM call |
| `_assign_responsibilities_batched()` | Batch processing |
| `_validate_assignments()` | Validation check |
| `_apply_fallback_assignments()` | Fallback handler |
| `_load_reference_document()` | Load reference |

---

## 🐛 Common Issues & Solutions

### Issue: Reference Document Not Found
```bash
# Solution: Check path
ls -la assigner_tools/En/Assigner\ refrence.md
export ASSIGNER_REFERENCE_DOC="correct/path/to/reference.md"
```

### Issue: High Generic Term Rate
```bash
# Solution: Update reference or reduce temperature
export ASSIGNER_TEMPERATURE=0.05
# Or improve action descriptions with explicit job titles
```

### Issue: Batch Timeouts
```bash
# Solution: Reduce batch size
export ASSIGNER_BATCH_SIZE=10
export OLLAMA_TIMEOUT=5000
```

### Issue: Inconsistent Assignments
```bash
# Solution: Set temperature to 0
export ASSIGNER_TEMPERATURE=0.0
```

---

## 📊 Performance Metrics

| Metric | Expected Value |
|--------|---------------|
| Small batch (< 30) | 5-15 seconds total |
| Large batch (> 30) | 10-30 seconds total |
| Per action | 0.3-1.0 seconds |
| Success rate | > 95% |
| Retry rate | < 10% |

---

## 🧪 Testing

```bash
# Run all tests
pytest test_assigner_integration.py -v -s

# Run specific test
pytest test_assigner_integration.py::TestAssignerIntegration::test_explicit_job_title_preserved -v

# With coverage
pytest test_assigner_integration.py --cov=agents.assigner --cov-report=html
```

**Test Coverage:** 14 tests covering:
- Semantic extraction (3 tests)
- Organizational levels (3 tests)
- Quality & validation (3 tests)
- Validation unit tests (5 tests)

---

## 📝 Best Practices

### ✅ DO:
- Use temperature 0.1 for production
- Keep reference document updated
- Monitor validation logs
- Set batch size to 15
- Enable 3 retries

### ❌ DON'T:
- Use temperature > 0.5
- Set batch size > 30
- Disable retry logic
- Ignore validation warnings
- Use generic terms in reference

---

## 🔄 Integration with Workflow

**Position in Pipeline:**
```
Orchestrator → Analyzer → Extractor → Deduplicator → 
Selector → Timing → ⭐ ASSIGNER ⭐ → Formatter
```

**Input:** `timed_actions` from Timing Agent  
**Output:** `assigned_actions` to Formatter Agent

---

## 📖 Example Scenarios

### Scenario 1: Ministry-Level Crisis
```python
user_config = {
    "level": "ministry",
    "phase": "response",
    "subject": "national_emergency"
}
# Expected: "Deputy Minister of Health", "Director of Crisis Management"
```

### Scenario 2: Hospital Emergency
```python
user_config = {
    "level": "center",
    "phase": "response",
    "subject": "mass_casualty"
}
# Expected: "Head of Emergency Department", "Hospital Director"
```

### Scenario 3: University Preparedness
```python
user_config = {
    "level": "university",
    "phase": "preparedness",
    "subject": "pandemic"
}
# Expected: "Dean of Health Affairs", "University Chancellor"
```

---

## 🔗 Related Documentation

- **Full Documentation:** `ASSIGNER_AGENT_COMPREHENSIVE_DOCUMENTATION.md`
- **Implementation Summary:** `ASSIGNER_SEMANTIC_ENHANCEMENT_SUMMARY.md`
- **Overhaul Summary:** `ASSIGNER_OVERHAUL_SUMMARY.md`
- **Source Code:** `agents/assigner.py`
- **Prompts:** `config/prompts.py::ASSIGNER_PROMPT`
- **Settings:** `config/settings.py`

---

## 📞 Quick Troubleshooting

```python
# Debug Mode
import logging
logging.basicConfig(level=logging.DEBUG)

# Check LLM Connection
from utils.llm_client import LLMClient
client = LLMClient.create_for_agent("assigner", dynamic_settings)
response = client.generate("Test")

# Verify Reference Document
print(f"Ref doc length: {len(assigner.reference_doc)}")

# Check System Prompt
from config.prompts import get_prompt
print(f"Prompt length: {len(get_prompt('assigner'))}")

# Validate Manually
is_valid, issues = assigner._validate_assignments(actions)
print(f"Valid: {is_valid}, Issues: {issues}")
```

---

## 📈 Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.0 | Oct 2025 | Initial with RAG |
| 1.5 | Nov 2, 2025 | Direct reference lookup |
| 2.0 | Nov 12, 2025 | Semantic enhancement |

---

## 🎓 Key Concepts

### Semantic Extraction
The agent proactively searches action descriptions for job titles rather than relying solely on external assignment rules.

### Validation System
Two-level validation ensures both structural correctness and semantic quality (no generic terms).

### Hierarchical Escalation
When specific role cannot be determined, escalates to appropriate supervisor based on functional area and organizational level.

### Field Preservation
Critical guarantee: ALL original action fields preserved; ONLY `who` field modified.

---

**Status: PRODUCTION READY** ✅

For detailed information, see `ASSIGNER_AGENT_COMPREHENSIVE_DOCUMENTATION.md`

