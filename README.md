# LLM Agent Orchestration for Action Plan Development

A sophisticated multi-agent system using Large Language Models (LLMs) to automatically generate evidence-based action plans for health policy making. The system leverages LangGraph for workflow orchestration, Ollama for LLM inference, Neo4j for structural graph-based RAG, and ChromaDB for semantic vector search. It also features a comprehensive Streamlit UI for ease of use and a Persian translation workflow.

**Status:** ✅ **Production Ready** | **Version:** 3.1

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture (Version 3.0)](#architecture-version-30)
- [Streamlit UI](#streamlit-ui)
- [Persian Translation Workflow](#persian-translation-workflow)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage & Commands](#usage--commands)
- [Database Management](#database-management)
- [Data Ingestion](#data-ingestion)
- [Configuration](#configuration)
- [Agent System (Version 3.0)](#agent-system-version-30)
- [RAG Architecture](#rag-architecture)
- [Workflow](#workflow)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Overview

This system generates comprehensive action plans for any health policy subject by orchestrating a team of specialized AI agents through a quality-controlled workflow. It combines hierarchical document summarization, graph-based knowledge representation, and semantic vector search for accurate, traceable, and actionable recommendations. The system is fully accessible through a user-friendly Streamlit web interface.

### What It Does

1.  **Analyzes** user input and queries policy guidelines.
2.  **Identifies** key subjects for deep analysis.
3.  **Traverses** the knowledge graph to find relevant information.
4.  **Extracts** relevant actions from protocol documents.
5.  **Refines** and deduplicates actions.
6.  **Prioritizes** actions by timeline.
7.  **Assigns** responsibilities and resources.
8.  **Validates** outputs for quality and compliance.
9.  **Formats** into WHO/CDC-style markdown documents.
10. **Translates** the final plan into Persian.

---

## Key Features

### ✅ **Hierarchical Document Summarization**

-   **Bottom-up summarization:** Child summaries provide context for parent summaries.
-   **Context-aware:** Each section summary leverages subsection summaries.
-   **LLM-powered:** Specialized prompts for health policy documents.
-   **Source tracking:** Full file path and line range preservation.

### ✅ **Unified Knowledge Base with Smart Tagging**

-   **Single unified collection:** All documents in one Neo4j graph and ChromaDB collection.
-   **Intelligent document tagging:** Documents automatically tagged as guidelines or protocols.
-   **Simplified management:** One directory, one database, easier maintenance.

### ✅ **Advanced Semantic Search with Dual Embeddings**

-   **GraphAwareRAG (enabled by default):** Combines graph structure with semantic embeddings for precise retrieval.
-   **Automatic Neo4j embeddings:** Summary embeddings generated and stored during ingestion for fast semantic search.
-   **ChromaDB dual collections:** Separate summary and content embeddings for optimized retrieval.
-   **Semantic Phase 1:** Introduction-level queries now use embedding similarity instead of regex patterns.
-   **Reciprocal Rank Fusion (RRF):** Industry-standard method for combining multiple retrieval strategies.
-   **Maximal Marginal Relevance (MMR):** Prevents redundant results by optimizing for diversity.
-   **Graph-Expanded Retrieval:** Leverages parent/child relationships to boost relevant sections.
-   **Context Window Expansion:** Returns surrounding context for better LLM understanding.
-   **Adaptive retrieval:** Multiple modes (node_name, summary, content, automatic, hybrid, graph_expanded) for different agent needs.

### ✅ **Multi-Agent Orchestration (Version 3.0)**

-   **Specialized agents:** Each with specific expertise in a multi-phase workflow.
-   **Quality feedback loops:** Automatic validation and retry mechanisms.
-   **Source traceability:** Every recommendation linked to its source.
-   **LLM-based graph traversal:** For intelligent information retrieval.
-   **Intelligent Action Filtering:** A `Selector` agent pre-filters actions for relevance, optimizing the workflow and reducing the load on downstream agents.
-   **Action Deduplication:** An intelligent agent merges similar actions to create a concise, non-redundant plan.
-   **Comprehensive Quality Validator:** A final supervisory agent reviews the entire plan and can trigger targeted re-runs of specific agents to fix issues.

### ✅ **Comprehensive Streamlit UI**

-   **Full system control:** Manage documents, databases, and plan generation from the UI.
-   **Live progress tracking:** See agents work in real-time.
-   **Interactive graph visualization:** Explore the knowledge base.
-   **Plan history:** View, download, or re-generate previous plans.

### ✅ **Automated Persian Translation**

-   **End-to-end workflow:** Automatic translation after plan generation.
-   **Terminology validation:** Uses a dictionary to ensure accurate technical terms.
-   **High-quality output:** Utilizes a powerful translation model.

### ✅ **Professional Prompt Engineering (v3.1)**

-   **Structured evaluation frameworks:** Multi-step relevance assessment with explicit criteria.
-   **Domain-aware filtering:** Prevents cross-domain contamination (e.g., clinical vs. operational protocols).
-   **Precision-focused queries:** Smart keyword extraction with stop words filtering.
-   **Context-aware LLM instructions:** System prompts tailored for each agent's expertise.
-   **Quality-first approach:** "Precision over recall" ensures only highly relevant content is retrieved.

---

## Architecture (Version 3.0)

The system architecture has been redesigned in v3.0 to be more focused and intelligent, with a new deduplication step and a comprehensive quality validation loop.

```
Orchestrator → Analyzer → Phase3 → Extractor → Selector → Deduplicator → Prioritizer → Assigner → Formatter
      ↑                                                                                 ↓
      └───────────────────────────(Agent Rerun on Quality Failure)─────────────────────── ComprehensiveQualityValidator
```

This multi-phase approach allows for a deeper and more accurate analysis of the user's request, leading to higher quality action plans.

---

## Streamlit UI

A comprehensive, production-ready Streamlit web interface provides full access to all backend capabilities with an intuitive, professional design.

-   **Dashboard:** System status, database stats, and quick actions.
-   **Graph Explorer:** Interactive Neo4j graph visualization.
-   **Document Manager:** Upload, manage, and ingest documents.
-   **Plan Generator:** Generate action plans with live progress tracking.
-   **Plan History:** Browse and view past plans.
-   **Settings:** View all configuration parameters.

Refer to `QUICK_START_UI.md` for a detailed guide on using the UI.

---

## Persian Translation Workflow

The system includes an automated workflow to translate the final English action plan into Persian.

1.  **Translator:** Creates a verbatim Persian translation.
2.  **Segmentation:** Splits the text into chunks for analysis.
3.  **Term Identifier:** Finds technical terms.
4.  **Dictionary Lookup:** Validates terms against `Dictionary.md`.
5.  **Refinement:** Applies corrections to produce the final Persian plan.

---

## Quick Start

### Using the Streamlit UI (Recommended)

1.  **Launch the UI:**
    ```bash
    ./launch_ui.sh
    ```
2.  **Open in browser:** `http://localhost:8501`
3.  **Check System Status:** Ensure all systems are green in the sidebar.
4.  **Upload Documents:** Use the "Documents" tab to upload and ingest your policy documents.
5.  **Generate Plan:** Go to the "Generate Plan" tab, enter a subject, and click generate.

### Using the Command Line

1.  **Initialize Databases:**
    ```bash
    python3 main.py init-db
    ```
2.  **Ingest Documents:**
    ```bash
    python3 main.py ingest --docs-dir /path/to/your/docs
    ```
3.  **Generate Action Plan:**
    ```bash
    python3 main.py generate --subject "hand hygiene protocol implementation"
    ```

---

## Prerequisites

-   Python 3.9+
-   Ollama with `gpt-oss:20b`, `embeddinggemma:latest`, and `gemma3:27b` models.
-   Neo4j Database (Docker recommended).
-   ChromaDB (embedded, no setup needed).

---

## Installation

1.  **Navigate to Project:**
    ```bash
    cd /storage03/Saboori/ActionPlan/Agents
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create Environment File:**
    ```bash
    cp .env.example .env
    # Edit .env with your settings
    ```
4.  **Initialize Databases:**
    ```bash
    python3 main.py init-db
    ```

---

## Usage & Commands

### Generate Action Plan

-   **UI:** Use the "Generate Plan" tab.
-   **CLI:**
    ```bash
    python3 main.py generate --subject "your subject here"
    ```

### Batch Generation (CLI)

```bash
while read subject; do
    echo "Generating: $subject"
    python3 main.py generate --subject "$subject"
done < subjects.txt
```

### Clearing and Re-ingesting All Data (CLI)

To perform a clean reset of all databases and re-ingest your documents from scratch, follow these two steps. This is useful when you have updated your source documents or changed the ingestion logic.

1.  **Clear All Databases:**

    This command will wipe the Neo4j graph and the ChromaDB vector stores.

    ```bash
    python3 main.py clear-db --database both
    ```

2.  **Re-ingest Documents:**

    This command will rebuild the Neo4j graph and the ChromaDB vector stores from your source documents. **Note:** The graph-building process can be very slow as it generates a summary for every section of every document. Please allow it to run to completion.

    ```bash
    python3 main.py ingest --docs-dir /path/to/your/docs
    ```

---

## Database Management

-   **Initialize Databases:** `python3 main.py init-db`
-   **Show Statistics:** `python3 main.py stats`
-   **Clear Databases:** `python3 main.py clear-db --database <neo4j|chromadb|both>`

---

## Data Ingestion

-   **UI:** Use the "Documents" tab.
-   **CLI:** `python3 main.py ingest --docs-dir /path/to/docs`

The system uses a unified knowledge base. All documents are placed in a single directory and are auto-tagged as "guideline" or "protocol" based on filenames.

### Automatic Embedding Generation (v3.1)

During ingestion, the system now automatically:
1. **Builds Neo4j graph** with hierarchical structure and summaries
2. **Generates embeddings** for all document nodes using Ollama's `embeddinggemma:latest`
3. **Stores embeddings in Neo4j** as `summary_embedding` properties for fast semantic search
4. **Creates ChromaDB collections** with dual embeddings (summary + content)
5. **Reports statistics** showing embedding coverage percentage

**No manual steps required!** Semantic search works out of the box after ingestion.

---

## Configuration

All configuration is managed through the `.env` file. See `.env.example` for all available options.

Key settings include:
-   Database credentials
-   Ollama model names and parameters
-   Document paths
-   RAG and workflow settings

---

## Agent System (Version 3.0)

The v3.0 agent system uses a multi-phase approach for deeper analysis.

1.  **Orchestrator Agent:** Transforms the user's request into a clear, actionable problem statement to guide the entire multi-agent system. It leverages a sophisticated internal prompt and can accept an optional, detailed `Description` from the user to create a highly focused starting point for the workflow.
2.  **Analyzer Agent (2-Phase):**
    -   **Phase 1: Document Retrieval:** Analyzes the user's request to find the most relevant documents from the knowledge base.
    -   **Phase 2: Node Identification:** Identifies the specific nodes (sections) within the retrieved documents that are most relevant for deep analysis.
3.  **Phase3 Agent:** Performs a deep analysis of the identified nodes by traversing the knowledge graph to extract detailed information and context.
4.  **Extractor Agent:** Extracts structured actions (who, when, what) from the rich context provided by the Phase3 Agent. It validates the extracted actions and flags any that are incomplete.
5.  **Selector Agent:** Filters the extracted actions based on semantic relevance to the user's request. This crucial step significantly reduces the workload for subsequent agents by ensuring they only process pertinent information.
6.  **Deduplicator Agent:** Intelligently merges the now-filtered list of similar or duplicate actions, creating a concise and non-redundant set of tasks.
7.  **Prioritizer Agent:** Assigns timelines and urgency to each action.
8.  **Assigner Agent:** Assigns responsibilities and resources for each action.
9.  **Formatter Agent:** Compiles all the structured information into a final, human-readable action plan in WHO/CDC-style markdown format.
10. **Comprehensive Quality Validator:** A new supervisory agent that reviews the final formatted plan. It can:
    -   **Approve** the plan if it meets quality standards.
    -   **Self-Repair** minor issues directly in the plan.
    -   **Trigger an Agent Rerun** by sending the plan back to a specific agent with targeted feedback if significant revisions are needed.
11. **Translation Agents:** A team of 5 agents for the Persian translation workflow.

---

## RAG Architecture

The system uses an advanced hybrid RAG approach with semantic embeddings:

### GraphAwareRAG (Default, v3.1)
-   **Neo4j + Embeddings:** Combines graph structure with vector embeddings stored directly in Neo4j
-   **Fast semantic search:** Cosine similarity computed on-demand from stored embeddings
-   **Multi-mode retrieval:**
    - `node_name`: Fast keyword/title matching via Neo4j
    - `summary`: Search using summary embeddings (lighter, faster)
    - `content`: Search using content embeddings (comprehensive)
    - `automatic`: Dynamically selects mode based on query complexity
    - `hybrid`: Combines graph structure + embedding similarity with weighted scoring

### ChromaDB Integration
-   **Dual collections:** Separate summary and content embeddings for optimized retrieval
-   **Batch processing:** Efficient embedding generation with caching
-   **Synchronized:** Embeddings added to both Neo4j and ChromaDB during ingestion

### Advanced Retrieval Techniques (v3.1)
-   **Semantic-First Approach:** All retrieval now uses embeddings as primary mechanism
-   **Reciprocal Rank Fusion:** Combines semantic + keyword results optimally (RRF formula: Σ(1/(k+rank)))
-   **Maximal Marginal Relevance:** Balances relevance vs diversity (λ parameter configurable)
-   **Graph Expansion:** Boosts scores based on related node similarity (configurable depth/boost)
-   **Context Windows:** Automatically includes parent/child section context
-   **Multi-Mode Retrieval:**
    - `semantic`: Pure embedding similarity (Phase 1 default)
    - `hybrid`: RRF fusion of semantic + keyword (Phase 2 default)
    - `graph_expanded`: Hybrid + relationship boosting
    - `context_window`: Hybrid + parent/child context

### Intelligent Query Processing
-   **LLM-Generated Queries:** Professional prompts guide query generation
-   **Semantic ranking:** Results scored 0.0-1.0 based on cosine similarity
-   **Domain-aware filtering:** LLM-based evaluation prevents cross-domain false positives
-   **Diversity optimization:** MMR ensures varied, non-redundant results

This architecture implements RAG best practices from 2024-2025 research, ensuring agents retrieve only the most relevant, diverse, and contextually-rich content for their specific tasks.

---

## Workflow

The workflow is managed by LangGraph and follows the agent system described above. A new `ComprehensiveQualityValidator` agent now sits at the end of the main workflow to ensure the final output is of high quality. If the validator detects issues, it can send the workflow back to any of the previous agents for a targeted re-run, creating a powerful quality control loop.

---

## Verification & Testing Tools (v3.1)

The system includes diagnostic tools for verifying embeddings and testing retrieval quality:

### Verify Embeddings

Check that all Neo4j nodes have embeddings:
```bash
python scripts/verify_embeddings.py
```

**Output:**
- Total heading nodes count
- Nodes with embeddings count
- Coverage percentage
- Embedding dimension validation
- Sample nodes with/without embeddings

### Test Analyzer Fix

Validate that semantic search returns relevant results:
```bash
python scripts/test_analyzer_fix.py
```

**Validates:**
- ✓ Scores are varied (semantic ranking working)
- ✓ No irrelevant cross-domain nodes
- ✓ Scores in valid range [0.0, 1.0]

### Manually Add Embeddings (If Needed)

If you have an older database without embeddings:
```bash
python scripts/add_embeddings_to_neo4j.py
```

This generates and stores embeddings for all existing Neo4j nodes. **Note:** Not needed for fresh ingestions after v3.1.

---

## Troubleshooting

-   **ChromaDB Instance Conflict:** This can happen in Streamlit due to multiple components creating clients. The system now uses a singleton pattern to prevent this. If you see this error, restart the Streamlit app.
-   **Extractor Returning 0 Actions:** This was a critical bug caused by a document name mismatch. It has been fixed by using graph traversals instead of name matching.
-   **Phase3 Filtering All Nodes:** The scoring threshold was sometimes too strict. This has been fixed by lowering the default threshold and adding a fallback mechanism to guarantee a minimum number of nodes are returned.
-   **Application Hanging on Large Inputs:** Previously, agents like the `Selector` or `Deduplicator` could hang when processing a large number of actions in a single LLM call. This has been resolved by implementing robust batch processing, ensuring the system remains responsive even with complex documents.
-   **Final Plan Quality Issues:** Previously, quality checks were intermediate. Now, a `ComprehensiveQualityValidator` performs a final review and can trigger re-runs of specific agents to fix issues, making the output more robust.
-   **Irrelevant Node Retrieval (Fixed in v3.1):** Previously, the analyzer could return irrelevant nodes from different domains (e.g., clinical protocols for operational queries). This has been completely resolved through: (1) enabling semantic search with Neo4j embeddings, (2) improved keyword filtering with stop words, (3) enhanced LLM prompts with structured evaluation frameworks, and (4) domain-aware filtering rules.
-   **For UI issues:** Check `streamlit.log`.
-   **For backend issues:** Check `action_plan_orchestration.log`.

---

## Development

-   **Running Tests:**
    ```bash
    python test_analyzer_system.py
    python test_refactored_extractor.py
    ```
-   **Debugging:** Use `--log-level DEBUG` for verbose logging.
-   **Code Style:** Follow PEP 8 and use type hints.

---
