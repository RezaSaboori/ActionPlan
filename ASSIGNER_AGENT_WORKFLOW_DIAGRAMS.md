# Assigner Agent - Workflow Diagrams

Visual representations of the Assigner Agent's processes and workflows.

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        ASSIGNER AGENT                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────┐           ┌──────────────────┐             │
│  │   Initialize    │           │   LLM Client     │             │
│  │   Reference Doc │◄──────────┤   (Ollama/OpenAI)│             │
│  └────────┬────────┘           └──────────────────┘             │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────────────────────────────────┐                │
│  │          Execute Method                     │                │
│  │  • Validate input                           │                │
│  │  • Check batch threshold (30)               │                │
│  │  • Route to single/batch processing         │                │
│  └────────────────┬────────────────────────────┘                │
│                   │                                               │
│         ┌─────────▼──────────┐                                   │
│         │   Batch Decision   │                                   │
│         └─────────┬──────────┘                                   │
│                   │                                               │
│        ┌──────────▼──────────┐                                   │
│        │ Actions ≤ 30?       │                                   │
│        └──────────┬──────────┘                                   │
│                   │                                               │
│         ┌─────────▼──────────┐                                   │
│         │        YES          │                                   │
│         │  Single Batch       │                                   │
│         │  with Retry         │                                   │
│         └─────────┬──────────┘                                   │
│                   │                                               │
│                   ▼                                               │
│         ┌─────────────────────────────────┐                      │
│         │  _assign_responsibilities       │                      │
│         │  with_retry()                   │                      │
│         │  • Up to 3 attempts             │                      │
│         │  • Exponential backoff          │                      │
│         │  • Validation after each        │                      │
│         └─────────┬──────────────────────┘                      │
│                   │                                               │
│                   ▼                                               │
│         ┌─────────────────────────────────┐                      │
│         │     Validation                  │                      │
│         │  • Check generic terms          │                      │
│         │  • Check empty fields           │                      │
│         └─────────┬──────────────────────┘                      │
│                   │                                               │
│         ┌─────────▼──────────┐                                   │
│         │   Valid?            │                                   │
│         └──────────┬──────────┘                                   │
│                    │                                               │
│          ┌─────────▼──────────┐                                   │
│          │  YES: Return        │                                   │
│          │  NO: Retry/Fallback │                                   │
│          └─────────┬──────────┘                                   │
│                    │                                               │
│                    ▼                                               │
│         ┌─────────────────────────────────┐                      │
│         │     Output                      │                      │
│         │  • assigned_actions             │                      │
│         │  • tables (pass-through)        │                      │
│         └─────────────────────────────────┘                      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

        ┌──────────────┐
        │    NO        │
        │ Batch Mode   │
        │ Split into   │
        │ chunks of 15 │
        └──────┬───────┘
               │
               ▼
    ┌──────────────────────────┐
    │ _assign_responsibilities │
    │ _batched()               │
    │ • Process each batch     │
    │ • Retry per batch        │
    │ • Progress logging       │
    └──────────────────────────┘
```

---

## 2. Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     START: execute()                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Extract Input Data    │
                    │ • prioritized_actions │
                    │ • user_config         │
                    │ • tables              │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Actions empty?        │
                    └───────────┬───────────┘
                                │
                     ┌──────────▼──────────┐
                     │ YES                 │
                     │ Return empty result │
                     └─────────────────────┘
                     
                     │ NO
                     ▼
         ┌───────────────────────────┐
         │ len(actions) > threshold? │
         │ (default: 30)             │
         └───────────┬───────────────┘
                     │
         ┌───────────▼──────────┐
         │ YES: BATCH MODE      │
         └───────────┬──────────┘
                     │
                     ▼
    ┌────────────────────────────────────┐
    │ Split into batches (size: 15)      │
    └────────────────┬───────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────┐
    │ FOR EACH BATCH:                    │
    │                                    │
    │  Attempt 1 ───► Assign ───► Valid?│
    │                   │           │    │
    │                   │           ▼    │
    │                   │          YES   │
    │                   │           │    │
    │                   │         Next   │
    │                   │         Batch  │
    │                   │                │
    │                   ▼           NO   │
    │                 Retry             │
    │                   │                │
    │  Attempt 2 ──────┘                │
    │                                    │
    │  (Repeat for up to 3 attempts)    │
    │                                    │
    │  All Failed? ──► Fallback         │
    └────────────────┬───────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────┐
    │ Concatenate all batch results      │
    └────────────────┬───────────────────┘
                     │
                     └──────────┐
                                │
         ┌──────────────────────┘
         │ NO: SINGLE MODE
         ▼
    ┌────────────────────────────────────┐
    │ _assign_responsibilities_with_retry│
    │                                    │
    │  Attempt 1 ───► Assign ───► Valid?│
    │                   │           │    │
    │                   │           ▼    │
    │                   │          YES   │
    │                   │           │    │
    │                   │         Return │
    │                   │                │
    │                   ▼           NO   │
    │                 Wait 1s            │
    │                   │                │
    │  Attempt 2 ──────┘                │
    │                   │                │
    │                 Wait 2s            │
    │                   │                │
    │  Attempt 3 ──────┘                │
    │                   │                │
    │                 Valid?             │
    │                   │                │
    │            ┌──────▼──────┐         │
    │            │ YES         │         │
    │            │ Return      │         │
    │            └─────────────┘         │
    │                                    │
    │            │ NO                    │
    │            │ Fallback              │
    └────────────────┬───────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Return Result:        │
         │ • assigned_actions    │
         │ • tables              │
         └───────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │      END              │
         └───────────────────────┘
```

