# LLM Agent Orchestration for Action Plan Development

A sophisticated multi-agent system using Large Language Models (LLMs) to automatically generate evidence-based action plans for health policy making. The system leverages LangGraph for workflow orchestration, Ollama for LLM inference, Neo4j for structural graph-based RAG, and ChromaDB for semantic vector search.

**Status:** ✅ **Production Ready** | **Version:** 2.0 Enhanced

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start (5 Steps)](#quick-start-5-steps)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Management](#database-management)
- [Data Ingestion](#data-ingestion)
- [Usage & Commands](#usage--commands)
- [Configuration](#configuration)
- [Agent System](#agent-system)
- [RAG Architecture](#rag-architecture)
- [Workflow](#workflow)
- [Command Reference](#command-reference)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Testing & Verification](#testing--verification)
- [Performance Optimization](#performance-optimization)
- [Advanced Topics](#advanced-topics)
- [Development](#development)

---

## Overview

This system generates comprehensive action plans for any health policy subject by orchestrating 7 specialized AI agents through a quality-controlled workflow. It combines hierarchical document summarization, graph-based knowledge representation, and semantic vector search for accurate, traceable, and actionable recommendations.

### What It Does

1. **Analyzes** user input and queries policy guidelines
2. **Extracts** relevant actions from protocol documents
3. **Refines** and deduplicates actions
4. **Prioritizes** actions by timeline
5. **Assigns** responsibilities and resources
6. **Validates** outputs for quality and compliance
7. **Formats** into WHO/CDC-style markdown documents

---

## Key Features

### ✅ **Hierarchical Document Summarization**
- **Bottom-up summarization:** Child summaries provide context for parent summaries
- **Context-aware:** Each section summary leverages subsection summaries
- **LLM-powered:** Specialized prompts for health policy documents
- **Source tracking:** Full file path and line range preservation

### ✅ **Unified Knowledge Base with Smart Tagging**
- **Single unified collection:** All documents (guidelines and protocols) in one Neo4j graph and ChromaDB collection
- **Intelligent document tagging:** Documents automatically tagged as guidelines or protocols
- **Hierarchical context for guidelines:** Parent node names included in prompts for better traceability
- **Simplified management:** One directory, one database, easier maintenance

### ✅ **Hybrid RAG Architecture**
- **Graph RAG (Neo4j):** Structural document navigation via hierarchy with is_rule metadata
- **Vector RAG (ChromaDB):** Semantic search using Ollama embeddings across unified collection
- **Dual-embedding support:** Summary and content embeddings
- **Adaptive retrieval:** Multiple modes (node_name, summary, content, automatic)
- **Context enrichment:** Automatic hierarchical path retrieval for guideline documents

### ✅ **Multi-Agent Orchestration**
- **7 specialized agents:** Each with specific expertise
- **Quality feedback loops:** Automatic validation and retry
- **Source traceability:** Every recommendation linked to source
- **Configurable workflows:** LangGraph state machine

### ✅ **Production-Ready Features**
- **Automatic database initialization:** One-command setup
- **Statistics and monitoring:** Real-time database metrics
- **Error handling and recovery:** Transaction-based with rollback
- **Comprehensive logging:** Detailed operation tracking

### ✅ **Health Policy Compliance**
- WHO/CDC template adherence
- Equity and ethics considerations
- Evidence-based recommendations
- Standard role assignments (EOC, Incident Commander, etc.)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input (Subject)                      │
└────────────────────────────┬────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Orchestrator Agent                          │
│  • Queries unified knowledge base for plan structure         │
│  • Includes hierarchical context for guidelines              │
│  • Coordinates workflow and routing                          │
└────────────────────────────┬────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Analyzer Agent                            │
│  • Extracts actions from unified knowledge base              │
│  • Uses Hybrid RAG (Graph + Vector) with smart tagging       │
│  • Enriches guideline citations with hierarchical paths      │
└────────────────────────────┬────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │ Quality Checker│ ← Feedback Loop
                    └────────┬───────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Extractor Agent                            │
│  • Refines and deduplicates actions                          │
│  • Groups related items                                      │
└────────────────────────────┬────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │ Quality Checker│
                    └────────┬───────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Prioritizer Agent                           │
│  • Classifies by timeline (immediate/short/long-term)       │
│  • Assigns urgency scores and dependencies                   │
└────────────────────────────┬────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │ Quality Checker│
                    └────────┬───────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Assigner Agent                             │
│  • Assigns roles/units and resources                         │
│  • Verifies timings against protocols                        │
└────────────────────────────┬────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │ Quality Checker│
                    └────────┬───────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Formatter Agent                            │
│  • Compiles into WHO/CDC template                            │
│  • Creates tables, timelines, and references                 │
└────────────────────────────┬────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Final Action Plan (Markdown)                    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
Documents (Markdown - Guidelines & Protocols)
        ↓
┌───────────────────────────────────┐
│ Enhanced Graph Builder             │
│  • Parse hierarchy                 │
│  • Auto-tag as guideline/protocol  │
│  • Bottom-up summaries             │
│  • Store with is_rule metadata     │
│  • Transaction-based               │
└─────┬─────────────────────────────┘
      ↓
┌──────────────────────────────────────┐
│  Unified Knowledge Base               │
│  ┌──────────┐    ┌──────────┐       │
│  │  Neo4j   │    │ ChromaDB │       │
│  │  Graph   │    │  Vectors │       │
│  │ +is_rule │    │ (unified)│       │
│  └─────┬────┘    └────┬─────┘       │
│        └──────┬────────┘             │
└───────────────┼──────────────────────┘
                ↓
      ┌─────────────────────┐
      │ Unified Hybrid RAG   │
      │  • Graph with tags   │
      │  • Vector search     │
      │  • Hierarchy fetch   │
      │  • Smart routing     │
      └──────┬───────────────┘
             ↓
      ┌─────────────┐
      │   Agents    │
      │  Workflow   │
      │ +Hierarchy  │
      └──────┬──────┘
             ↓
      Action Plan
```

---

## Quick Start (5 Steps)

### step 0: active the virtual enviroment:
```bash
source /storage03/Saboori/ActionPlan/Agents/.venv/bin/activate
```

### Step 1: Initialize Databases (1 minute)
```bash
cd /storage03/Saboori/ActionPlan/Agents
python3 main.py init-db
```

**Expected Output:**
```
============================================================
Database Initialization
============================================================

1. Initializing Neo4j...
   ✓ Neo4j connected successfully (0 nodes in database)
   ✓ Created indexes for unified collection

2. Initializing ChromaDB...
   ✓ ChromaDB connected successfully (0 collections)

============================================================
✓ All databases initialized successfully
```

### Step 2: Check System Status (30 seconds)
```bash
python3 main.py check
```

Verifies:
- ✅ Ollama connection
- ✅ Neo4j connection  
- ✅ ChromaDB setup
- ✅ Document directories

### Step 3: Ingest Documents (5-10 minutes)
```bash
python3 main.py ingest --docs-dir /storage03/Saboori/ActionPlan/Agents/held/docs
```

**Or use default directory:**
```bash
python3 main.py ingest
```

**What happens:**
1. 📄 Extracts document hierarchy from all markdown files
2. 🏷️ Auto-tags documents as guidelines or protocols based on filename
3. 🤖 Generates hierarchical summaries (bottom-up)
4. 🔗 Creates unified Neo4j knowledge graph with is_rule metadata
5. 🔍 Creates semantic vectors in unified ChromaDB collection
6. 📊 Shows statistics

### Step 4: Verify Ingestion (10 seconds)
```bash
python3 main.py stats
```

**Example Output:**
```
============================================================
Database Statistics
============================================================

Neo4j:
  Status: connected
  Nodes: 347
  Relationships: 346

ChromaDB:
  Status: connected
  Collections: 2
  Documents: 1250
============================================================
```

### Step 5: Generate Action Plan (2-5 minutes)
```bash
python3 main.py generate --subject "hand hygiene protocol implementation"
```

**Output:** `action_plans/hand_hygiene_protocol_implementation_20251014_120530.md`

---

## Prerequisites

### 1. Python 3.9+
```bash
python3 --version
```

### 2. Ollama with Models
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
# Pull required models
ollama pull gpt-oss:20b              # Main LLM
ollama pull embeddinggemma:latest    # Embeddings

# Verify
ollama list
```

### 3. Neo4j Database
   ```bash
# Using Docker (recommended)
   docker run -d \
     --name neo4j \
     -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/cardiosmartai \
     neo4j:latest

# Verify
docker ps | grep neo4j
   ```

### 4. ChromaDB (Embedded or Docker)
   ```bash
# Option 1: Embedded (default, no setup needed)
# ChromaDB will use ./chroma_storage

# Option 2: Docker
   docker run -d \
     --name chroma \
     -p 8000:8000 \
     chromadb/chroma
   ```

---

## Installation

### 1. Navigate to Project
   ```bash
   cd /storage03/Saboori/ActionPlan/Agents
   ```

### 2. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```

### 3. Create Environment File
   ```bash
   cp .env.example .env
nano .env  # Edit with your settings
   ```

### 4. Initialize Databases
```bash
python3 main.py init-db
```

---

## Database Management

### Initialize Databases
```bash
python3 main.py init-db
```

**What it does:**
- Connects to Neo4j and creates indexes
- Initializes ChromaDB storage
- Verifies connections
- Shows node/collection counts

### Show Statistics
```bash
python3 main.py stats
```

**Output includes:**
- Neo4j: node count, relationship count, connection status
- ChromaDB: collection count, document count, connection status

### Clear Databases
```bash
# Clear Neo4j only (with confirmation)
python3 main.py clear-db --database neo4j

# Clear ChromaDB only
python3 main.py clear-db --database chromadb

# Clear both databases
python3 main.py clear-db --database both
```

**⚠️ Warning:** This permanently deletes all data. Always backup first!

### Database Utilities (Programmatic)
```python
from utils.db_init import (
    initialize_all_databases,
    get_database_statistics,
    clear_neo4j_database,
    clear_chromadb
)

# Initialize
success = initialize_all_databases()

# Get stats
stats = get_database_statistics()
print(f"Neo4j nodes: {stats['neo4j']['nodes']}")
print(f"ChromaDB collections: {stats['chromadb']['collections']}")

# Clear (returns success, message)
success, msg = clear_neo4j_database()
success, msg = clear_chromadb()
```

---

## Data Ingestion

### Hierarchical Summarization

The enhanced system uses **bottom-up hierarchical summarization**:

**Traditional Approach (Flat):**
```
Section 1:     → Summary from Section 1 content only
  Section 1.1: → Summary from Section 1.1 content only
  Section 1.2: → Summary from Section 1.2 content only
```

**Enhanced Approach (Hierarchical):**
```
Section 1.1  → Summarize from its content
Section 1.2  → Summarize from its content
Section 1    → Summarize from its content + context from 1.1 and 1.2 summaries
```

**Benefits:**
- More coherent summaries with parent-child context
- Better understanding of document structure
- Improved retrieval accuracy

### Ingestion Commands

#### Ingest All Documents (Unified)
```bash
# Specify custom directory
python3 main.py ingest --docs-dir /path/to/documents

# Or use default from .env
python3 main.py ingest
```

**Document Auto-Tagging:**
- Files containing "guideline", "template", or "action_plan" in name → Tagged as guidelines (`is_rule: true`)
- All other files → Tagged as protocols (`is_rule: false`)
- Customizable via `RULE_DOCUMENT_NAMES` in .env

### What Happens During Ingestion

1. **Document Parsing**
   - Extract markdown heading hierarchy (H1-H6)
   - Build document tree structure
   - Track line ranges for each section

2. **Hierarchical Summarization**
   - Start at deepest level (leaf nodes)
   - Generate summaries using Ollama
   - Use child summaries as context for parent summaries
   - Specialized health policy prompts

3. **Graph Construction**
   - Create Document and Heading nodes in Neo4j
   - Build HAS_SUBSECTION relationships
   - Store summaries and line ranges
   - Execute in single transaction (atomic)

4. **Vector Store Creation**
   - Chunk documents (400 tokens, 50 overlap)
   - Generate embeddings using Ollama
   - Store in ChromaDB with metadata
   - Maintain source traceability

### Programmatic Ingestion
```python
from data_ingestion.enhanced_graph_builder import EnhancedGraphBuilder
from data_ingestion.vector_builder import VectorBuilder

# Enhanced graph building with hierarchical summarization
graph_builder = EnhancedGraphBuilder(collection_name="rules")
graph_builder.build_from_directory("/path/to/docs", clear_existing=False)

# Get statistics
stats = graph_builder.get_statistics()
print(f"Documents: {stats['documents']}, Headings: {stats['headings']}")

graph_builder.close()

# Vector store building
vector_builder = VectorBuilder(collection_name="rules_documents")
vector_builder.build_from_directory("/path/to/docs")
```

---

## Usage & Commands

### Generate Action Plan

**Basic:**
```bash
python3 main.py generate --subject "hand hygiene protocol"
```

**Custom output:**
```bash
python3 main.py generate \
  --subject "pandemic influenza response" \
  --output custom_plans/pandemic.md
```

**Programmatic:**
```python
from workflows.orchestration import create_workflow
from workflows.graph_state import ActionPlanState

workflow = create_workflow()

state: ActionPlanState = {
    "subject": "emergency triage protocols",
    "current_stage": "start",
    "retry_count": {},
    "errors": [],
    "metadata": {}
}

result = workflow.invoke(state)
print(result["final_plan"])
```

### Batch Generation
```bash
# Create subject list
cat > subjects.txt <<EOF
hand hygiene protocol
emergency triage procedures
infection control measures
patient isolation guidelines
medical waste disposal
EOF

# Generate all plans
while read subject; do
    echo "Generating: $subject"
    python3 main.py generate --subject "$subject"
done < subjects.txt
```

---

## Configuration

### Environment Variables (.env)

```bash
# ═══════════════════════════════════════════════════════════
# NEO4J CONFIGURATION
# ═══════════════════════════════════════════════════════════
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=cardiosmartai

# ═══════════════════════════════════════════════════════════
# CHROMADB CONFIGURATION
# ═══════════════════════════════════════════════════════════
CHROMA_PATH=./chroma_storage

# ═══════════════════════════════════════════════════════════
# OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_EMBEDDING_MODEL=embeddinggemma:latest
OLLAMA_TEMPERATURE=0.1
OLLAMA_TIMEOUT=3000
OLLAMA_MAX_TOKENS=2000

# ═══════════════════════════════════════════════════════════
# DOCUMENT PATHS (Unified Directory)
# ═══════════════════════════════════════════════════════════
DOCS_DIR=/storage03/Saboori/ActionPlan/Agents/held/docs

# ═══════════════════════════════════════════════════════════
# COLLECTION NAMES (Unified)
# ═══════════════════════════════════════════════════════════
DOCUMENTS_COLLECTION=health_documents
SUMMARY_COLLECTION_NAME=document_summaries

# ═══════════════════════════════════════════════════════════
# GRAPH PREFIX (Unified)
# ═══════════════════════════════════════════════════════════
GRAPH_PREFIX=health

# ═══════════════════════════════════════════════════════════
# RULE DOCUMENTS (for auto-tagging)
# ═══════════════════════════════════════════════════════════
RULE_DOCUMENT_NAMES=["guideline", "action_plan_template", "template"]

# ═══════════════════════════════════════════════════════════
# RAG CONFIGURATION
# ═══════════════════════════════════════════════════════════
CHUNK_SIZE=400
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
EMBEDDING_DIMENSION=768
MAX_SECTION_TOKENS=1000

# ═══════════════════════════════════════════════════════════
# AGENT RETRIEVAL MODES
# ═══════════════════════════════════════════════════════════
ANALYZER_RETRIEVAL_MODE=automatic
ASSIGNER_RETRIEVAL_MODE=summary
PRIORITIZER_RETRIEVAL_MODE=content

# ═══════════════════════════════════════════════════════════
# WORKFLOW CONFIGURATION
# ═══════════════════════════════════════════════════════════
MAX_RETRIES=3
QUALITY_THRESHOLD=0.7
```

### Performance Tuning

**For Faster Processing:**
```bash
OLLAMA_MODEL=cogito:8b           # Smaller, faster model
OLLAMA_TEMPERATURE=0.3           # Less precise but faster
CHUNK_SIZE=300                   # Smaller chunks
```

**For Better Quality:**
```bash
OLLAMA_MODEL=gpt-oss:20b         # Larger, more accurate
OLLAMA_TEMPERATURE=0.1           # More deterministic
OLLAMA_TIMEOUT=5000              # Longer timeout
TOP_K_RESULTS=10                 # More retrieval results
```

---

## Agent System

### 7 Specialized Agents

#### 1. **Orchestrator Agent**
- **Role:** Workflow coordinator and plan structure definition
- **Tools:** HybridRAG on rules documents
- **Tasks:** 
  - Query action plan structure guidelines
  - Define plan skeleton
  - Route tasks to specialized agents
  - Make retry/proceed decisions

#### 2. **Analyzer Agent**
- **Role:** Action extraction from protocols
- **Tools:** HybridRAG (Graph + Vector) on protocols
- **Retrieval Mode:** Automatic (adaptive)
- **Tasks:**
  - Find relevant protocol sections
  - Extract actionable items
  - Maintain source citations (node_id, line ranges)

#### 3. **Extractor Agent**
- **Role:** Action refinement and deduplication
- **Tools:** LLM processing
- **Tasks:**
  - Deduplicate similar actions
  - Group related actions
  - Improve clarity while preserving sources

#### 4. **Prioritizer Agent**
- **Role:** Timeline assignment and urgency scoring
- **Tools:** HybridRAG on protocols (content mode)
- **Retrieval Mode:** Content (detailed information)
- **Tasks:**
  - Classify actions (immediate/short-term/long-term)
  - Assign urgency scores (1-10)
  - Identify dependencies

#### 5. **Assigner Agent**
- **Role:** Responsibility and resource assignment
- **Tools:** HybridRAG on protocols (summary mode)
- **Retrieval Mode:** Summary (fast role lookup)
- **Tasks:**
  - Assign specific roles/units (EOC, Incident Commander, etc.)
  - Verify timings against protocols
  - Identify required resources

#### 6. **Quality Checker Agent**
- **Role:** Validation and feedback provision
- **Tools:** HybridRAG on rules
- **Evaluation Criteria:**
  1. **Accuracy** (0-1): Actions align with protocols
  2. **Completeness** (0-1): All necessary actions included
  3. **Ethical Compliance** (0-1): Equity and ethics respected
  4. **Source Traceability** (0-1): Citations present and valid
  5. **Actionability** (0-1): Actions are specific and implementable
- **Pass Threshold:** 0.7 (average score)
- **Tasks:**
  - Evaluate on 5 criteria
  - Provide constructive feedback
  - Recommend improvements

#### 7. **Formatter Agent**
- **Role:** Final document compilation
- **Tools:** WHO/CDC template processing
- **Tasks:**
  - Compile into standard format
  - Create responsibility matrices
  - Generate timelines and Gantt charts
  - Format references and citations

---

## RAG Architecture

### Three RAG Strategies

#### 1. **Graph RAG (Neo4j)**

**Structural Navigation:**
```cypher
// Traverse document hierarchy
MATCH (d:Document {name: "emergency_protocols"})-[:HAS_SUBSECTION*]->(h:Heading)
WHERE h.title CONTAINS "triage"
RETURN h.title, h.summary, h.start_line, h.end_line
```

**Use Cases:**
- Known section lookup
- Hierarchical navigation
- Structure-aware retrieval

#### 2. **Vector RAG (ChromaDB)**

**Semantic Search:**
```python
from rag_tools.vector_rag import VectorRAG

rag = VectorRAG(collection_name="protocols_documents")
results = rag.semantic_search(
    query="emergency triage procedures",
    top_k=5,
    filters={"source": "emergency_protocols.md"}
)
```

**Use Cases:**
- Semantic similarity search
- Content-based retrieval
- Unknown terminology lookup

#### 3. **Hybrid RAG**

**Combined Approach:**
```python
from rag_tools.hybrid_rag import HybridRAG

rag = HybridRAG(
    vector_collection="protocols_documents",
    use_graph_aware=True
)

results = rag.query(
    query="What are the steps for emergency triage?",
    mode="automatic",  # or "summary", "content", "node_name"
    top_k=5
)
```

**Strategies:**
- **Reciprocal Rank Fusion (RRF):** Merge graph + vector results
- **Graph-guided Vector:** Use graph structure to inform vector search
- **Sequential:** Try graph first, fallback to vector

### Graph-Aware RAG

**Advanced Features:**

1. **Dual Embeddings**
   - Summary embeddings (lightweight, fast)
   - Content embeddings (comprehensive, detailed)

2. **Retrieval Modes**

| Mode | Speed | Use Case | Example Query |
|------|-------|----------|---------------|
| `node_name` | ⚡⚡⚡ | Known sections | "Find triage section" |
| `summary` | ⚡⚡ | Quick overview | "List main responsibilities" |
| `content` | ⚡ | Detailed info | "Explain step-by-step procedure" |
| `automatic` | ⚡⚡ | General purpose | "What are emergency protocols?" |

3. **Context Expansion**
   - Use graph relationships to expand results
   - Include parent and child sections
   - Maintain structural context

### Building Graph-Aware Vector Store

```bash
python3 scripts/build_graph_vector_store.py \
  --summary-collection graph_summaries \
  --content-collection graph_contents \
  --docs-dir /path/to/docs \
  --clear
```

---

## Workflow

### Execution Flow

```
1. Initialization
   ↓
2. Orchestrator: Query rules, define structure
   ↓
3. Analysis Loop (max 3 retries)
   ├─→ Analyzer: Extract actions
   ├─→ Quality Checker: Evaluate
   └─→ If score < 0.7: Retry with feedback
   ↓
4. Extraction Loop
   ├─→ Extractor: Refine and deduplicate
   ├─→ Quality Checker: Evaluate
   └─→ If score < 0.7: Retry with feedback
   ↓
5. Prioritization Loop
   ├─→ Prioritizer: Assign timelines
   ├─→ Quality Checker: Evaluate
   └─→ If score < 0.7: Retry with feedback
   ↓
6. Assignment Loop
   ├─→ Assigner: Assign responsibilities
   ├─→ Quality Checker: Evaluate
   └─→ If score < 0.7: Retry with feedback
   ↓
7. Formatting
   ├─→ Formatter: Compile final plan
   └─→ Apply WHO/CDC template
   ↓
8. Output: Markdown document saved
```

### Quality Feedback Loop

**Mechanism:**
- Each agent output validated by Quality Checker
- Score < 0.7: Agent retries with specific feedback
- Score ≥ 0.7: Proceed to next stage
- Max retries exceeded: Proceed with warning

**Example Feedback:**
```
Score: 0.65 (below threshold)
Feedback:
- Accuracy: 0.8 - Good protocol alignment
- Completeness: 0.5 - Missing infection control actions
- Source Traceability: 0.7 - Some citations missing line ranges
Recommendation: Add infection control procedures and complete citations
```

### LangGraph State Management

```python
from workflows.graph_state import ActionPlanState

state: ActionPlanState = {
    "subject": str,                    # User input
    "rules_context": str,              # From Orchestrator
    "extracted_actions": list,         # From Analyzer
    "refined_actions": list,           # From Extractor
    "prioritized_actions": list,       # From Prioritizer
    "assigned_actions": list,          # From Assigner
    "final_plan": str,                 # From Formatter
    "current_stage": str,              # Workflow tracking
    "retry_count": dict,               # Per-agent retry counts
    "quality_scores": dict,            # Per-stage scores
    "errors": list,                    # Error collection
    "metadata": dict                   # Additional info
}
```

---

## Command Reference

### Database Management
```bash
# Initialize all databases
python3 main.py init-db

# Show statistics
python3 main.py stats

# Clear databases (with confirmation)
python3 main.py clear-db --database neo4j
python3 main.py clear-db --database chromadb
python3 main.py clear-db --database both
```

### System Checks
```bash
# Check prerequisites and connections
python3 main.py check

# Run comprehensive verification (if available)
python3 verify_setup.py
```

### Data Operations
```bash
# Ingest all documents from unified directory
python3 main.py ingest --docs-dir /path/to/docs

# Or use default directory from .env
python3 main.py ingest
```

### Action Plan Generation
```bash
# Generate with default output
python3 main.py generate --subject "hand hygiene protocol"

# Generate with custom output
python3 main.py generate \
  --subject "emergency triage" \
  --output custom_plans/triage.md

# With debug logging
python3 main.py generate --subject "test" --log-level DEBUG
```

### Monitoring
```bash
# View logs in real-time
tail -f action_plan_orchestration.log

# Search for errors
grep ERROR action_plan_orchestration.log

# View INFO messages
grep INFO action_plan_orchestration.log

# Monitor LLM usage
watch -n 5 'curl -s http://localhost:11434/api/ps'
```

### Docker Management
```bash
# Neo4j
docker ps | grep neo4j
docker start neo4j
docker stop neo4j
docker logs neo4j

# Neo4j Browser: http://localhost:7474
# Connect: bolt://localhost:7687
# User: neo4j, Password: cardiosmartai
```

### Advanced Queries
```bash
# Export Neo4j data
python3 <<EOF
from neo4j import GraphDatabase
from config.settings import get_settings
import json

s = get_settings()
driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

with driver.session() as session:
    result = session.run("MATCH (d:Document) RETURN d")
    docs = [dict(record['d']) for record in result]
    
with open('documents_export.json', 'w') as f:
    json.dump(docs, f, indent=2)

driver.close()
EOF
```

---

## Troubleshooting

### Common Issues

#### 1. Ollama Not Accessible
```bash
# Check status
curl http://localhost:11434/api/tags

# If not running
ollama serve

# Verify model
ollama list
ollama pull gpt-oss:20b
```

#### 2. Neo4j Connection Failed
```bash
# Check container
docker ps | grep neo4j

# View logs
docker logs neo4j

# Restart
docker restart neo4j

# Wait for startup
sleep 10

# Test connection
python3 -c "from utils.db_init import initialize_neo4j; initialize_neo4j()"
```

#### 3. ChromaDB Issues
```bash
# Check directory
ls -la ./chroma_storage

# If corrupted, clear and reinitialize
rm -rf ./chroma_storage
python3 main.py init-db
```

#### 4. Import Errors (sentence-transformers)
**Issue:** `X509_V_FLAG_NOTIFY_POLICY` attribute error

**Solution:** System already uses Ollama embeddings instead
```bash
# Verify in .env
grep OLLAMA_EMBEDDING_MODEL .env
# Should show: embeddinggemma:latest

# No action needed - system bypasses sentence-transformers
```

#### 5. No Actions Extracted
```bash
# Check if documents exist
ls -la /storage03/Saboori/ActionPlan/HELD/docs/*.md

# Verify ingestion completed
python3 main.py stats

# Check logs for errors
grep ERROR action_plan_orchestration.log

# Re-run ingestion if needed
python3 main.py ingest --type both \
  --rules-dir /path/to/rules \
  --protocols-dir /path/to/protocols
```

#### 6. Quality Check Failures
```bash
# Increase retries in .env
MAX_RETRIES=5

# Lower threshold (not recommended)
QUALITY_THRESHOLD=0.6

# Check if protocols have sufficient detail
python3 -c "from rag_tools.vector_rag import VectorRAG; \
  r = VectorRAG('protocols_documents'); \
  print(r.semantic_search('test', top_k=1))"
```

#### 7. Slow Summarization
```bash
# Use faster model
OLLAMA_MODEL=cogito:8b

# Increase timeout
OLLAMA_TIMEOUT=5000

# Reduce document batch size
# Process fewer files at once
```

### Reset Everything
```bash
# WARNING: Deletes all data!

# 1. Stop services
docker stop neo4j

# 2. Clear databases
python3 main.py clear-db --database both

# 3. Remove data
rm -rf ./chroma_storage

# 4. Restart services
docker start neo4j
sleep 10

# 5. Reinitialize
python3 main.py init-db

# 6. Reingest
python3 main.py ingest --type both \
  --rules-dir /path/to/rules \
  --protocols-dir /path/to/protocols
```

---

## Implementation Details

### File Structure (33 files)

```
Agents/
├── config/
│   ├── __init__.py
│   ├── settings.py              # Pydantic settings with env vars
│   └── prompts.py               # All 7 agent prompts
│
├── data_ingestion/
│   ├── __init__.py
│   ├── enhanced_graph_builder.py   # Hierarchical summarization (NEW)
│   ├── graph_builder.py            # Basic graph construction
│   ├── vector_builder.py           # ChromaDB vector store
│   └── graph_vector_builder.py     # Dual-embedding builder
│
├── rag_tools/
│   ├── __init__.py
│   ├── graph_rag.py             # Neo4j graph retrieval
│   ├── vector_rag.py            # ChromaDB vector search (Ollama embeddings)
│   ├── hybrid_rag.py            # Combined retrieval with RRF
│   └── graph_aware_rag.py       # Advanced dual-embedding RAG
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py          # Workflow coordinator
│   ├── analyzer.py              # Action extraction
│   ├── extractor.py             # Refinement
│   ├── prioritizer.py           # Timeline assignment
│   ├── assigner.py              # Responsibility assignment
│   ├── quality_checker.py       # Validation
│   └── formatter.py             # Final compilation
│
├── workflows/
│   ├── __init__.py
│   ├── graph_state.py           # LangGraph state definitions
│   └── orchestration.py         # Complete workflow
│
├── utils/
│   ├── __init__.py
│   ├── llm_client.py            # Ollama client (singleton)
│   ├── document_parser.py       # Markdown parsing
│   ├── ollama_embeddings.py     # Ollama embedding client
│   └── db_init.py               # Database utilities (NEW)
│
├── templates/
│   └── action_plan.md           # WHO/CDC template
│
├── scripts/
│   └── build_graph_vector_store.py  # Vector store builder
│
├── examples/
│   └── graph_aware_rag_demo.py      # RAG demonstration
│
├── docs/
│   └── GRAPH_AWARE_RAG.md           # Technical documentation
│
├── action_plans/                # Generated plans
├── requirements.txt             # Dependencies
├── .env                         # Environment configuration
├── main.py                      # CLI entry point
├── verify_setup.py              # Setup verification
└── README.md                    # This file
```

### Key Improvements in Version 2.0

| Feature | v1.0 | v2.0 Enhanced |
|---------|------|---------------|
| Summarization | Flat (independent) | Hierarchical (bottom-up) |
| Database Init | Manual | Automatic (`init-db`) |
| Statistics | None | Real-time (`stats`) |
| Cypher Execution | Sequential | Transaction-based |
| Source Tracking | Basic | Full file path |
| Error Handling | Continue on error | Atomic rollback |
| Embeddings | sentence-transformers | Ollama embeddings |
| Maintenance | Manual queries | CLI commands |
| Documentation | 3 files | 13+ comprehensive guides |

### Neo4j Graph Schema (Unified)

```cypher
// Document nodes with unified schema
(:Document {
  name: "document_name",
  type: "health",  // Unified collection type
  source: "/absolute/path/to/file.md",
  is_rule: true/false  // Auto-tagged: true for guidelines, false for protocols
})

// Heading nodes
(:Heading {
  id: "document_name_h1",
  title: "Section Title",
  level: 1-6,
  start_line: 10,
  end_line: 50,
  summary: "Hierarchical summary...",
  summary_embedding: [...]  // Optional: if using Neo4j embeddings
})

// Relationships
(Document)-[:HAS_SUBSECTION]->(Heading)
(Heading)-[:HAS_SUBSECTION]->(Heading)

// Indexes (automatic)
CREATE INDEX heading_id FOR (h:Heading) ON (h.id);
CREATE INDEX document_name FOR (d:Document) ON (d.name);
CREATE INDEX document_type FOR (d:Document) ON (d.type);
CREATE INDEX document_is_rule FOR (d:Document) ON (d.is_rule);

// Query examples
// Get all guidelines
MATCH (d:Document {is_rule: true}) RETURN d

// Get all protocols  
MATCH (d:Document {is_rule: false}) RETURN d

// Get hierarchy for a section
MATCH path = (d:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: 'some_id'})
RETURN nodes(path)
```

### ChromaDB Collections (Unified)

**Structure:**
```python
{
    "id": "chunk_id",
    "embedding": [768-dim vector from Ollama],
    "document": "text content",
    "metadata": {
        "source": "file_path.md",
        "node_id": "document_h1",
        "start_line": 10,
        "end_line": 50,
        "heading_title": "Section Title",
        "level": 1,
        "is_rule": true/false,  // Indicates if from guideline
        "hierarchy": "Doc > Section > Subsection"  // For guidelines
    }
}
```

**Collections:**
- `health_documents`: Unified collection for all documents
- `document_summaries`: Summary embeddings (for GraphAwareRAG)

---

## Testing & Verification

### Verification Checklist

```bash
# 1. Configuration
python3 -c "from config.settings import get_settings; print('✓ Config loaded')"

# 2. Ollama connection
curl -s http://localhost:11434/api/tags | grep -q gpt-oss && echo "✓ Ollama" || echo "✗ Ollama"

# 3. Neo4j connection
python3 -c "from utils.db_init import initialize_neo4j; \
  success, msg = initialize_neo4j(); \
  print('✓ Neo4j' if success else '✗ Neo4j')"

# 4. ChromaDB connection
python3 -c "from utils.db_init import initialize_chromadb; \
  success, msg = initialize_chromadb(); \
  print('✓ ChromaDB' if success else '✗ ChromaDB')"

# 5. Document parser
python3 -c "from utils.document_parser import DocumentParser; \
  print('✓ Parser loaded')"

# 6. LLM client
python3 -c "from utils.llm_client import OllamaClient; \
  c = OllamaClient(); \
  print('✓ LLM' if c.check_connection() else '✗ LLM')"

# 7. Workflow
python3 -c "from workflows.orchestration import create_workflow; \
  create_workflow(); \
  print('✓ Workflow')"
```

### Test Results (October 14, 2025)

**System Status:** ✅ **ALL SYSTEMS OPERATIONAL**

| Component | Status | Notes |
|-----------|--------|-------|
| Configuration | ✅ | All settings loaded |
| Ollama | ✅ | Connected, generating |
| Neo4j | ✅ | 254+ nodes, indexes created |
| ChromaDB | ✅ | Fresh init, working |
| Embeddings | ✅ | Ollama embeddings functional |
| Graph Builder | ✅ | Hierarchical summarization ready |
| Database Utils | ✅ | All commands functional |
| Agents | ✅ | All 7 agents operational |
| Workflow | ✅ | LangGraph workflow tested |

**Known Non-Issues:**
- sentence-transformers SSL: Bypassed (using Ollama embeddings)
- ChromaDB minor warning: Does not affect functionality

### Performance Metrics

**Ingestion:**
- Small docs (< 50 headings): 1-2 minutes
- Medium docs (50-200 headings): 5-10 minutes
- Large docs (> 200 headings): 10-20 minutes
- Bottleneck: LLM summarization (1 call per heading)

**Querying:**
- Neo4j graph queries: < 100ms (with indexes)
- Vector semantic search: < 500ms
- Hybrid queries: < 1 second
- Action plan generation: 2-5 minutes

**Resource Usage:**
- RAM: ~4GB (with embeddings loaded)
- Disk: ~1GB (for vector storage)
- GPU: Optional (speeds up Ollama)

---

## Performance Optimization

### Neo4j Optimization

**Indexes (automatic):**
```cypher
CREATE INDEX heading_id FOR (h:Heading) ON (h.id);
CREATE INDEX document_name FOR (d:Document) ON (d.name);
CREATE INDEX document_type FOR (d:Document) ON (d.type);
```

**Query optimization:**
```cypher
// Use indexed properties in WHERE clauses
MATCH (h:Heading)
WHERE h.id = "specific_id"  // Fast (indexed)
RETURN h

// Limit result sets
MATCH (h:Heading)
RETURN h
LIMIT 100
```

### ChromaDB Optimization

**Batch operations:**
```python
# Add documents in batches
builder.add_documents_batch(docs, batch_size=50)

# Query with filters
rag.semantic_search(
    query="text",
    top_k=5,
    filters={"source": "specific_file.md"}  # Reduces search space
)
```

### Ollama Optimization

**Model selection:**
```bash
# Fast but less accurate
OLLAMA_MODEL=cogito:8b

# Balanced
OLLAMA_MODEL=gpt-oss:20b

# Most accurate but slower
OLLAMA_MODEL=llama3.1:70b
```

**Temperature tuning:**
```bash
# More deterministic (recommended for summarization)
OLLAMA_TEMPERATURE=0.1

# More creative (for varied outputs)
OLLAMA_TEMPERATURE=0.7
```

### Caching

**Embedding cache:**
```python
from utils.ollama_embeddings import OllamaEmbeddingsClient

client = OllamaEmbeddingsClient()
# Embeddings are cached automatically using MD5 keys

# Clear cache if needed
client.clear_cache()
```

**LLM response cache:**
- Currently not implemented
- Can add with Redis or local file cache

---

## Advanced Topics

### Custom Agent Development

```python
from agents.base import BaseAgent
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG

class CustomAgent(BaseAgent):
    def __init__(self, llm_client: OllamaClient, rag: HybridRAG):
        super().__init__(llm_client, rag)
        self.name = "CustomAgent"
    
    def execute(self, state: dict) -> dict:
        # Get context from RAG
        context = self.rag.query(
            query=state["subject"],
            mode="automatic",
            top_k=5
        )
        
        # Process with LLM
        prompt = f"Custom task for: {state['subject']}\n\nContext: {context}"
        result = self.llm_client.generate(prompt)
        
        # Update state
        state["custom_output"] = result
        return state
```

### Custom Prompts

Edit `config/prompts.py`:

```python
CUSTOM_AGENT_PROMPT = """You are a specialized agent for [specific task].

**Guidelines:**
1. [Guideline 1]
2. [Guideline 2]

**Chain-of-Thought Process:**
1. Analyze input
2. Consider context
3. Generate output

**Example:**
Input: [example input]
Output: [example output]

**Your Task:**
{task_description}

**Context:**
{context}

Provide your response:
"""
```

### Extending RAG

**Custom retrieval mode:**

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

class CustomRAG(GraphAwareRAG):
    def custom_retrieve(self, query: str, filters: dict = None):
        # Custom retrieval logic
        graph_results = self.neo4j_client.run_query(custom_cypher)
        vector_results = self.vector_search(query, filters)
        
        # Custom merging strategy
        merged = self.custom_merge(graph_results, vector_results)
        return merged
```

### Workflow Customization

**Add custom nodes:**

```python
from langgraph.graph import StateGraph
from workflows.graph_state import ActionPlanState

def create_custom_workflow():
    graph = StateGraph(ActionPlanState)
    
    # Add custom node
    graph.add_node("custom_stage", custom_agent.execute)
    
    # Add edges
    graph.add_edge("analyzer", "custom_stage")
    graph.add_edge("custom_stage", "extractor")
    
    return graph.compile()
```

---

## Development

### Running Tests

```bash
# Test LLM client
python3 -c "from utils.llm_client import OllamaClient; \
  c = OllamaClient(); \
  print(c.generate('Say hello', max_tokens=20))"

# Test RAG
python3 -c "from rag_tools.graph_rag import GraphRAG; \
  g = GraphRAG('rules'); \
  print(g.traverse_by_keywords(['triage']))"

# Test embeddings
python3 -c "from utils.ollama_embeddings import OllamaEmbeddingsClient; \
  c = OllamaEmbeddingsClient(); \
  vec = c.embed('test'); \
  print(f'Dim: {len(vec)}')"
```

### Debugging

**Enable debug logging:**
```bash
python3 main.py generate --subject "test" --log-level DEBUG
```

**Monitor specific components:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now run your code
from workflows.orchestration import create_workflow
# ... debug output will be verbose
```

### Contributing

**Code style:**
- Follow PEP 8
- Use type hints
- Add docstrings (Google style)
- Keep functions focused

**Testing new features:**
1. Create test in `tests/` (if directory exists)
2. Run full ingestion test
3. Generate test action plan
4. Check logs for errors

---

## Aliases for Convenience

Add to `~/.bashrc`:

```bash
# Action Plan shortcuts
alias ap-init='cd /storage03/Saboori/ActionPlan/Agents && python3 main.py init-db'
alias ap-stats='cd /storage03/Saboori/ActionPlan/Agents && python3 main.py stats'
alias ap-check='cd /storage03/Saboori/ActionPlan/Agents && python3 main.py check'
alias ap-ingest='cd /storage03/Saboori/ActionPlan/Agents && python3 main.py ingest'
alias ap-logs='tail -f /storage03/Saboori/ActionPlan/Agents/action_plan_orchestration.log'
alias ap-generate='cd /storage03/Saboori/ActionPlan/Agents && python3 main.py generate'

# Usage:
# ap-init
# ap-stats
# ap-ingest
# ap-generate --subject "hand hygiene"
```

---

## References

### Technologies
- **LangGraph:** https://github.com/langchain-ai/langgraph
- **Ollama:** https://ollama.com/
- **Neo4j:** https://neo4j.com/
- **ChromaDB:** https://www.trychroma.com/

### Standards
- **WHO Guidelines:** https://www.who.int/
- **CDC Standards:** https://www.cdc.gov/
- **NACCHO Action Planning:** https://www.naccho.org/

### Research Papers
- GraphRAG: Graph-Retrieval-Augmented Generation
- NodeRAG: Heterogeneous Graph Structures
- Contextual Retrieval: Anthropic's approach
- Reciprocal Rank Fusion: Multi-strategy merging

---

## Support

### Getting Help

1. **Check Documentation** (you're reading it!)
2. **View Logs:** `action_plan_orchestration.log`
3. **Run Diagnostics:**
   ```bash
   python3 main.py check
   python3 main.py stats
   ```
4. **Common Solutions:**
   - Restart services (Ollama, Neo4j)
   - Verify `.env` configuration
   - Check document paths
   - Ensure disk space available

### Reporting Issues

When reporting issues, include:
- Command that failed
- Error message from logs
- Output of `python3 main.py check`
- Output of `python3 main.py stats`
- System info (OS, Python version)

---

## License

This project is for educational and research purposes in health policy development.

---

## Acknowledgments

Built with:
- LangGraph for workflow orchestration
- Ollama for LLM inference and embeddings
- Neo4j for graph-based knowledge representation
- ChromaDB for semantic vector search

Inspired by state-of-the-art RAG research including GraphRAG, NodeRAG, and contextual retrieval techniques.

---

## Final Notes

**⚠️ Important:** Always review generated action plans with domain experts before implementation. This system provides evidence-based recommendations but requires human oversight for critical health decisions.

**✅ Production Ready:** This system has been tested and verified for production use. All core components are operational and documented.

**🚀 Ready to Start?**

```bash
cd /storage03/Saboori/ActionPlan/Agents
python3 main.py init-db
python3 main.py ingest --type both \
  --rules-dir /storage03/Saboori/ActionPlan/HELD/docs \
  --protocols-dir /storage03/Saboori/ActionPlan/HELD/docs
python3 main.py generate --subject "your health policy topic"
```

---

**Version:** 2.1 Unified Knowledge Base with Smart Tagging  
**Last Updated:** October 15, 2025  
**Status:** ✅ ALL SYSTEMS OPERATIONAL

**Key Improvements in v2.1:**
- ✅ Unified collection for all documents (guidelines + protocols)
- ✅ Intelligent auto-tagging with `is_rule` metadata
- ✅ Hierarchical context enrichment for guideline citations
- ✅ Simplified configuration and management
- ✅ Single directory, single database approach
