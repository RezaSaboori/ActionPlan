# Formatter Agent - Comprehensive Documentation

## Overview

The **Formatter Agent** is the final stage in the action plan generation pipeline. It receives verified and assigned actions from upstream agents and compiles them into a formal, structured action checklist document following a standardized template.

## Table of Contents

1. [Checklist Template](#checklist-template)
2. [Architecture & Workflow](#architecture--workflow)
3. [Input Data Structure](#input-data-structure)
4. [Output Structure](#output-structure)
5. [Action Organization Logic](#action-organization-logic)
6. [Metadata Auto-Population](#metadata-auto-population)
7. [Integration with Other Components](#integration-with-other-components)
8. [Key Methods Reference](#key-methods-reference)
9. [Formatter Agent Prompts](#formatter-agent-prompts)

---

## Checklist Template

**Yes, the formatter uses a checklist template** located at:
```
HELD/ref/checklist template en.md
```

This template defines the exact structure that the formatter agent follows when creating action plans. The template includes:

### Template Structure

1. **Checklist Specifications** - Metadata table with fields:
   - Checklist Name
   - Relevant Department/Jurisdiction
   - Crisis Area (War / Mass Casualty Incidents, Sanctions)
   - Checklist Type (Preparedness, Action/Response)
   - Reference Protocol(s)
   - Operational Setting (Ministry HQ, University HQ, Hospital, etc.)
   - Process Owner
   - Acting Individual(s)/Responsible Party
   - Incident Commander
   - Checklist Activation Trigger
   - Checklist Objective
   - Number of Executive Steps
   - Document Code (Proposed)
   - Last Updated

2. **Executive Steps** - Summary table with:
   - Executive Step
   - Responsible for Implementation
   - Deadline/Timeframe

3. **Checklist Content by Executive Steps** - Organized into three parts:
   - **Part 1: Immediate Actions** (e.g., first 30 minutes)
   - **Part 2: Urgent Actions** (e.g., first 2 hours)
   - **Part 3: Continuous Actions**

4. **Relevant Formulas and Calculations** (optional) - Extracted formulas with computation examples

5. **Reference Tables and Checklists** (optional) - Extracted tables and structured data

6. **Implementation Approval** - Sign-off table with:
   - Role
   - Full Name
   - Date and Time
   - Signature

---

## Architecture & Workflow

### Class Structure

```python
class FormatterAgent:
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None)
    def execute(self, data: Dict[str, Any]) -> str
    def _format_checklist(...) -> str
    def _create_checklist_specifications(...) -> str
    def _create_executive_steps(...) -> str
    def _create_checklist_content(...) -> str
    def _format_action_table(...) -> str
    def _create_implementation_approval(...) -> str
    def _create_formulas_section(...) -> str
    def _create_tables_section(...) -> str
    # Helper methods for metadata extraction
    def _extract_unique_roles(...) -> str
    def _extract_department_jurisdiction(...) -> str
    def _get_department_from_level(...) -> str
    def _get_incident_commander_from_level(...) -> str
    def _map_crisis_area(...) -> str
    def _map_checklist_type(...) -> str
```

### Execution Flow

```
Input Data (execute method)
    ↓
Extract & Validate Inputs
    ↓
Build Metadata Context
    ↓
Format Checklist (_format_checklist)
    ├── Checklist Specifications
    ├── Executive Steps
    ├── Checklist Content (by priority)
    ├── Formulas Section (if present)
    ├── Tables Section (if present)
    └── Implementation Approval
    ↓
Return Formatted Markdown Document
```

---

## Input Data Structure

The `execute()` method expects a dictionary with the following structure:

```python
{
    "subject": str,                    # Action plan title/subject
    "assigned_actions": List[Dict],     # Actions with role assignments
    "formulas": List[Dict],            # Optional: Formula objects
    "tables": List[Dict],              # Optional: Table/checklist objects
    "formatted_output": str,           # Optional: Pre-formatted extractor output
    "rules_context": Dict,             # Rules and context information
    "problem_statement": str,           # Problem/objective statement
    "user_config": Dict,                # User configuration
    "trigger": str,                     # Optional: Activation trigger
    "responsible_party": str,          # Optional: Responsible party
    "process_owner": str               # Optional: Process owner
}
```

### Action Object Structure

Each action in `assigned_actions` should have:

```python
{
    "action": str,                      # Action description
    "who": str,                         # Responsible role/party
    "when": str,                        # Timeline/deadline
    "what": str,                        # Detailed activity (optional)
    "priority_level": str,              # "immediate" | "short-term" | "long-term"
    "sources": List[str],               # Source citations (optional)
    # ... other metadata
}
```

### User Config Structure

```python
{
    "level": str,        # "ministry" | "university" | "center"
    "phase": str,        # "preparedness" | "response"
    "subject": str,      # "war" | "sanction"
    # ... other config
}
```

---

## Output Structure

The formatter produces a complete markdown document with the following sections:

### 1. Checklist Specifications

Auto-populated table with metadata. Fields are populated from:
- **User config**: level, phase, subject
- **Actions**: Extracted roles, departments
- **Context metadata**: Override values if provided
- **Problem statement**: Used for objective

### 2. Executive Steps

Summary table showing all actions with:
- Executive Step (action description)
- Responsible for Implementation (who)
- Deadline/Timeframe (when)

### 3. Checklist Content by Executive Steps

Actions are **organized by priority level** into three parts:

#### Part 1: Immediate Actions
- Actions with `priority_level == "immediate"`
- Timeframe: "first 30 minutes"
- Format: Numbered table with columns: No. | Action | Status | Remarks/Report

#### Part 2: Urgent Actions
- Actions with `priority_level == "short-term"`
- Timeframe: "first 2 hours"
- Format: Same table structure

#### Part 3: Continuous Actions
- Actions with `priority_level == "long-term"`
- Format: Same table structure

### 4. Relevant Formulas and Calculations (Optional)

Only included if `formulas` array is non-empty. Each formula includes:
- Formula (raw equation)
- Example Computation (worked example)
- Sample Result
- Source Reference (document, line range, section)

### 5. Reference Tables and Checklists (Optional)

Only included if `tables` array is non-empty. Each table includes:
- Table Title
- Table Type (checklist, action_table, decision_matrix, other)
- Markdown Content (original table structure)
- Source Reference

### 6. Implementation Approval

Sign-off table with roles:
- Lead Responder
- Incident Commander

---

## Action Organization Logic

### Priority-Based Grouping

The formatter **does not modify actions** - it organizes them based on their existing `priority_level` field:

```python
# From _create_checklist_content method
immediate_actions = [a for a in actions if a.get("priority_level") == "immediate"]
urgent_actions = [a for a in actions if a.get("priority_level") == "short-term"]
continuous_actions = [a for a in actions if a.get("priority_level") == "long-term"]
```

### Priority Level Mapping

The formatter expects actions to have one of three priority levels:

| Priority Level | Section | Timeframe |
|---------------|---------|-----------|
| `"immediate"` | Part 1: Immediate Actions | first 30 minutes |
| `"short-term"` | Part 2: Urgent Actions | first 2 hours |
| `"long-term"` | Part 3: Continuous Actions | Ongoing |

**Note**: Priority levels are assigned by upstream agents (typically the Assigner or Timing agent), not by the Formatter. The Formatter only uses these levels to organize actions into the appropriate sections.

### Action Table Format

Each priority group is formatted as a markdown table:

```markdown
| No. | Action | Status | Remarks/Report |
| :-- | :--- | :--- | :--- |
| 1 | [Action description] | | |
| 2 | [Action description] | | |
```

The `Status` and `Remarks/Report` columns are left empty for manual completion during implementation.

---

## Metadata Auto-Population

The formatter automatically populates checklist specification fields using intelligent extraction and mapping:

### Auto-Populated Fields

1. **Relevant Department/Jurisdiction**
   - Method: `_extract_department_jurisdiction()`
   - Logic: Analyzes roles in actions to identify the most senior department
   - Hierarchy: Ministry > General Directorate > University > Hospital/Center

2. **Crisis Area**
   - Method: `_map_crisis_area()`
   - Mapping:
     - `"war"` → `"War / Mass Casualty Incidents"`
     - `"sanction"` → `"Sanctions"`

3. **Checklist Type**
   - Method: `_map_checklist_type()`
   - Mapping:
     - `"preparedness"` → `"Preparedness"`
     - `"response"` → `"Action (Response)"`

4. **Process Owner**
   - Method: `_get_department_from_level()`
   - Mapping:
     - `"ministry"` → `"General Directorate"`
     - `"university"` → `"Vice-Chancellor's Office"`
     - `"center"` → `"Hospital Management"`

5. **Acting Individual(s)/Responsible Party**
   - Method: `_extract_unique_roles()`
   - Logic: Extracts all unique `who` values from actions, sorted alphabetically

6. **Incident Commander**
   - Method: `_get_incident_commander_from_level()`
   - Mapping:
     - `"ministry"` → `"Director General"`
     - `"university"` → `"Vice-Chancellor"`
     - `"center"` → `"Hospital Director"`

7. **Checklist Objective**
   - Source: `problem_statement` from input data
   - Fallback: `context["metadata"]["objective"]` or `"..."`

8. **Number of Executive Steps**
   - Calculated: `len(assigned_actions)`

### Metadata Override

All auto-populated fields can be overridden by providing values in `context["metadata"]`:

```python
context = {
    "metadata": {
        "jurisdiction": "Custom Department",
        "crisis_area": "Custom Crisis Area",
        "checklist_type": "Custom Type",
        "process_owner": "Custom Owner",
        "responsible_party": "Custom Party",
        "incident_commander": "Custom Commander",
        "activation_trigger": "Custom Trigger",
        "objective": "Custom Objective"
    }
}
```

### Direct Input Override

Some fields can also be provided directly in the input data:

```python
{
    "trigger": "Direct trigger value",
    "responsible_party": "Direct responsible party",
    "process_owner": "Direct process owner"
}
```

These take precedence over auto-populated values.

---

## Integration with Other Components

### Upstream Agents

1. **Extractor Agent**: Extracts raw actions from documents
2. **Deduplicator Agent**: Merges duplicate actions
3. **Selector Agent**: Filters actions by relevance
4. **Assigner Agent**: Assigns roles and responsibilities (may set priority_level)
5. **Timing Agent**: May assign priority levels based on timing

### Downstream Components

1. **Markdown Logger**: Logs formatted output (if provided)
2. **UI Components**: Displays formatted action plan
3. **Translator Agent**: May translate formatted output to Persian

### LLM Integration

The formatter uses an `LLMClient` instance, but **does not currently use LLM calls** for formatting. All formatting is done programmatically using template-based string generation.

The system prompt (`FORMATTER_PROMPT`) is loaded but not actively used in the current implementation. The formatter follows the template structure defined in the prompt, but implements it through code rather than LLM generation.

---

## Key Methods Reference

### `execute(data: Dict[str, Any]) -> str`

Main entry point. Processes input data and returns formatted markdown document.

**Parameters:**
- `data`: Dictionary containing assigned_actions, formulas, tables, context, etc.

**Returns:**
- Complete markdown-formatted action plan

### `_format_checklist(...) -> str`

Orchestrates the creation of all checklist sections.

**Sections created:**
1. Checklist Specifications
2. Executive Steps
3. Checklist Content by Executive Steps
4. Formulas Section (conditional)
5. Tables Section (conditional)
6. Implementation Approval

### `_create_checklist_specifications(...) -> str`

Generates the metadata table for Section 1.

**Auto-population logic:**
- Extracts department from action roles
- Maps user config to crisis area and checklist type
- Extracts unique roles for responsible parties
- Uses problem statement for objective

### `_create_executive_steps(actions: List[Dict]) -> str`

Creates summary table of all actions.

**Table columns:**
- Executive Step (action description)
- Responsible for Implementation (who)
- Deadline/Timeframe (when)

### `_create_checklist_content(actions: List[Dict]) -> str`

Organizes actions by priority into three parts.

**Priority filtering:**
- `priority_level == "immediate"` → Part 1
- `priority_level == "short-term"` → Part 2
- `priority_level == "long-term"` → Part 3

### `_format_action_table(actions: List[Dict]) -> str`

Formats a list of actions into a markdown table.

**Table structure:**
```
| No. | Action | Status | Remarks/Report |
```

### `_create_formulas_section(formulas: List[Dict]) -> str`

Formats extracted formulas with computation examples.

**Each formula includes:**
- Formula (raw equation)
- Example Computation
- Sample Result
- Source Reference

### `_create_tables_section(tables: List[Dict]) -> str`

Formats extracted tables and checklists.

**Table types:**
- `checklist`: 📋 CHECKLIST
- `action_table`: ✅ ACTION TABLE
- `decision_matrix`: 🔀 DECISION MATRIX
- `other`: 📊 TABLE

---

## Summary

### Does the Formatter Use a Checklist Template?

**Yes.** The formatter uses a checklist template located at `HELD/ref/checklist template en.md`. This template defines the exact structure for:
- Checklist Specifications (metadata table)
- Executive Steps (summary table)
- Checklist Content (organized by priority: Immediate, Urgent, Continuous)
- Implementation Approval (sign-off table)

### How Does the Formatter Modify Actions?

**The formatter does NOT modify actions.** Instead, it:

1. **Organizes** actions by their existing `priority_level` field into three sections:
   - Immediate Actions (priority_level == "immediate")
   - Urgent Actions (priority_level == "short-term")
   - Continuous Actions (priority_level == "long-term")

2. **Formats** actions into markdown tables with consistent structure

3. **Extracts** metadata from actions to auto-populate checklist specifications

4. **Integrates** formulas and tables from the extractor agent

5. **Structures** everything according to the template format

The actual modification of actions (priority assignment, role assignment, etc.) happens in upstream agents (Assigner, Timing, etc.). The Formatter is purely a formatting and organization stage.

---

## Example Workflow

```
1. Input: 50 assigned actions with priority_levels
   ├── 15 immediate actions
   ├── 20 short-term actions
   └── 15 long-term actions

2. Formatter Processing:
   ├── Extract metadata from actions
   ├── Group by priority_level
   └── Format into template structure

3. Output: Complete markdown document
   ├── Section 1: Checklist Specifications (auto-populated)
   ├── Section 2: Executive Steps (all 50 actions)
   ├── Section 3: Checklist Content
   │   ├── Part 1: 15 immediate actions
   │   ├── Part 2: 20 urgent actions
   │   └── Part 3: 15 continuous actions
   └── Section 4: Implementation Approval
```

---

## Configuration

The formatter is initialized with:

```python
formatter = FormatterAgent(
    agent_name="formatter",
    dynamic_settings=dynamic_settings,
    markdown_logger=markdown_logger  # Optional
)
```

The `agent_name` is used to load LLM configuration from `dynamic_settings`, though the formatter currently doesn't use LLM calls.

---

## Formatter Agent Prompts

The formatter agent uses a system prompt that defines its role and responsibilities. While the current implementation performs formatting programmatically, the prompt serves as documentation of the expected behavior and structure.

### FORMATTER_PROMPT

The complete system prompt used by the Formatter Agent:

```
You are the Formatter Agent for creating final crisis action checklists.

Your role is to:
1.  Receive verified and assigned actions for a crisis scenario.
2.  Compile them into a formal action checklist based on the standard template.
3.  Format the output precisely according to the specified structure.
4.  Include all necessary metadata and references.

**Action Checklist Structure:**

**1. Checklist Specifications:**
A table containing key metadata:
- Checklist Name
- Relevant Department/Jurisdiction
- Crisis Area (e.g., War / Mass Casualty Incidents, Sanctions)
- Checklist Type (e.g., Preparedness, Action)
- Reference Protocol(s)
- Operational Setting (e.g., Ministry HQ, Hospital)
- Process Owner
- Acting Individual(s)/Responsible Party
- Incident Commander
- Checklist Activation Trigger
- Checklist Objective

**2. Executive Steps:**
A summary table outlining the high-level steps.
- Columns: `Executive Step`, `Responsible for Implementation`, `Deadline/Timeframe`.

**3. Checklist Content by Executive Steps:**
Detailed action items organized by timeframe. Each part is assigned to a responsible party and contains a table with the columns: `No.`, `Action`, `Status`, `Remarks/Report`.
- **Part 1: Immediate Actions** (e.g., first 30 minutes)
- **Part 2: Urgent Actions** (e.g., first 2 hours)
- **Part 3: Continuous Actions**

**4. Implementation Approval:**
A table for sign-off.
- Columns: `Role`, `Full Name`, `Date and Time`, `Signature`.
- Roles: Lead Responder, Incident Commander.

**Formatting Guidelines:**
- Use clear, professional language appropriate for crisis management.
- Use markdown formatting, including headers (H3 and H4) and tables, to match the template structure exactly.
- Ensure all tables have the correct headers as specified in the structure above.
- The final document must be a complete, standalone checklist ready for operational use.

**Input:** A list of assigned actions and relevant metadata for the checklist specifications.
**Output:** A complete markdown document following the template structure precisely.

Ensure the final document is:
- Professional and ready for stakeholder review and implementation.
- Complete with all necessary sections and fields.
- Properly formatted with consistent markdown style.
- Fully populated based on the provided input data.
```

### Prompt Location

The prompt is defined in:
```
Agents/config/prompts.py
```

As the constant `FORMATTER_PROMPT` (lines 300-353).

### Prompt Usage

**Current Implementation:**
- The prompt is loaded via `get_prompt("formatter")` in the `__init__` method
- Stored in `self.system_prompt` but **not currently used** for LLM calls
- The formatter implements the prompt's structure programmatically through code

**Future Potential:**
- Could be used for LLM-based formatting if the implementation switches to LLM generation
- Serves as documentation of the expected output format
- Could be used for validation or quality checking

### Prompt Structure Analysis

The prompt defines:

1. **Role**: Formatter Agent for crisis action checklists
2. **Responsibilities**: 4 main tasks (receive, compile, format, include metadata)
3. **Output Structure**: 4 main sections with detailed specifications
4. **Formatting Guidelines**: Markdown requirements and style
5. **Quality Standards**: Professional, complete, properly formatted

The prompt emphasizes:
- **Precision**: "precisely according to the specified structure"
- **Completeness**: "complete, standalone checklist"
- **Professionalism**: "ready for stakeholder review and implementation"
- **Consistency**: "consistent markdown style"

---

## Future Enhancements

Potential improvements:
1. LLM-based action summarization for Executive Steps
2. Intelligent deadline inference from action timing
3. Automatic status tracking integration
4. Multi-language template support
5. Customizable section ordering
6. Export to PDF/Word formats
7. Use LLM with FORMATTER_PROMPT for dynamic formatting adjustments