---

## 3. Semantic Assignment Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│              SEMANTIC ASSIGNMENT PROCESS                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Input: Action         │
                    │ "Emergency head       │
                    │  activates triage"    │
                    └───────────┬───────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────────┐
        │         PHASE 1: EXTRACTION                   │
        │                                               │
        │  Step 1: Scan Action Description              │
        │  ├─ Search for job titles                    │
        │  ├─ Identify role keywords                   │
        │  └─ Extract candidates                       │
        │                                               │
        │  Extracted: "emergency head"                  │
        └───────────────────┬───────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────────┐
        │         PHASE 2: VALIDATION                   │
        │                                               │
        │  Step 2A: Exact Match?                        │
        │  ├─ Search reference doc                     │
        │  ├─ "emergency head" → NOT FOUND             │
        │  └─ Proceed to semantic match                │
        │                                               │
        │  Step 2B: Semantic Match?                     │
        │  ├─ Search similar terms                     │
        │  ├─ "emergency head" ≈                       │
        │  │   "Head of Emergency Department"          │
        │  └─ MATCH FOUND ✓                            │
        │                                               │
        │  Validated: "Head of Emergency Department"    │
        └───────────────────┬───────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────────┐
        │         PHASE 3: ASSIGNMENT                   │
        │                                               │
        │  Assign validated title to 'who' field        │
        │                                               │
        │  who = "Head of Emergency Department"         │
        └───────────────────┬───────────────────────────┘
                            │
                            ▼
                    ┌───────────────────────┐
                    │ Output: Action        │
                    │ {                     │
                    │   "action": "...",    │
                    │   "who": "Head of     │
                    │    Emergency Dept."   │
                    │ }                     │
                    └───────────────────────┘


        ┌───────────────────────────────────────────────┐
        │         IF NO MATCH IN PHASE 2                │
        │                                               │
        │  PHASE 3: ESCALATION                          │
        │                                               │
        │  Step 3A: Identify Functional Area            │
        │  ├─ Emergency → Emergency domain             │
        │  ├─ Clinical → Clinical domain               │
        │  └─ Administrative → Admin domain            │
        │                                               │
        │  Step 3B: Identify Org Level                  │
        │  ├─ Ministry → National level                │
        │  ├─ University → Regional level              │
        │  └─ Center → Local level                     │
        │                                               │
        │  Step 3C: Assign Supervisor                   │
        │  ├─ Emergency + Center →                     │
        │  │   "Head of Emergency Department"          │
        │  ├─ Clinical + University →                  │
        │  │   "Dean of Health Affairs"                │
        │  └─ Admin + Ministry →                       │
        │      "Deputy Minister of Health"              │
        └───────────────────────────────────────────────┘
