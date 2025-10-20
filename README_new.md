# LLM Agent Orchestration for Action Plan Development

A sophisticated multi-agent system using Large Language Models (LLMs) to automatically generate evidence-based action plans for health policy making. The system leverages LangGraph for workflow orchestration, Ollama for LLM inference, Neo4j for structural graph-based RAG, and ChromaDB for semantic vector search. It also features a comprehensive Streamlit UI for ease of use and a Persian translation workflow.

**Status:** ✅ **Production Ready** | **Version:** 3.0

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

### ✅ **Hybrid RAG Architecture**

-   **Graph RAG (Neo4j):** Structural document navigation.
-   **Vector RAG (ChromaDB):** Semantic search using Ollama embeddings.
-   **Adaptive retrieval:** Multiple modes for different agents.

### ✅ **Multi-Agent Orchestration (Version 3.0)**

-   **Specialized agents:** Each with specific expertise in a multi-phase workflow.
-   **Quality feedback loops:** Automatic validation and retry mechanisms.
-   **Source traceability:** Every recommendation linked to its source.
-   **LLM-based graph traversal:** For intelligent information retrieval.

### ✅ **Comprehensive Streamlit UI**

-   **Full system control:** Manage documents, databases, and plan generation from the UI.
-   **Live progress tracking:** See agents work in real-time.
-   **Interactive graph visualization:** Explore the knowledge base.
-   **Plan history:** View, download, or re-generate previous plans.

### ✅ **Automated Persian Translation**

-   **End-to-end workflow:** Automatic translation after plan generation.
-   **Terminology validation:** Uses a dictionary to ensure accurate technical terms.
-   **High-quality output:** Utilizes a powerful translation model.

---

## Architecture (Version 3.0)

The system architecture has been redesigned in v3.0 to be more focused and intelligent.

```
Orchestrator → Analyzer (2-Phase) → phase3 → Extractor → Prioritizer → Assigner → Formatter
     ↓              ↓                     ↓            ↓
   Topics    Subjects (3-8)     Subject Nodes    Actions (who/when/what)
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

1.  **Orchestrator Agent:** Coordinates the workflow and defines plan structure.
2.  **Analyzer Agent (2-Phase):**
    -   **Phase 1: Context Building:** Finds relevant documents.
    -   **Phase 2: Subject Identification:** Generates specific subjects for deep analysis.
3.  **phase3 Agent:** Performs deep analysis by traversing the knowledge graph with LLM-based relevance scoring.
4.  **Extractor Agent:** Extracts structured actions (who/when/what).
5.  **Prioritizer Agent:** Assigns timelines and urgency.
6.  **Assigner Agent:** Assigns responsibilities and resources.
7.  **Quality Checker Agent:** Validates outputs at each stage.
8.  **Formatter Agent:** Compiles the final document.
9.  **Translation Agents:** A team of 5 agents for the Persian translation workflow.

---

## RAG Architecture

The system uses a hybrid RAG approach, combining:

-   **Graph RAG (Neo4j):** For structural navigation and hierarchical lookups.
-   **Vector RAG (ChromaDB):** For semantic search and content-based retrieval.

This allows agents to query the knowledge base in the most effective way for their specific task.

---

## Workflow

The workflow is managed by LangGraph and follows the agent system described above. Quality checks are performed between major stages, and if the quality score is below a threshold, the previous agent is asked to retry with feedback.

---

## Troubleshooting

-   **ChromaDB Instance Conflict:** This can happen in Streamlit due to multiple components creating clients. The system now uses a singleton pattern to prevent this. If you see this error, restart the Streamlit app.
-   **Extractor Returning 0 Actions:** This was a critical bug caused by a document name mismatch. It has been fixed by using graph traversals instead of name matching.
-   **phase3 Filtering All Nodes:** The scoring threshold was sometimes too strict. This has been fixed by lowering the default threshold and adding a fallback mechanism to guarantee a minimum number of nodes are returned.
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
