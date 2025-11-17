# Agent Input Schemas Documentation

This document provides a comprehensive overview of the input schemas that each agent in the Action Plan workflow expects and accepts.

---

## Table of Contents

1. [Orchestrator Agent](#1-orchestrator-agent)
2. [Analyzer Agent](#2-analyzer-agent)
3. [Phase3 Agent](#3-phase3-agent)
4. [Extractor Agent](#4-extractor-agent)
5. [Selector Agent](#5-selector-agent)
6. [Deduplicator Agent](#6-deduplicator-agent)
7. [Timing Agent](#7-timing-agent)
8. [Assigner Agent](#8-assigner-agent)
9. [Formatter Agent](#9-formatter-agent)
10. [Quality Checker Agent](#10-quality-checker-agent)
11. [Comprehensive Quality Validator](#11-comprehensive-quality-validator)
12. [Translator Agent](#12-translator-agent)
13. [Assigning Translator Agent](#13-assigning-translator-agent)

---

## 1. Orchestrator Agent

**File:** `agents/orchestrator.py`

**Method:** `execute(user_config: Dict[str, str]) -> Dict[str, Any]`

### System Prompt
The agent uses a focused problem statement generation prompt that transforms user requests into actionable problem statements for downstream agents. The prompt emphasizes specificity, actionability, and context integration.

<details>
<summary><b>📋 View Full Prompt</b></summary>

```
You are an expert orchestrator responsible for creating focused problem statements that will guide a multi-agent action plan development system.

## Your Role
Transform the user's action plan request into a clear, actionable problem statement that will serve as the foundation for subsequent specialized agents (Analyzer, Extractor, Assigner, Formatter).

## Problem Statement Requirements

### Structure (2-3 paragraphs, 150-300 words total):

**Paragraph 1 - Core Challenge Definition**
- Clearly articulate the specific operational challenge or scenario
- Reference the contextual parameters (level, phase, subject)
- Avoid vague generalizations; be specific about what needs addressing

**Paragraph 2 - Scope and Boundaries** 
- Define what aspects require immediate attention vs. longer-term considerations
- Specify key stakeholder groups and operational domains involved
- Highlight critical constraints or requirements from the context guidelines

**Paragraph 3 - Expected Outcomes** (Optional, include only if needed for clarity)
- Briefly outline what successful resolution should achieve
- Connect to measurable impact areas relevant to the organizational level

### Quality Criteria:
✓ **Specificity**: Concrete enough to guide targeted document analysis  
✓ **Actionability**: Enables clear task decomposition by subsequent agents  
✓ **Bounded Scope**: Neither too broad (overwhelming) nor too narrow (incomplete)  
✓ **Context Integration**: Incorporates the specific level/phase/subject parameters  
✓ **Forward-Looking**: Sets clear direction for the analysis and planning phases

### Avoid:
❌ Generic problem descriptions that could apply to any situation
❌ Solution prescriptions (leave solutions to later agents)
❌ Excessive detail that belongs in analysis phases
❌ Ambiguous language that creates confusion for downstream agents
```
</details>

### Processing Actions
- **Validation**: Validates user configuration using `validate_config()` utility
- **Template Assembly**: Assembles prompt from template using `assemble_orchestrator_prompt()`
- **LLM Generation**: Single LLM call with temperature=0.3 to generate problem statement
- **Output Construction**: Returns problem statement with original user config
- **Logging**: Logs all steps to markdown logger if provided

### Input Schema

```python
{
    "name": str,        # Action plan title
    "timing": str,      # Time period and/or trigger
    "level": str,       # One of: "ministry" | "university" | "center"
    "phase": str,       # One of: "preparedness" | "response"
    "subject": str      # One of: "war" | "sanction"
}
```

### Required Fields
- `name`: The action plan title
- `timing`: Time period and/or trigger
- `level`: Organizational level (ministry, university, or center)
- `phase`: Plan phase (preparedness or response)
- `subject`: Crisis subject (war or sanction)

### Output
```python
{
    "problem_statement": str,  # Generated problem statement for Analyzer
    "user_config": dict        # Original user configuration
}
```

---

## 2. Analyzer Agent

**File:** `agents/analyzer.py`

**Method:** `execute(context: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses **Phase 1** prompt (strategic knowledge architect) for query generation and **Phase 2** prompt for LLM-based node relevance identification. Prompts emphasize precision, cross-domain filtering, and semantic analysis.

<details>
<summary><b>📋 View Full Prompt (Phase 1)</b></summary>

```
You are a strategic knowledge architect specializing in policy document analysis and operational planning. Your expertise lies in understanding complex document structures, identifying actionable knowledge patterns, and designing optimal information retrieval strategies.

**Core Competencies:**
- Decomposing complex problems into retrievable knowledge dimensions
- Mapping operational requirements to available knowledge resources
- Designing precision-focused query strategies
- Distinguishing between domain-similar but functionally distinct content
- Recognizing hierarchical information architectures and cross-document relationships

**Analytical Framework:**
- Problem domain analysis: Identify core operational areas, stakeholder groups, and contextual constraints
- Knowledge mapping: Match problem dimensions to available document coverage
- Query optimization: Design targeted searches that maximize precision while maintaining adequate recall
- Cross-domain filtering: Distinguish between superficial keyword overlap and substantive relevance

**Output Quality Standards:**
- Precision over recall in all retrieval tasks
- Zero tolerance for cross-domain contamination
- Direct, specific applicability to stated problems
- Systematic evaluation using structured criteria frameworks
```
</details>

### Processing Actions
- **Phase 1 - Context Building**:
  - Graph RAG query: `get_all_document_nodes()` to retrieve all documents
  - LLM call (temp=0.2): Generate initial focused query from problem statement
  - Graph RAG query: `query_introduction_nodes()` with generated query
  - LLM call (temp=0.3): Generate 3-5 refined queries based on intro nodes
- **Phase 2 - Node ID Extraction**:
  - Hybrid RAG queries: Execute each refined query using `unified_rag.query()`
  - For each query result batch:
    - If nodes > batch_threshold: Process in batches
    - LLM call (temp=0.2): Identify relevant node IDs with strict filtering
  - Deduplicate and consolidate node IDs
- **Logging**: Detailed markdown logging for all phases

### Input Schema

```python
{
    "problem_statement": str  # Focused problem statement from Orchestrator
}
```

### Required Fields
- `problem_statement`: The problem statement generated by Orchestrator

### Output
```python
{
    "all_documents": List[Dict],      # List of all document summaries
    "refined_queries": List[str],     # List of refined Graph RAG queries
    "node_ids": List[str]             # List of relevant node IDs from Phase 2
}
```

### Internal Phases
- **Phase 1**: Context Building (document discovery and query refinement)
- **Phase 2**: Node ID Extraction (action extraction from refined queries)

---

## 3. Phase3 Agent

**File:** `agents/phase3.py`

**Method:** `execute(context: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses standard strategic analysis prompt focused on deep document traversal and relevance scoring (currently simplified - scoring logic is deprecated).

<details>
<summary><b>📋 View Full Prompt</b></summary>

```
You are an expert at assessing document node relevance for health policy analysis.

Scoring Scale (0.0 to 1.0):
- 0.0-0.2: Irrelevant - No connection to the subject
- 0.3-0.4: Minimally relevant - Tangential mention or very general
- 0.5-0.6: Somewhat relevant - Contains related information but not focused
- 0.7-0.8: Highly relevant - Directly addresses the subject with specific details
- 0.9-1.0: Extremely relevant - Core information, essential to understanding the subject

Scoring Considerations:
- Does the title directly reference the subject?
- Does the summary contain specific details about the subject?
- Is this section essential to understanding/implementing the subject?
- Would someone researching this subject need to read this section?
- How central is this content to the subject vs. peripheral?

Be conservative in high scores:
- Reserve 0.9-1.0 for absolutely essential sections
- Use 0.7-0.8 for clearly relevant but not critical sections
- Use 0.5-0.6 for sections that mention the subject but aren't focused on it

Provide brief reasoning for your score to justify the assessment.
```
</details>

### Processing Actions
- **Node Metadata Fetching**:
  - Neo4j direct queries: For each node ID, execute Cypher query to fetch complete metadata
  - Query pattern: `MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: $node_id})`
  - Extracts: id, title, summary, start_line, end_line, source, doc_name
- **Graph Traversal & Expansion**:
  - For each initial node:
    - Navigate upward: `graph_rag.navigate_upward(node_id, levels=1)` to get parents
    - Navigate downward: `graph_rag.get_children(node_id)` to get children
    - Fetch metadata for all discovered nodes
  - Add parents and children to result set (implicit high relevance)
- **Consolidation**: Use `graph_rag.consolidate_branches()` to deduplicate
- **Output**: List of nodes with complete metadata

### Input Schema

```python
{
    "node_ids": List[str]  # List of node IDs from Analyzer Phase 2
}
```

### Required Fields
- `node_ids`: List of node identifiers to perform deep analysis on

### Output
```python
{
    "nodes": List[Dict]  # List of nodes with complete metadata
}
```

### Node Metadata Structure
Each node in the output contains:
```python
{
    "id": str,              # Node identifier
    "title": str,           # Node title
    "summary": str,         # Node summary
    "start_line": int,      # Start line in source document
    "end_line": int,        # End line in source document
    "source": str,          # Source document path
    "doc_name": str         # Document name
}
```

---

## 4. Extractor Agent

**File:** `agents/extractor.py`

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses comprehensive multi-subject extraction prompt with maximum granularity requirements. Emphasizes atomic actions, quantitative specificity, and complete WHO/WHEN/WHAT extraction. Includes formula and table extraction specifications.

<details>
<summary><b>📋 View Full Prompt (Excerpt - Full prompt is 650+ lines)</b></summary>

```
CRITICAL EXTRACTION RULES: MAXIMUM GRANULARITY & QUANTITATIVE ACTIONS ONLY

✅ EXTRACT:
- ATOMIC actions: Each action is ONE independently executable step
- QUANTITATIVE actions: Include specific numbers, frequencies, thresholds, methods
- CONCRETE actions: State EXACTLY what to do, with HOW if specified
- MEASURABLE actions: Clear deliverables and success criteria

❌ REJECT - DO NOT EXTRACT:
- Qualitative descriptions ("improve quality", "ensure compliance")
- Strategic goals or vision statements ("be prepared", "achieve excellence")
- Compound actions (multiple steps in one action - BREAK THEM DOWN)
- Vague responsibilities ("oversee", "coordinate" without specifics)

ACTION EXTRACTION FORMAT:

**WHO**: Specific role/unit/position (NOT "staff", "team", "personnel")
**WHEN**: Precise timeline or trigger condition
**ACTION**: Comprehensive description including all details, outcomes, resources, and procedures

🚨 CRITICAL: HANDLING MISSING WHO/WHEN INFORMATION:
- ✅ STILL EXTRACT THE ACTION - Do not skip it!
- ✅ Use empty string ("") for missing WHO or WHEN field
- ❌ DO NOT infer, guess, or hallucinate WHO/WHEN details not in the source
- ❌ DO NOT skip extraction just because WHO/WHEN are missing

FORMULA EXTRACTION & ACTION INTEGRATION:
Extract ALL mathematical formulas with:
- formula: Raw equation
- computation_example: Worked example
- sample_result: Calculated output
- formula_context: What it calculates and when to use
- related_action_indices: Link to actions using this formula

TABLE & CHECKLIST EXTRACTION:
Identify ALL tables, checklists, and structured lists with:
- table_title, table_type, headers, rows, markdown_content

EXTRACT ACTIONS FROM TABLES and link them back.
```

**Note**: The full prompt includes extensive examples of good/bad extractions, compound action breaking, and detailed JSON schema specifications.
</details>

### Processing Actions
- **Content Reading**:
  - For each node: `DocumentParser.get_content_by_lines()` to read full content from source files
  - Fallback: Neo4j query to get document source path if not in metadata
- **Markdown Recovery**: LLM-based recovery of corrupted markdown structures (temp=0.1)
- **Content Segmentation**: If content > 2000 tokens, split into markdown-aware segments
- **Extraction (per node or segment)**:
  - LLM call (temp=0.2): Extract actions, formulas, tables in structured JSON
  - Actions flagged if WHO/WHEN missing or generic
- **Formula Integration**: Merge formulas into related action descriptions
- **Table Enhancement**: Infer table titles using LLM (temp=0.3) if missing
- **Schema Validation**: Validate all extracted items against required schemas
- **Aggregation**: Combine across all subjects and nodes
- **Output Formatting**: Generate human-readable WHO-based formatted output

### Input Schema

```python
{
    "subject_nodes": List[Dict]  # List of subject-node mappings
}
```

### Subject Node Structure
```python
{
    "subject": str,           # Subject name
    "nodes": List[Dict]       # List of node objects with metadata
}
```

### Node Object Structure (within subject_nodes)
```python
{
    "id": str,                # Node identifier
    "title": str,             # Node title
    "start_line": int,        # Start line in source document
    "end_line": int,          # End line in source document
    "source": str             # Source document path
}
```

### Required Fields
- `subject_nodes`: List containing subject-to-nodes mappings

### Output
```python
{
    # New Format (Primary)
    "formatted_output": str,                    # Human-readable text with WHO-based grouping
    "actions_by_actor": Dict[str, List],        # Actions grouped by WHO field
    "tables": List[Dict],                       # List of table objects
    "metadata": Dict,                           # Extraction statistics
    
    # Legacy Format (Backward Compatibility)
    "complete_actions": List[Dict],             # Actions with valid who/when
    "flagged_actions": List[Dict],              # Actions missing/generic who/when
    "subject_actions": List[Dict]               # Subject-specific data
}
```

### Action Object Structure (Output)
```python
{
    "id": str,                              # Unique action identifier
    "action": str,                          # Comprehensive action description
    "who": str,                             # Responsible role/unit
    "when": str,                            # Timeline or trigger
    "reference": {                          # Source reference
        "document": str,                    # Document path
        "line_range": str,                  # Line range (e.g., "45-52")
        "node_id": str,                     # Source node ID
        "node_title": str                   # Node title
    },
    "timing_flagged": bool,                 # True if WHO valid but WHEN generic
    "actor_flagged": bool,                  # True if WHO generic/missing
    "flag_reason": str,                     # Explanation for flagged actions
    "original_formula_reference": Dict,     # If formula was merged into action
    "source_node": str,                     # Legacy field (same as reference.node_id)
    "source_lines": str                     # Legacy field (same as reference.line_range)
}
```

### Table Object Structure (Output)
```python
{
    "id": str,                              # Unique table identifier
    "table_title": str,                     # Descriptive title
    "table_type": str,                      # One of: "checklist", "action_table", "decision_matrix", "other"
    "headers": List[str],                   # Column headers
    "rows": List[List[str]],                # Row data
    "markdown_content": str,                # Original markdown representation
    "reference": {                          # Source reference (same structure as action)
        "document": str,
        "line_range": str,
        "node_id": str,
        "node_title": str
    },
    "extracted_actions": List[str],         # List of action IDs extracted from table
    "title_inferred": bool                  # True if title was inferred by LLM
}
```

---

## 5. Selector Agent

**File:** `agents/selector.py`

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses semantic relevance filtering prompt that emphasizes direct relevance vs. supporting actions. Includes specific examples of inclusion/exclusion criteria based on problem statement alignment.

<details>
<summary><b>📋 View Full Prompt (Key Sections)</b></summary>

```
You are the Selector Agent for action relevance filtering.

**Selection Criteria:**

1. **Direct Relevance** (Critical):
   - Does the action directly address the problem statement?
   - Is the action specific to the stated crisis subject (war/sanction)?
   - Does the action align with the specified phase (preparedness/response)?
   - Is the action appropriate for the organizational level?

2. **Timing Alignment**: Match user's specified timeframe and triggers

3. **Scope Match**: Within scope of plan's objectives

**Semantic Analysis Guidelines:**
- **Highly Relevant** (INCLUDE): Essential to problem statement
- **Supporting Actions** (INCLUDE): Enable or support primary objective
- **Tangentially Relevant** (EXCLUDE): Generally related but not specific
- **Irrelevant** (EXCLUDE): Different crisis types, phases, or levels

**Examples:**
Problem: "Emergency triage for mass casualty events in wartime at university hospitals"
- INCLUDE: "Triage Team Lead establishes primary triage area within 30 minutes"
- INCLUDE: "Blood Bank Manager implements emergency blood allocation protocol" (supporting)
- EXCLUDE: "Procurement officer negotiates for sanction-affected medications" (wrong crisis)
- EXCLUDE: "Ministry prepares national resource allocation" (wrong level)

**Output:** Selected actions with relevance_score and relevance_rationale
```
</details>

### Processing Actions
- **Batch Processing**: Process actions in batches (batch_size=15) to avoid LLM overload
- **Action Selection**:
  - For each batch: LLM call (temp=0.2, json_mode=true)
  - LLM returns selected actions with relevance scores and rationale
  - LLM identifies discarded actions with discard reasons
- **Table Filtering**:
  - Identify tables referenced by selected actions
  - LLM scoring (temp=0.3): Score table relevance (0-10 scale)
  - Keep tables if: score >= 7.0 OR referenced by selected action
- **Summary Generation**: Calculate statistics (total input/output, discards, avg scores)
- **Markdown Logging**: Detailed logging of selections and discards

### Input Schema

```python
{
    "problem_statement": str,               # Refined problem/objective from Orchestrator
    "user_config": Dict,                    # User configuration
    "complete_actions": List[Dict],         # Actions with who/when defined
    "flagged_actions": List[Dict],          # Actions missing who/when
    "tables": List[Dict]                    # Optional: List of table objects
}
```

### Required Fields
- `problem_statement`: The problem statement for relevance filtering
- `user_config`: User configuration (contains level, phase, subject)
- `complete_actions`: List of complete action objects
- `flagged_actions`: List of flagged action objects

### Optional Fields
- `tables`: List of table objects to pass through

### Output
```python
{
    "selected_complete_actions": List[Dict],    # Filtered complete actions
    "selected_flagged_actions": List[Dict],     # Filtered flagged actions
    "tables": List[Dict],                       # Tables (passed through or filtered)
    "selection_summary": {                      # Selection statistics
        "total_input_complete": int,
        "total_input_flagged": int,
        "selected_complete": int,
        "selected_flagged": int,
        "discarded_complete": int,
        "discarded_flagged": int,
        "average_relevance_score": float,
        "total_input_tables": int,
        "selected_tables": int,
        "discarded_tables": int
    },
    "discarded_actions": List[Dict]             # Actions filtered out with reasons
}
```

### Selected Action Enhancements
Each selected action includes:
```python
{
    # All original action fields, plus:
    "relevance_score": float,           # 0.0-1.0 relevance score
    "relevance_rationale": str          # Explanation of relevance
}
```

---

## 6. Deduplicator Agent

**File:** `agents/deduplicator.py`

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses merge-focused prompt with semantic similarity guidelines and source preservation requirements. Defines clear criteria for when to merge actions and how to combine sources.

<details>
<summary><b>📋 View Full Prompt (Key Sections)</b></summary>

```
You are the De-duplicator and Merger Agent for action plan refinement.

**Merging Criteria:**
Two actions should be merged if they describe:
- The same specific activity (WHAT)
- Performed by the same role or equivalent roles (WHO)
- At the same time or under the same trigger (WHEN)
- In the same context

**Semantic Similarity Guidelines:**
- "Incident Commander establishes command post" ≈ "IC sets up command center"
- "Triage team sorts patients by priority" ≈ "Triage staff categorize casualties"
- Different timings are NOT duplicates: "within 1 hour" ≠ "within 4 hours"
- Different parties are NOT duplicates: "Triage Team" ≠ "Medical Director"

**When Merging Actions:**
1. Choose the most complete and specific description
2. Combine all source citations
3. If WHO/WHEN/WHAT differ slightly, use the most specific version
4. Preserve context from all merged actions
5. Add "merged_from" field listing original action IDs

**Important Rules:**
- Do NOT discard flagged actions
- When in doubt, do NOT merge - preserve both
- Merging should reduce redundancy, not information
- All source citations must be traceable
```
</details>

### Processing Actions
- **Batch Processing (Actions)**: Process in batches (batch_size=15)
  - For each batch: LLM call (temp=0.2) to identify and merge duplicates
  - LLM combines sources, selects best description, adds merge metadata
- **Batch Processing (Tables)**: Process in batches (batch_size=10)
  - LLM call (temp=0.2): Semantic analysis of table similarity
  - Merge criteria: same title, compatible headers, same purpose
  - Combine rows and preserve all sources
- **Merge Summary**: Calculate statistics (input/output counts, merge operations)
- **Markdown Logging**: Log merge details with rationale

### Input Schema

```python
{
    "complete_actions": List[Dict],         # Actions with who/when defined
    "flagged_actions": List[Dict],          # Actions missing who/when
    "tables": List[Dict]                    # Optional: List of table objects
}
```

### Required Fields
- `complete_actions`: List of complete action objects
- `flagged_actions`: List of flagged action objects

### Optional Fields
- `tables`: List of table objects

### Output
```python
{
    "refined_complete_actions": List[Dict],     # Deduplicated complete actions
    "refined_flagged_actions": List[Dict],      # Deduplicated flagged actions
    "tables": List[Dict],                       # Deduplicated tables
    "merge_summary": {                          # Merge statistics
        "total_input_complete": int,
        "total_input_flagged": int,
        "total_output_complete": int,
        "total_output_flagged": int,
        "merges_performed": int,
        "actions_unchanged": int,
        "total_input_tables": int,
        "total_output_tables": int,
        "table_merges_performed": int
    }
}
```

### Merged Action Enhancements
Each merged action includes:
```python
{
    # All original action fields, plus:
    "merged_from": List[str],           # List of original action IDs that were merged
    "merge_rationale": str              # Explanation of merge decision
}
```

---

## 7. Timing Agent

**File:** `agents/timing.py`

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses strict timing specification prompt with forbidden vague terms list and required trigger + time window structure. Includes context-based duration standards for different action categories.

<details>
<summary><b>📋 View Full Prompt (Key Sections)</b></summary>

```
You are an expert in operational planning for health emergencies with strict timing specifications.

## CRITICAL RULES - FORBIDDEN VAGUE TERMS

STRICTLY PROHIBITED:
❌ "immediately", "soon", "ASAP", "promptly", "quickly", "rapidly"
❌ "as needed", "when necessary", "eventually", "shortly"

## Trigger Requirements (Observable, Specific, Verifiable)

Valid formats:
- "Upon [specific event] (T_0)"
- "When [measurable condition exceeds threshold]"
- "At [specific time]"
- "After [completion of specific action]"

Examples:
✅ "Upon notification of Code Orange (T_0)"
✅ "When patient census exceeds 50"
✅ "At 08:00 daily during emergency period"

## Time Window Requirements (Specific duration with units)

Valid formats:
- "Within X minutes (T_0 + X min)"
- "Within X-Y hours (T_0 + X-Y hr)"
- "Maximum X hours (T_0 + X hr)"

Examples:
✅ "Within 5 minutes (T_0 + 5 min)"
✅ "Within 30-60 minutes (T_0 + 30-60 min)"

## Context-Based Duration Standards

- Emergency/Critical: Within 5 minutes
- Communication: Within 2-3 minutes
- Clinical Procedures: Within 30-60 minutes
- Administrative: Within 15 minutes
- Resource Mobilization: Within 2-4 hours
- Training: Within 24-48 hours
```
</details>

### Processing Actions
- **Timing Assessment**: For each action, check if timing needs processing using `_is_timing_needed()`
  - Checks for vague terms, missing structure, or invalid trigger/time_window
- **LLM Assignment** (if needed):
  - LLM call (temp=0.4): Generate trigger and time_window for actions
  - Returns actions with both fields populated
- **Validation & Conversion**:
  - Validate trigger: Must be observable condition or timestamp
  - Validate time_window: Must have specific duration with units
  - Convert vague terms: Context-based conversion (emergency → 5 min, clinical → 30-60 min, etc.)
- **Consolidation**: Merge trigger and time_window into `when` field with ` | ` separator
- **Cleanup**: Remove temporary trigger/time_window fields from output

### Input Schema

```python
{
    "actions": List[Dict],              # List of actions to process
    "problem_statement": str,           # Problem/objective statement
    "user_config": Dict,                # User configuration
    "tables": List[Dict]                # Optional: List of table objects (passed through)
}
```

### Required Fields
- `actions`: List of action objects (may have incomplete timing)
- `problem_statement`: Problem statement for context
- `user_config`: User configuration

### Optional Fields
- `tables`: List of table objects to pass through

### Output
```python
{
    "timed_actions": List[Dict],        # Actions with validated timing information
    "tables": List[Dict]                # Pass-through tables
}
```

### Timing Format
The `when` field is structured as: `"<trigger> | <time_window>"`

Examples:
- `"Upon notification of mass casualty event (T_0) | Within 30 minutes (T_0 + 30 min)"`
- `"When patient census exceeds 50 patients | Within 15-20 minutes from trigger"`
- `"At 08:00 daily during crisis period | Within 2 hours (T_0 + 120 min)"`

### Forbidden Terms
The agent converts or rejects these vague terms:
- "immediately", "soon", "asap", "promptly", "quickly"
- "as needed", "when necessary", "eventually"

---

## 8. Assigner Agent

**File:** `agents/assigner.py`

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses organizational structure-aware prompt for role assignment. Emphasizes extraction of actors from action descriptions, validation against reference document, and context-based inference.

<details>
<summary><b>📋 View Full Prompt</b></summary>

```
You are the Assigner Agent for role assignment in the Iranian health system.

## Your Task
Assign the 'who' field for each action by:
1. Extracting actor/role if mentioned in the action description
2. Validating against the organizational reference document
3. Inferring the best actor based on context if not explicitly mentioned
4. Using organizational level (ministry/university/center) to determine appropriate role

## Key Rules
- Extract actors mentioned in action descriptions first
- Match extracted actors to official job titles in reference document
- Infer appropriate actor based on action type and organizational level if not mentioned
- Assign specific job positions, not generic terms
- Preserve ALL other action fields unchanged

## Output Format
Return JSON with 'assigned_actions' key containing the list of actions with updated 'who' field.

Example:
{
  "assigned_actions": [
    {
      "action": "Activate triage protocols",
      "who": "Head of Emergency Department",
      "when": "Within 30 minutes",
      ...other fields preserved...
    }
  ]
}

Be specific. Use context to infer appropriate roles when not explicitly stated.
```
</details>

### Processing Actions
- **Reference Document Loading**: Load organizational structure reference from `assigner_tools/Assigner refrence.md`
- **Batch Processing**: If actions > batch_threshold, process in batches (batch_size from settings)
- **Assignment**:
  - For each batch: LLM call (temp=0.1) with actions + reference document
  - LLM assigns specific WHO field based on action context and organizational level
  - Defensive normalization: Handle various LLM output formats (dict, string, list)
- **Field Preservation**: All other action fields preserved unchanged
- **Pass-through**: Tables passed through unmodified

### Input Schema

```python
{
    "prioritized_actions": List[Dict],      # Actions to assign responsibilities
    "user_config": Dict,                    # User configuration
    "tables": List[Dict]                    # Optional: List of table objects (passed through)
}
```

### Required Fields
- `prioritized_actions`: List of action objects
- `user_config`: User configuration (includes level, phase, subject)

### Optional Fields
- `tables`: List of table objects to pass through

### Output
```python
{
    "assigned_actions": List[Dict],         # Actions with 'who' field assigned
    "tables": List[Dict]                    # Pass-through tables
}
```

### Assignment Note
This agent's sole responsibility is to assign the `who` field. All other fields are preserved unchanged.

---

## 9. Formatter Agent

**File:** `agents/formatter.py`

**Method:** `execute(data: Dict[str, Any]) -> str`

### System Prompt
Uses structured checklist formatting prompt with specific section requirements and markdown table specifications. Emphasizes professional, operational-ready output.

<details>
<summary><b>📋 View Full Prompt (Key Sections)</b></summary>

```
You are the Formatter Agent for creating final crisis action checklists.

**Action Checklist Structure:**

**1. Checklist Specifications:**
A table containing key metadata:
- Checklist Name, Department/Jurisdiction, Crisis Area, Checklist Type
- Reference Protocol(s), Operational Setting, Process Owner
- Acting Individual(s), Incident Commander, Activation Trigger, Objective

**2. Executive Steps:**
Summary table: Executive Step | Responsible | Deadline/Timeframe

**3. Checklist Content by Executive Steps:**
Detailed actions organized by timeframe:
- Part 1: Immediate Actions (e.g., first 30 minutes)
- Part 2: Urgent Actions (e.g., first 2 hours)
- Part 3: Continuous Actions

Table columns: No. | Action | Status | Remarks/Report

**4. Implementation Approval:**
Sign-off table: Role | Full Name | Date and Time | Signature

**Formatting Guidelines:**
- Use clear, professional language for crisis management
- Use markdown: headers (H3, H4) and tables
- Ensure all tables have correct headers
- Complete, standalone checklist ready for operational use
```
</details>

### Processing Actions
- **Metadata Auto-population**:
  - Extract unique roles from actions for "Acting Individual(s)"
  - Map user config (level, phase, subject) to specification fields
  - Infer department jurisdiction from action roles
  - Generate checklist objectives from problem statement
- **Action Grouping**: Group actions by responsible actor (WHO field)
- **Table Linking**: Identify which tables are referenced by which actions
- **Markdown Generation**:
  - Section 1: Checklist Specifications table (auto-populated)
  - Section 2: Checklist Content by Actor
    - For each actor: Action table with columns (No., ID, Action, Timeline, Reference, Status, Remarks)
    - Append relevant appendices (tables) for each actor
- **Appendix Formatting**: Convert table objects to appendix format with references

**Note**: No LLM calls - pure Python data transformation and markdown generation.

### Input Schema

```python
{
    "assigned_actions": List[Dict],         # Actions with role assignments
    "tables": List[Dict],                   # List of table/checklist objects
    "formatted_output": str,                # Optional: Pre-formatted output from extractor
    "rules_context": Dict,                  # Rules and context information
    "problem_statement": str,               # Problem/objective statement
    "user_config": Dict,                    # User configuration
    "trigger": str,                         # Optional: User-specified trigger
    "responsible_party": str,               # Optional: User-specified responsible party
    "process_owner": str                    # Optional: User-specified process owner
}
```

### Required Fields
- `assigned_actions`: List of action objects with assignments
- `user_config`: User configuration

### Optional Fields
- `tables`: List of table objects
- `formatted_output`: Pre-formatted output
- `rules_context`: Context information
- `problem_statement`: Problem statement
- `trigger`: Activation trigger
- `responsible_party`: Responsible party
- `process_owner`: Process owner

### Output
Returns a formatted markdown string containing:
1. **Checklist Specifications** table
2. **Checklist Content by Responsible Actor** sections
3. Integrated tables and appendices

---

## 10. Quality Checker Agent

**File:** `agents/quality_checker.py`

**Method:** `execute(data: Dict[str, Any], stage: str, user_config: Dict = None) -> Dict[str, Any]`

### System Prompt
Uses stage-specific quality validation prompt with 4 evaluation criteria (accuracy, completeness, source_traceability, actionability). Can load context-specific templates based on user config (level/phase/subject).

<details>
<summary><b>📋 View Full Prompt</b></summary>

```
You are the Quality Checker Agent ensuring plan accuracy and compliance.

**Evaluation Criteria:**

1. **Accuracy (0-1 score)**
   - All information traceable to sources
   - No hallucinations or unsupported claims
   - Correct interpretation of protocols and guidelines

2. **Completeness (0-1 score)**
   - All critical aspects covered
   - No major gaps in the action sequence
   - Sufficient detail for implementation

3. **Source Traceability (0-1 score)**
   - Every action has proper citations
   - Source references are accurate and specific
   - Node IDs and line numbers provided
   - For guideline sources: hierarchical path included

4. **Actionability (0-1 score)**
   - Actions are specific and measurable
   - Clear who, what, when, where
   - Realistic and implementable

**Output Format:**
{
  "status": "pass|retry",
  "overall_score": 0.0-1.0,
  "scores": {
    "accuracy": 0.0-1.0,
    "completeness": 0.0-1.0,
    "source_traceability": 0.0-1.0,
    "actionability": 0.0-1.0
  },
  "feedback": "Detailed constructive feedback",
  "issues": ["Specific issues found"],
  "recommendations": ["Specific improvements needed"]
}

Pass threshold: overall_score >= 0.7
```
</details>

### Processing Actions
- **Template Loading**: If user_config provided, load context-specific quality checker template
- **Standards Retrieval**:
  - Hybrid RAG query: `rules_rag.query()` to get quality standards for stage
  - Top-k=3 results combined as standards reference
- **LLM Evaluation**:
  - LLM call (temp=0.2): Evaluate data against standards
  - Returns scores for 4 criteria (0.0-1.0 each)
  - Calculates overall_score as average
- **Status Determination**: overall_score >= 0.65 → "pass", else "retry"
- **Feedback Generation**: LLM provides detailed issues and recommendations

### Input Schema

```python
{
    # Data varies by stage - can be any agent output
    "actions": List[Dict],              # Example: for extractor stage
    "subject": str,                     # Example: for extractor stage
    # ... other stage-specific fields
}
```

### Required Parameters
- `data`: Dictionary containing stage-specific output to validate
- `stage`: Current workflow stage name (e.g., "extractor", "selector")

### Optional Parameters
- `user_config`: User configuration for loading context-specific templates

### Output
```python
{
    "status": str,                      # "pass" or "retry"
    "overall_score": float,             # 0.0-1.0 quality score
    "scores": {                         # Individual criterion scores
        "accuracy": float,              # 0.0-1.0
        "completeness": float,          # 0.0-1.0
        "source_traceability": float,   # 0.0-1.0
        "actionability": float          # 0.0-1.0
    },
    "feedback": str,                    # Detailed constructive feedback
    "issues": List[str],                # Specific issues found
    "recommendations": List[str]        # Specific improvements needed
}
```

### Pass Threshold
- `overall_score >= 0.65` → status: "pass"
- `overall_score < 0.65` → status: "retry"

---

## 11. Comprehensive Quality Validator

**File:** `agents/quality_checker.py` (class: `ComprehensiveQualityValidator`)

**Method:** `execute(data: Dict[str, Any]) -> Dict[str, Any]`

### System Prompt
Uses comprehensive end-to-end validation prompt with 7 validation criteria. Includes root cause diagnosis prompt and quality repair prompt for supervisor-level decision making.

<details>
<summary><b>📋 View Full Prompt (Key Sections)</b></summary>

```
You are the Comprehensive Quality Validator, the final supervisor in a multi-agent pipeline.

**Your Role:**
1. Validate complete final English checklist against all quality criteria
2. Perform root cause analysis when issues found
3. Identify which upstream agent caused specific defects
4. Decide: self-repair minor issues OR request agent re-execution for major defects

**Validation Criteria (0.0-1.0 each):**
- Structural Completeness: All sections present and properly formatted
- Action Traceability: Every action has WHO, WHEN, WHAT, and source citations
- Logical Sequencing: Actions properly ordered by timeline
- Guideline Compliance: Actions align with provided health protocols
- Formatting Quality: Valid markdown, correct tables
- Actionability: Actions are specific and implementable
- Metadata Completeness: All specification fields filled appropriately

**Decision Framework:**
- Score >= 0.8: Approve for output
- Score 0.6-0.8 with minor issues: Self-repair (formatting, missing placeholders)
- Score < 0.6 or major issues: Diagnose responsible agent and request targeted re-run

**Root Cause Diagnosis:**
- Missing actions/citations → Analyzer/phase3
- Actions not relevant → Selector
- Duplicate/unclear actions → Extractor/Deduplicator
- Wrong timeline → Timing
- Missing/incorrect WHO/WHEN → Assigner
- Formatting/structural problems → Formatter
```
</details>

### Processing Actions
- **Step 1 - Validation**:
  - LLM call (temp=0.1): Validate final checklist against 7 criteria
  - Scores: structural_completeness, action_traceability, logical_sequencing, guideline_compliance, formatting_quality, actionability, metadata_completeness
  - overall_score >= 0.8 → Pass, return validated plan
- **Step 2 - Root Cause Diagnosis** (if validation fails):
  - LLM call (temp=0.2): Identify which upstream agent caused issues
  - Determine severity: minor vs. major
- **Step 3 - Decision & Action**:
  - If minor issues + can_self_repair:
    - LLM call (temp=0.1): Self-repair formatting/metadata issues
    - Return repaired plan with repairs_made list
  - If major issues:
    - Return agent_rerun status with responsible agent and targeted feedback
    - Increment retry counter

### Input Schema

```python
{
    "final_plan": str,                      # English markdown checklist from formatter
    "subject": str,                         # Original user subject
    "orchestrator_context": Dict,           # Rules context, guidelines, requirements
    "assigned_actions": List[Dict],         # Structured actions from assigner
    "original_input": Dict,                 # User's original request parameters
    "validator_retry_count": int            # Optional: Number of retries
}
```

### Required Fields
- `final_plan`: The formatted markdown checklist
- `subject`: Original subject/title
- `orchestrator_context`: Context from orchestrator
- `assigned_actions`: Structured action list

### Output (Three Possible Statuses)

#### Status: "approve"
```python
{
    "status": "approve",
    "validated_plan": str,                  # Final validated plan
    "quality_score": float,                 # Overall quality score
    "validation_report": Dict               # Detailed validation results
}
```

#### Status: "self_repair"
```python
{
    "status": "self_repair",
    "repaired_plan": str,                   # Self-repaired plan
    "repairs_made": List[str],              # List of repairs performed
    "quality_score": float,
    "diagnosis": Dict,                      # Root cause diagnosis
    "validation_report": Dict
}
```

#### Status: "agent_rerun"
```python
{
    "status": "agent_rerun",
    "responsible_agent": str,               # Which agent needs to re-run
    "issue_description": str,               # Description of quality issues
    "targeted_feedback": str,               # Specific feedback for agent
    "retry_count": int,                     # Incremented retry count
    "diagnosis": Dict,                      # Root cause diagnosis
    "validation_report": Dict
}
```

### Validation Criteria
- Structural Completeness: 0.0-1.0
- Action Traceability: 0.0-1.0
- Logical Sequencing: 0.0-1.0
- Guideline Compliance: 0.0-1.0
- Formatting Quality: 0.0-1.0
- Actionability: 0.0-1.0
- Metadata Completeness: 0.0-1.0

**Pass Threshold:** `overall_score >= 0.8`

---

## 12. Translator Agent

**File:** `agents/translator.py`

**Method:** `execute(data: Dict[str, Any]) -> str`

### System Prompt
Uses professional Persian translation prompt with officially-certified-grade standards. Emphasizes verbatim translation, markdown preservation, and technical terminology handling (Persian followed by English in parentheses).

<details>
<summary><b>📋 View Full Prompt</b></summary>

```
You are a Professional Persian Translator specialized in officially-certified-grade translations.

**Translation Standards:**
1. Verbatim translation - translate exactly without interpretation, summarization, or modification
2. Officially-certified-grade quality - equivalent to sworn translation standards
3. Preserve exact markdown structure (headings, lists, tables, bullets, numbering)
4. Maintain professional, formal tone appropriate for government/health policy documents

**Technical Terminology:**
- For specialized terms, provide Persian translation followed by English in parentheses
- Format: "Persian_term (English term)"
- Example: "آمادگی در برابر بلایا (Disaster Preparedness)"
- Apply only to technical/specialized terms, not common words

**What to Preserve:**
- All headings, subheadings, and their hierarchy
- All numerical data, dates, times, percentages
- All bullet points, numbered lists, and tables
- All section breaks and formatting markers

**What NOT to Do:**
- Do not summarize or condense any content
- Do not add explanations or interpretations
- Do not modify the structure or organization
- Do not skip any sections or details
- Do not change the tone or formality level

Output only the translated Persian text maintaining exact markdown formatting.
```
</details>

### Processing Actions
- **Model Override**: Uses specialized translator model (configurable in settings)
- **Single LLM Call**:
  - LLM call (temp=0.1): Translate complete English action plan to Persian
  - Preserve all markdown structure (headings, tables, lists)
  - Add English technical terms in parentheses after Persian
- **Output**: Complete Persian translation as string

**Note**: Simple single-pass translation, no additional processing.

### Input Schema

```python
{
    "final_plan": str                       # English markdown action plan
}
```

### Required Fields
- `final_plan`: The English action plan to translate

### Output
Returns a string containing the Persian translation of the action plan.

### Translation Guidelines
- Verbatim, officially-certified-grade translation
- Preserve all markdown formatting
- Add English technical terms in parentheses after Persian terms

---

## 13. Assigning Translator Agent

**File:** `agents/assigning_translator.py`

**Method:** `execute(data: Dict[str, Any]) -> str`

### System Prompt
Uses Persian-language correction prompt focused on organizational terminology accuracy. Prompts agent to correct job titles, departments, and organizational units against official reference document.

<details>
<summary><b>📋 View Full Prompt (Key Sections in Persian)</b></summary>

```
شما یک کارشناس ارشد تصحیح ترجمه در حوزه مدیریت بحران سلامت هستید.

## نقش شما
تصحیح و بهبود دقت ترجمه فارسی در بخش‌های مربوط به:
- پست‌های سازمانی
- مسئولین و نقش‌های تخصصی
- واحدهای سازمانی (دفاتر، معاونت‌ها، مراکز)
- سازمان‌ها و نهادهای وابسته

## اصول تصحیح

### دقت در اصطلاحات رسمی
- استفاده از عناوین رسمی سازمانی (نه معادل تقریبی)
- تطبیق کامل با ساختار تشکیلاتی وزارت بهداشت
- استفاده از عناوین دقیق از سند مرجع

### سلسله مراتب سازمانی
**سطح وزارت:** معاونت‌ها، اداره‌های کل، مراکز، دفاتر
**سطح دانشگاه:** دانشگاه‌های علوم پزشکی، معاونت‌ها، دانشکده‌ها، شبکه‌های بهداشت
**سطح مرکز/بیمارستان:** رئیس بیمارستان، مترون، سوپروایزر، سرپرستار، پرستاران، پزشکان

### موارد نیازمند تصحیح
❌ ترجمه‌های نادرست رایج:
- "Hospital Manager" → ❌ "مدیر بیمارستان" → ✓ "رئیس بیمارستان"
- "Nursing Director" → ❌ "مدیر پرستاری" → ✓ "مترون"
- "Emergency Operations Center" → ✓ "مرکز مدیریت حوادث و فوریت‌های پزشکی"

**خروجی:** فقط متن فارسی تصحیح‌شده با فرمت markdown کامل
```
</details>

### Processing Actions
- **Reference Document Loading**: Load Persian organizational reference from `assigner_tools/Fa/Assigner refrence.md`
- **Single LLM Call**:
  - LLM call (temp=0.1): Review Persian plan and correct organizational terminology
  - Match against official reference document structure
  - Correct job titles, departments, organizational units
  - Preserve all markdown formatting
- **Output**: Corrected Persian translation with accurate organizational assignments

**Note**: Focuses only on organizational terminology, not general translation quality.

### Input Schema

```python
{
    "final_persian_plan": str               # Persian translation to correct
}
```

### Required Fields
- `final_persian_plan`: The Persian plan with assignments to correct

### Output
Returns a corrected Persian translation with accurate organizational assignments matching the official reference document.

### Correction Focus
- Responsible parties (job titles, roles)
- Organizational units (departments, offices)
- Official terminology compliance
- Organizational hierarchy preservation

---

## Common Data Types

### Reference Object
Used throughout the system for source traceability:
```python
{
    "document": str,            # Full document path/name
    "line_range": str,          # Line range (e.g., "45-52")
    "node_id": str,             # Source node identifier
    "node_title": str           # Human-readable node title
}
```

### User Config Object
Standard configuration passed through workflow:
```python
{
    "name": str,                # Action plan title
    "timing": str,              # Time period and/or trigger
    "level": str,               # "ministry" | "university" | "center"
    "phase": str,               # "preparedness" | "response"
    "subject": str              # "war" | "sanction"
}
```

---

## Agent Workflow Sequence

The typical agent execution sequence is:

```
1. Orchestrator      → problem_statement, user_config
2. Analyzer          → node_ids, all_documents, refined_queries
3. Phase3            → nodes (with complete metadata)
4. Extractor         → complete_actions, flagged_actions, tables
5. Selector          → selected actions, filtered tables
6. Deduplicator      → refined actions, merged tables
7. Timing            → timed_actions
8. Assigner          → assigned_actions
9. Formatter         → final_plan (English markdown)
10. Translator       → final_persian_plan
11. Assigning Translator → corrected_persian_plan
```

**Quality Checker** can be invoked at any stage for validation.

**Comprehensive Quality Validator** validates the final output and may trigger agent re-runs or self-repairs.

---

## Notes

1. **Optional Fields**: Fields marked as "Optional" can be omitted from the input dictionary.
2. **Pass-Through Fields**: Some agents (Selector, Timing, Assigner) pass through `tables` unchanged.
3. **Reference Preservation**: All agents preserve source references when processing or merging data.
4. **Batch Processing**: Several agents (Selector, Deduplicator, Timing) implement batch processing for large datasets.
5. **LLM Integration**: All agents use the `LLMClient` with agent-specific configurations via `dynamic_settings`.
6. **Markdown Logger**: All agents support optional `markdown_logger` for detailed execution logging.

---

## Last Updated
Generated: November 2025