```

---

## 4. Validation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     VALIDATION PROCESS                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Input: assigned_actions│
                    │ List of actions       │
                    └───────────┬───────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │ Initialize:                   │
                │ • issues = []                 │
                │ • generic_terms = [...]       │
                └───────────┬───────────────────┘
                            │
                            ▼
                ┌───────────────────────────────┐
                │ FOR EACH action:              │
                └───────────┬───────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │ CHECK 1: Empty Field?                 │
        │                                       │
        │ who.strip() == "" ?                   │
        │                                       │
        │  ┌────────────────┐                   │
        │  │ YES            │                   │
        │  │ Add to issues: │                   │
        │  │ "Empty field"  │                   │
        │  └────────────────┘                   │
        │                                       │
        │  │ NO                                 │
        │  │ Continue                           │
        │  ▼                                    │
        └───┬───────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────┐
        │ CHECK 2: Generic Terms?               │
        │                                       │
        │ FOR EACH generic_term:                │
        │   IF term in who.lower():             │
        │                                       │
        │     ┌──────────────────┐              │
        │     │ FOUND            │              │
        │     │ Add to issues:   │              │
        │     │ "Generic term    │              │
        │     │  '{term}' found" │              │
        │     └──────────────────┘              │
        │                                       │
        │     Break (one issue per action)      │
        │                                       │
        │  NOT FOUND                            │
        │  ▼                                    │
        │  Action is VALID ✓                    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ ALL actions processed │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ len(issues) == 0?     │
            └───────────┬───────────┘
                        │
         ┌──────────────▼──────────────┐
         │ YES                         │
         │ Return (True, [])           │
         │ ✓ VALIDATION PASSED         │
         └─────────────────────────────┘
         
         │ NO
         │ Return (False, issues)
         │ ✗ VALIDATION FAILED
         │
         │ Issues logged:
         │ "Action 5: Generic term..."
         │ "Action 12: Empty field"
         │
         └────► TRIGGER RETRY
```

---

## 5. Retry & Fallback Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                  RETRY & FALLBACK FLOW                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ max_retries = 3       │
                    │ retry_delay = 1.0s    │
                    │ attempt = 1           │
                    └───────────┬───────────┘
                                │
                                ▼
            ┌───────────────────────────────────┐
            │ ATTEMPT LOOP (1 to max_retries)  │
            └───────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────────────┐
        │ Log: "Assignment attempt {attempt}/3"         │
        └───────────────────┬───────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────────────┐
        │ TRY:                                          │
        │                                               │
        │  ┌──────────────────────────────────────┐    │
        │  │ _assign_responsibilities()           │    │
        │  │ • Construct prompt                   │    │
        │  │ • Call LLM (temp=0.1)                │    │
        │  │ • Parse JSON response                │    │
        │  └──────────────┬───────────────────────┘    │
        │                 │                             │
        │                 ▼                             │
        │  ┌──────────────────────────────────────┐    │
        │  │ _validate_assignments()              │    │
        │  │ • Check empty fields                 │    │
        │  │ • Check generic terms                │    │
        │  └──────────────┬───────────────────────┘    │
        │                 │                             │
        │                 ▼                             │
        │         ┌───────────────┐                     │
        │         │ is_valid?     │                     │
        │         └───────┬───────┘                     │
        │                 │                             │
        │    ┌────────────▼────────────┐               │
        │    │ YES                     │               │
        │    │ Log: "Successful"       │               │
        │    │ RETURN assigned_actions │               │
        │    └─────────────────────────┘               │
        │                                               │
        │    │ NO                                       │
        │    ▼                                          │
        │ ┌──────────────────────────────────────┐     │
        │ │ Log validation issues (first 5)      │     │
        │ │ "- Action 5: Generic term..."        │     │
        │ │ "- Action 12: Empty field"           │     │
        │ └──────────────┬───────────────────────┘     │
        │                │                             │
        │                ▼                             │
        │         ┌───────────────────┐                │
        │         │ attempt < max?    │                │
        │         └──────┬────────────┘                │
        │                │                             │
        │    ┌───────────▼──────────┐                  │
        │    │ YES                  │                  │
        │    │ Log: "Retrying..."   │                  │
        │    │ sleep(delay*attempt) │                  │
        │    │ • Attempt 1: 1s      │                  │
        │    │ • Attempt 2: 2s      │                  │
        │    │ • Attempt 3: 3s      │                  │
        │    │ attempt += 1          │                  │
        │    │ LOOP BACK            │                  │
        │    └──────────────────────┘                  │
        │                                               │
        │    │ NO (Final attempt)                       │
        │    ▼                                          │
        │ ┌──────────────────────────────────────┐     │
        │ │ Log: "Validation failed after        │     │
        │ │       3 attempts. Applying fallback" │     │
        │ │                                      │     │
        │ │ RETURN _apply_fallback_assignments() │     │
        │ │ • Sets who='undefined' for invalid   │     │
        │ └──────────────────────────────────────┘     │
        │                                               │
        └───────────────────────────────────────────────┘

        ┌───────────────────────────────────────────────┐
        │ EXCEPT (LLM/API Error):                       │
        │                                               │
        │  Log error                                    │
        │                                               │
        │  attempt < max?                               │
        │                                               │
        │    ┌─────────────┐                            │
        │    │ YES         │                            │
        │    │ Retry       │                            │
        │    └─────────────┘                            │
        │                                               │
        │    │ NO                                       │
        │    │ RAISE Exception                          │
        │    │ "Failed after 3 attempts"                │
        │    ▼                                          │
        └────────────────────────────────────────────────┘
