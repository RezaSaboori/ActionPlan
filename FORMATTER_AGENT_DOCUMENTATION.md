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

2. **Checklist Content by Responsible Actor** - Organized by actor/role with:
   - Actions grouped by the `who` field (responsible party)
   - Actions sorted chronologically within each actor section
   - Integrated appendices per actor with inline references
   - Action table columns: No. | Action | Timeline | Status | Remarks

3. **Relevant Formulas and Calculations** (optional) - Extracted formulas with computation examples

4. **Reference Tables and Checklists** (optional) - General reference tables not specific to actors

5. **Implementation Approval** - Sign-off table with:
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
    def _create_checklist_content(...) -> str
    def _format_action_table(...) -> str
    def _format_actor_section(...) -> str
    def _create_implementation_approval(...) -> str
    def _create_formulas_section(...) -> str
    def _create_tables_section(...) -> str
    
    # Data preparation methods
    def _group_actions_by_actor(...) -> Dict[str, List[Dict]]
    def _parse_timing(...) -> tuple
    def _sort_actions_by_timing(...) -> List[Dict]
    def _extract_actions_from_tables(...) -> List[Dict]
    def _infer_actor_from_table(...) -> str
    def _find_column_index(...) -> int
    
    # Appendix system methods
    def _identify_reference_tables(...) -> Dict[str, List[Dict]]
    def _generate_appendix_title(...) -> str
    def _format_appendix(...) -> str
    def _link_actions_to_appendices(...) -> Dict[int, List[str]]
    def _table_matches_action(...) -> bool
    def _match_table_to_actors_by_keywords(...) -> List[str]
    
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
    ├── Checklist Content (by actor)
    │   ├── Extract actions from tables
    │   ├── Group actions by actor (who field)
    │   ├── Sort actions by timing within each actor
    │   ├── Identify reference tables per actor
    │   └── Format each actor section with appendices
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
    "action": str,                      # Action description (comprehensive)
    "who": str,                         # Responsible role/party
    "when": str,                        # Timeline/deadline
    "reference": Dict,                  # Source reference with document, line_range, node info
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

### 2. Checklist Content by Responsible Actor

Actions are **organized by responsible actor** (the `who` field), with each actor section containing:

#### Actor Section Structure
- **Section Header**: Actor/role name (e.g., "Head of ICU", "Emergency Response Coordinator")
- **Actions Table**: Numbered table with columns: No. | Action | Timeline | Status | Remarks
- **Actions Sorting**: Within each actor, actions are sorted chronologically by:
  1. Start time (parsed from `when` field)
  2. Priority weight from timing text
- **Appendices**: Integrated per actor with:
  - Appendix ID (A, B, C... reset per actor)
  - Table/checklist content
  - Source reference
  - Related action numbers
- **Inline References**: Actions reference appendices with "(See Appendix A)" notation

#### Special Handling
- **Unassigned Section**: Actions with missing/undefined `who` field are grouped under "Unassigned"
- **Actor Ordering**: Actors are sorted alphabetically, with "Unassigned" always last
- **Table Actions**: Actions extracted from action tables are merged with main actions

### 3. Relevant Formulas and Calculations (Optional)

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

### Actor-Based Grouping

The formatter **organizes actions by responsible actor** using the `who` field:

```python
# From _create_checklist_content method
# Step 1: Extract actions from action tables
table_actions = self._extract_actions_from_tables(tables)

# Step 2: Merge with main actions
all_actions = actions + table_actions

# Step 3: Group by actor
actions_by_actor = self._group_actions_by_actor(all_actions)

# Step 4: Sort within each actor group
for actor in actions_by_actor:
    actions_by_actor[actor] = self._sort_actions_by_timing(actions_by_actor[actor])
```

### Actor Assignment Rules

1. **Primary Source**: Use the `who` field from the action
2. **Fallback Values**: If `who` is missing, empty, or "TBD" → assign to "Unassigned"
3. **Table Actions**: Infer actor from table context/title if not explicitly specified

### Timing-Based Sorting

Within each actor section, actions are sorted chronologically:

```python
def _parse_timing(when: str) -> tuple:
    # Returns: (start_minutes, priority_weight)
    # Examples:
    # "0-30min" → (0, 1)
    # "30min-2hr" → (30, 2)
    # "Immediate" → (0, 1)
    # "Continuous" → (0, 3)
```

**Sort Order**:
1. Start time in minutes (ascending)
2. Priority weight from timing text

### Action Table Format

Actions are formatted as markdown tables with timeline column:

```markdown
| No. | Action | Timeline | Status | Remarks |
| :-- | :--- | :--- | :--- | :--- |
| 1 | Activate protocol (See Appendix A) | Immediate (0-30min) | | |
| 2 | Coordinate teams | Immediate (0-30min) | | |
```