```

---

## 6. Data Flow Through Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                   WORKFLOW PIPELINE                             │
└─────────────────────────────────────────────────────────────────┘

        Orchestrator ──► Analyzer ──► Extractor ──► Deduplicator
             │               │              │              │
             │               │              │              │
             ▼               ▼              ▼              ▼
         user_config    raw_actions   refined_actions  deduplicated
                                                        
                         ▼
                    
        Selector ──► Timing ──► ⭐ ASSIGNER ⭐ ──► Formatter
           │            │              │                │
           │            │              │                │
           ▼            ▼              ▼                ▼
      selected      timed_actions  assigned_actions  final_plan
                                   + tables

┌─────────────────────────────────────────────────────────────────┐
│               ASSIGNER INPUT/OUTPUT DETAIL                      │
└─────────────────────────────────────────────────────────────────┘

INPUT (from Timing Agent):
┌────────────────────────────────┐
│ state["timed_actions"] = [    │
│   {                            │
│     "action": "Activate...",   │
│     "when": "Within 30 min",   │
│     "priority_level": "imm",   │
│     "sources": [...],          │
│     "who": ""  ← EMPTY         │
│   }                            │
│ ]                              │
│                                │
│ state["user_config"] = {       │
│   "level": "center",           │
│   "phase": "response",         │
│   "subject": "mass_casualty"   │
│ }                              │
│                                │
│ state["tables"] = [...]        │
└────────────────────────────────┘
                │
                │ Pass to Assigner
                ▼
┌────────────────────────────────────────────────┐
│         ASSIGNER PROCESSING                    │
│                                                │
│  1. Extract job titles from actions            │
│  2. Validate against reference document        │
│  3. Escalate if needed                         │
│  4. Retry on validation failure                │
│  5. Apply fallback if all retries fail         │
└────────────────┬───────────────────────────────┘
                 │
                 │ Update state
                 ▼
OUTPUT (to Formatter):
┌────────────────────────────────┐
│ state["assigned_actions"] = [ │
│   {                            │
│     "action": "Activate...",   │
│     "when": "Within 30 min",   │
│     "priority_level": "imm",   │
│     "sources": [...],          │
│     "who": "Head of            │
│             Emergency Dept."   │
│             ← ASSIGNED         │
│   }                            │
│ ]                              │
│                                │
│ state["tables"] = [...]        │
│         ← UNCHANGED            │
│                                │
│ state["current_stage"] =       │
│         "assigner"             │
└────────────────────────────────┘
```

---

## 7. Batch Processing Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                  BATCH PROCESSING FLOW                          │
└─────────────────────────────────────────────────────────────────┘

Input: 50 actions (> threshold of 30)

┌────────────────────────────────────────────┐
│ 50 Actions                                 │
│ ┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐  │
│ │1 │2 │3 │..│14│15│16│..│29│30│31│..│50│  │
│ └──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘  │
└────────────────────────────────────────────┘
                    │
                    │ Split into batches (size=15)
                    ▼
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │  Batch 1    │   │  Batch 2    │   │  Batch 3    │     │
│  │ Actions 1-15│   │Actions 16-30│   │Actions 31-45│     │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘     │
│         │                 │                 │             │
│         │                 │                 │             │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐     │
│  │  Batch 4    │   │             │   │             │     │
│  │Actions 46-50│   │             │   │             │     │
│  └──────┬──────┘   │             │   │             │     │
│         │          │             │   │             │     │
└─────────┼──────────┼─────────────┼───┼─────────────┘     │
          │          │             │   │                   │
          │          │             │   │                   │
          ▼          ▼             ▼   ▼                   │