The `Timeline` column shows the `when` field value. `Status` and `Remarks` columns are left empty for manual completion during implementation.

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

8. **Number of Actions**
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
4. **Assigner Agent**: Assigns roles and responsibilities
5. **Timing Agent**: Assigns timing information and may influence sorting

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
2. Checklist Content by Responsible Actor
3. Formulas Section (conditional)
4. Tables Section (conditional)
5. Implementation Approval

### `_create_checklist_specifications(...) -> str`

Generates the metadata table for Section 1.

**Auto-population logic:**
- Extracts department from action roles
- Maps user config to crisis area and checklist type
- Extracts unique roles for responsible parties
- Uses problem statement for objective

### `_create_checklist_content(actions: List[Dict], tables: List[Dict]) -> str`

Organizes actions by responsible actor with integrated appendices.

**Processing steps:**
1. Extract actions from action tables
2. Merge with main actions
3. Group by actor (`who` field)
4. Sort actions by timing within each actor
5. Identify reference tables for each actor
6. Format each actor section with appendices

**Returns:** Complete actor-based checklist content

### `_format_actor_section(actor: str, actions: List[Dict], appendices: List[Dict]) -> str`

Formats a complete section for one actor.

**Components:**
- Actor header
- Actions table with appendix references
- Integrated appendices (A, B, C...)

### `_format_action_table(actions: List[Dict], appendix_refs: Dict[int, str]) -> str`

Formats a list of actions into a markdown table with timeline and appendix references.

**Table structure:**
```
| No. | Action | Timeline | Status | Remarks |
```

**Parameters:**
- `actions`: List of action dictionaries
- `appendix_refs`: Optional mapping of action index to appendix reference text

### `_group_actions_by_actor(actions: List[Dict]) -> Dict[str, List[Dict]]`

Groups actions by the `who` field.

**Returns:** Dictionary mapping actor names to their actions
**Special handling:** Missing/empty `who` → "Unassigned"

### `_parse_timing(when: str) -> tuple`

Parses timing string to extract start time and priority weight.

**Returns:** `(start_minutes, priority_weight)`
**Examples:**
- "0-30min" → (0, 1)
- "Immediate" → (0, 1)
- "Continuous" → (0, 3)

### `_sort_actions_by_timing(actions: List[Dict]) -> List[Dict]`

Sorts actions chronologically by start time and priority.

**Sort criteria:**
1. Start time in minutes
2. Priority level
3. Priority weight

### `_extract_actions_from_tables(tables: List[Dict]) -> List[Dict]`

Extracts actions from tables marked as `action_table`.

**Processing:**
- Identifies action columns
- Infers actor from table context
- Returns list of action dictionaries

### `_identify_reference_tables(tables: List[Dict], actions_by_actor: Dict) -> Dict[str, List[Dict]]`

Maps reference tables to relevant actors.

**Returns:** Dictionary of actor names to their reference tables

### `_format_appendix(appendix: Dict, appendix_id: str, related_action_numbers: List[int]) -> str`

Formats an appendix with content and metadata.

**Components:**
- Appendix header with ID
- Table content
- Source reference
- Related action numbers

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

**Yes.** The formatter uses a checklist template located at `HELD/ref/checklist template en.md`. This template defines the structure for:
- Checklist Specifications (metadata table)
- Checklist Content (organized by responsible actor)
- Implementation Approval (sign-off table)

### How Does the Formatter Organize Actions?

**The formatter does NOT modify actions.** Instead, it:

1. **Groups** actions by responsible actor using the `who` field:
   - Each actor gets their own section
   - Actions with missing/undefined `who` → "Unassigned" section
   - Actors sorted alphabetically (Unassigned always last)

2. **Sorts** actions chronologically within each actor section:
   - Primary: Start time parsed from `when` field
   - Secondary: Priority weight derived from `when` field text

3. **Extracts** actions from action tables and merges with main actions

4. **Integrates** appendices per actor:
   - Reference tables mapped to relevant actors
   - Appendices numbered A, B, C... (reset per actor)
   - Inline references in action text

5. **Formats** actions into markdown tables with Timeline column

6. **Extracts** metadata from actions to auto-populate checklist specifications

7. **Structures** everything according to the template format

The actual modification of actions (priority assignment, role assignment, etc.) happens in upstream agents (Assigner, Timing, etc.). The Formatter is purely a formatting and organization stage.

---

## Example Workflow

```
1. Input: 50 assigned actions + 5 tables
   ├── Actions assigned to various actors
   ├── 2 action tables
   └── 3 reference tables

2. Formatter Processing:
   ├── Extract 10 actions from action tables
   ├── Merge with 50 main actions (total: 60)
   ├── Group by actor:
   │   ├── Head of ICU: 15 actions
   │   ├── Emergency Response Coordinator: 20 actions
   │   ├── Surgical Team Lead: 12 actions
   │   ├── Hospital Director: 8 actions
   │   └── Unassigned: 5 actions
   ├── Sort each actor's actions chronologically
   ├── Map reference tables to actors
   └── Format into template structure

3. Output: Complete markdown document
   ├── Section 1: Checklist Specifications (auto-populated)
   ├── Section 2: Checklist Content by Responsible Actor
   │   ├── Head of ICU (15 actions, 1 appendix)
   │   ├── Emergency Response Coordinator (20 actions, 2 appendices)
   │   ├── Hospital Director (8 actions, 0 appendices)
   │   ├── Surgical Team Lead (12 actions, 1 appendix)
   │   └── Unassigned (5 actions, 0 appendices)
   ├── Section 3: Relevant Formulas (if present)
   ├── Section 4: Reference Tables (general tables)
   └── Section 5: Implementation Approval
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

## Example Output Format

Here's an example of the new actor-based checklist structure:

```markdown
### **1. Checklist Specifications**

| Field | Description |
| :--- | :--- |
| **Checklist Name:** | Hospital Mass Casualty Response Plan |
| **Relevant Department/Jurisdiction:** | Health Center/Hospital |
| **Crisis Area:** | War / Mass Casualty Incidents |
| **Checklist Type:** | Action (Response) |
| **Process Owner:** | Hospital Management |
| **Acting Individual(s)/Responsible Party:** | Emergency Response Coordinator, Head of ICU, Surgical Team Lead |
| **Incident Commander:** | Hospital Director |
| **Checklist Objective:** | Establish immediate response protocols for mass casualty incidents |
| **Number of Actions:** | 12 |

---

### **2. Checklist Content by Responsible Actor**

### Emergency Response Coordinator

| No. | Action | Timeline | Status | Remarks |
|-----|--------|----------|--------|---------|
| 1   | Activate emergency response protocol | Immediate (0-10min) | | |
| 2   | Establish command center | Immediate (0-30min) | | |
| 3   | Contact external agencies (See Appendix A) | Immediate (10-30min) | | |
| 4   | Coordinate with triage team | Short-term (30min-1hr) | | |

#### Appendix A: External Agency Contact List

| Agency | Contact Person | Phone | Email |
|--------|---------------|-------|-------|
| Fire Department | Chief Johnson | 555-0100 | johnson@fire.gov |
| Police Department | Captain Smith | 555-0200 | smith@police.gov |

**Reference**: Emergency Response Manual, Appendix C (lines 45-60)
**Related Actions**: #3

---

### Head of ICU

| No. | Action | Timeline | Status | Remarks |
|-----|--------|----------|--------|---------|
| 1   | Activate ICU emergency protocol (See Appendix A) | Immediate (0-30min) | | |
| 2   | Prepare isolation rooms | Immediate (0-30min) | | |
| 3   | Coordinate with surgical teams | Immediate (30min-1hr) | | |
| 4   | Review patient triage assignments | Short-term (1-2hr) | | |

#### Appendix A: ICU Emergency Activation Checklist

- [ ] Check ventilator availability
- [ ] Verify medication stock levels
- [ ] Alert ICU nursing staff
- [ ] Prepare emergency equipment

**Reference**: ICU Protocol Manual, Section 4.2 (lines 120-145)
**Related Actions**: #1

---

### Surgical Team Lead

| No. | Action | Timeline | Status | Remarks |
|-----|--------|----------|--------|---------|
| 1   | Alert surgical staff | Immediate (0-15min) | | |
| 2   | Prepare operating rooms | Immediate (15-30min) | | |
| 3   | Coordinate with blood bank | Immediate (30min-1hr) | | |
| 4   | Review surgical triage criteria (See Appendix A) | Short-term (1-2hr) | | |

#### Appendix A: Surgical Triage Priority Matrix

| Priority | Condition | Action |
|----------|-----------|--------|
| P1 | Life-threatening, immediate surgery | Operate within 1 hour |
| P2 | Urgent surgery required | Operate within 2-4 hours |
| P3 | Surgery can be delayed | Schedule after P1/P2 |

**Reference**: Surgical Protocol Guide, Table 3.1 (lines 78-95)
**Related Actions**: #4

---

### **3. Implementation Approval**

| Role | Full Name | Date and Time | Signature |
| :--- | :--- | :--- | :--- |
| **Lead Responder:** | ... | ... | ... |
| **Incident Commander:** | ... | ... | ... |
```

---

## Future Enhancements

Potential improvements:
1. Enhanced appendix matching using semantic similarity
2. Intelligent deadline inference from action timing
3. Automatic status tracking integration
4. Multi-language template support
5. Customizable actor section ordering
6. Export to PDF/Word formats
7. Use LLM with FORMATTER_PROMPT for dynamic formatting adjustments
8. Smart detection of action dependencies across actors
9. Visual timeline generation for actor schedules
10. Automated conflict detection for resource allocation