┌─────────────────────────────────────────────────────────────┐
│           SEQUENTIAL PROCESSING                             │
│                                                             │
│  Process Batch 1 (15 actions)                               │
│  ├─ Log: "Processing batch 1/4 (15 actions)"               │
│  ├─ _assign_responsibilities_with_retry()                  │
│  │   ├─ Attempt 1 → Validate → Success ✓                  │
│  │   └─ Return 15 assigned actions                         │
│  └─ Log: "Batch 1 completed successfully"                  │
│                                                             │
│  Process Batch 2 (15 actions)                               │
│  ├─ Log: "Processing batch 2/4 (15 actions)"               │
│  ├─ _assign_responsibilities_with_retry()                  │
│  │   ├─ Attempt 1 → Validate → Failed ✗                   │
│  │   ├─ Wait 1s                                            │
│  │   ├─ Attempt 2 → Validate → Success ✓                  │
│  │   └─ Return 15 assigned actions                         │
│  └─ Log: "Batch 2 completed successfully"                  │
│                                                             │
│  Process Batch 3 (15 actions)                               │
│  ├─ Log: "Processing batch 3/4 (15 actions)"               │
│  ├─ _assign_responsibilities_with_retry()                  │
│  │   ├─ Attempt 1 → Validate → Success ✓                  │
│  │   └─ Return 15 assigned actions                         │
│  └─ Log: "Batch 3 completed successfully"                  │
│                                                             │
│  Process Batch 4 (5 actions)                                │
│  ├─ Log: "Processing batch 4/4 (5 actions)"                │
│  ├─ _assign_responsibilities_with_retry()                  │
│  │   ├─ Attempt 1 → Validate → Success ✓                  │
│  │   └─ Return 5 assigned actions                          │
│  └─ Log: "Batch 4 completed successfully"                  │
│                                                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Concatenate results
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Final Result: 50 assigned actions                           │
│ (15 + 15 + 15 + 5)                                          │
│                                                             │
│ All actions have valid 'who' assignments                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Reference Document Structure Flow

```
┌─────────────────────────────────────────────────────────────────┐
│            REFERENCE DOCUMENT HIERARCHY                         │
└─────────────────────────────────────────────────────────────────┘

At Initialization:
┌────────────────────────────────────┐
│ Load Reference Document            │
│ assigner_tools/En/                 │
│   Assigner refrence.md             │
└────────────┬───────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│ ORGANIZATIONAL STRUCTURE                                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ MINISTRY LEVEL                                     │     │
│  │  ├─ Minister of Health                             │     │
│  │  ├─ Deputy Minister of Health                      │     │
│  │  ├─ Deputy Minister for Treatment Affairs          │     │
│  │  └─ Director of Crisis Management                  │     │
│  └────────────────────────────────────────────────────┘     │
│                        │                                     │
│                        │ Hierarchical                        │
│                        │ Relationship                        │
│                        ▼                                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ UNIVERSITY LEVEL                                   │     │
│  │  ├─ University Chancellor                          │     │
│  │  ├─ Dean of Health Affairs                         │     │
│  │  └─ Director of Health Services                    │     │
│  └────────────────────────────────────────────────────┘     │
│                        │                                     │
│                        │ Hierarchical                        │
│                        │ Relationship                        │
│                        ▼                                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ CENTER/HOSPITAL LEVEL                              │     │
│  │  ├─ Hospital Director                              │     │
│  │  ├─ Head of Emergency Department                   │     │
│  │  ├─ Head of Nursing                                │     │
│  │  └─ Clinical Engineering Manager                   │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘

During Assignment:
┌────────────────────────────────────┐
│ Action: "Emergency head            │
│          activates triage"         │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Extract: "emergency head"          │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────┐
│ Search Reference for Match:                        │
│                                                    │
│  1. Exact: "emergency head" → NOT FOUND            │
│                                                    │
│  2. Semantic: "emergency head" ≈                   │
│               "Head of Emergency Department"       │
│               → FOUND ✓                            │
│                                                    │
│  3. Verify Level Context:                          │
│     user_config["level"] = "center"                │
│     Position is Center-level → VALID ✓             │
│                                                    │
│  4. Assign: who = "Head of Emergency Department"   │
└────────────────────────────────────────────────────┘
```

---

## 9. Error Handling Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                  ERROR HANDLING FLOW                            │
└─────────────────────────────────────────────────────────────────┘

                        START
                          │
                          ▼
              ┌───────────────────────┐
              │ Error Occurred        │
              └───────────┬───────────┘
                          │
          ┌───────────────▼────────────────┐
          │ Error Type?                    │
          └───────────────┬────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐  ┌──────────────┐  ┌─────────────────┐
│ Empty Actions │  │ Ref Doc      │  │ LLM Call Error  │
│               │  │ Not Found    │  │                 │
└───────┬───────┘  └──────┬───────┘  └────────┬────────┘
        │                 │                   │
        ▼                 ▼                   ▼
┌───────────────┐  ┌──────────────┐  ┌─────────────────┐
│ Log Warning   │  │ Raise        │  │ Retry?          │
│ Return Empty  │  │ FileNotFound │  │ attempt < max?  │
│ Result        │  │ Error        │  │                 │
│ ✓ Graceful    │  │ ✗ Fatal      │  └────────┬────────┘
└───────────────┘  └──────────────┘           │
                                    ┌──────────▼──────────┐
                                    │ YES                 │
                                    │ Log: "Retrying..."  │
                                    │ Wait (exponential)  │
                                    │ RETRY               │
                                    └─────────────────────┘
                                    
                                    │ NO
                                    ▼
                          ┌─────────────────────┐
                          │ Raise Exception     │
                          │ "Failed after       │
                          │  N attempts"        │
                          │ ✗ Fatal             │
                          └─────────────────────┘

        ┌──────────────────────────────────────┐
        │ Validation Error                     │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │ Retry?                               │
        │ attempt < max?                       │
        └────────────┬─────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │ YES                 │
          │ Log issues          │
          │ Wait (exponential)  │
          │ RETRY               │
          └─────────────────────┘
          
          │ NO
          ▼
┌─────────────────────────────────────────┐
│ Apply Fallback                          │
│ • Set who='undefined' for invalid       │
│ • Log all fallback applications         │
│ • Return with fallback assignments      │
│ ✓ Graceful degradation                  │
└─────────────────────────────────────────┘
```

---

## 10. Configuration Impact Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│              CONFIGURATION PARAMETERS IMPACT                    │
└─────────────────────────────────────────────────────────────────┘

┌────────────────┬──────────┬─────────┬──────────┬───────────────┐
│ Parameter      │ Low Value│ Med Val │ High Val │ Impact        │
├────────────────┼──────────┼─────────┼──────────┼───────────────┤
│ TEMPERATURE    │          │         │          │               │
│                │          │         │          │               │
│  0.0           │   ████   │         │          │ Deterministic │
│  0.1           │   ████   │  ████   │          │ Consistent ✓  │
│  0.5           │          │  ████   │  ████    │ Some variety  │
│  1.0           │          │         │  ████    │ High variety  │
│                │          │         │          │ Not recommended│
│                │          │         │          │               │
├────────────────┼──────────┼─────────┼──────────┼───────────────┤
│ BATCH_SIZE     │          │         │          │               │
│                │          │         │          │               │
│  10            │   ████   │         │          │ High quality  │
│  15            │   ████   │  ████   │          │ Balanced ✓    │
│  20            │          │  ████   │  ████    │ Faster       │
│  30+           │          │         │  ████    │ Risk overflow │
│                │          │         │          │               │
├────────────────┼──────────┼─────────┼──────────┼───────────────┤
│ MAX_RETRIES    │          │         │          │               │
│                │          │         │          │               │
│  1             │   ████   │         │          │ Low reliability│
│  3             │   ████   │  ████   │          │ Good balance ✓│
│  5             │          │  ████   │  ████    │ High cost     │
│  10            │          │         │  ████    │ Very expensive│
│                │          │         │          │               │
├────────────────┼──────────┼─────────┼──────────┼───────────────┤
│ RETRY_DELAY    │          │         │          │               │
│                │          │         │          │               │
│  0.5s          │   ████   │         │          │ Fast retry    │
│  1.0s          │   ████   │  ████   │          │ Balanced ✓    │
│  2.0s          │          │  ████   │  ████    │ Conservative  │
│  5.0s          │          │         │  ████    │ Very slow     │
└────────────────┴──────────┴─────────┴──────────┴───────────────┘

Recommended Configuration (✓):
- TEMPERATURE: 0.1
- BATCH_SIZE: 15
- MAX_RETRIES: 3
- RETRY_DELAY: 1.0
```

---

**End of Workflow Diagrams**

For detailed documentation, see:
- `ASSIGNER_AGENT_COMPREHENSIVE_DOCUMENTATION.md` (Full documentation)
- `ASSIGNER_AGENT_QUICK_REFERENCE.md` (Quick reference)

