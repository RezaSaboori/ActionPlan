# Migration Guide: v2.0 → v2.1 (Unified Knowledge Base)

## Overview

Version 2.1 introduces a **unified knowledge base** approach that merges rules and protocols into a single collection with intelligent auto-tagging and hierarchical context enrichment for guideline documents.

## What Changed

### 1. **Unified Document Storage**

**Before (v2.0):**
- Separate directories: `RULES_DOCS_DIR` and `PROTOCOLS_DOCS_DIR`
- Separate Neo4j collections: `rules` and `protocols`
- Separate ChromaDB collections: `rules_documents` and `protocols_documents`

**After (v2.1):**
- Single directory: `DOCS_DIR`
- Single Neo4j collection: `health` (configurable via `GRAPH_PREFIX`)
- Single ChromaDB collection: `health_documents` (configurable via `DOCUMENTS_COLLECTION`)
- Documents auto-tagged with `is_rule` metadata

### 2. **Smart Document Tagging**

Documents are automatically classified based on filename:
- Contains "guideline", "template", or "action_plan" → `is_rule: true` (Guideline)
- All others → `is_rule: false` (Protocol)

Customizable via `RULE_DOCUMENT_NAMES` in `.env`

### 3. **Hierarchical Context for Guidelines**

For guideline documents, the system now:
- Fetches full hierarchical path (Document > Section > Subsection)
- Includes hierarchy in agent prompts
- Enhances source traceability

### 4. **Simplified Configuration**

**Removed Settings:**
- `rules_docs_dir`
- `protocols_docs_dir`
- `rules_collection`
- `protocols_collection`
- `rules_graph_prefix`
- `protocols_graph_prefix`

**New Settings:**
- `docs_dir`: Unified document directory
- `documents_collection`: Unified ChromaDB collection
- `graph_prefix`: Unified Neo4j graph prefix
- `rule_document_names`: List of keywords for auto-tagging guidelines

### 5. **Updated Commands**

**Before:**
```bash
python3 main.py ingest --type both \
  --rules-dir /path/to/rules \
  --protocols-dir /path/to/protocols
```

**After:**
```bash
python3 main.py ingest --docs-dir /path/to/docs
# or simply:
python3 main.py ingest  # uses DOCS_DIR from .env
```

## Migration Steps

### Step 1: Update .env File

Replace old settings with new unified settings:

```bash
# OLD (remove these)
# RULES_DOCS_DIR=/path/to/rules
# PROTOCOLS_DOCS_DIR=/path/to/protocols
# RULES_COLLECTION=rules_documents
# PROTOCOLS_COLLECTION=protocols_documents
# RULES_GRAPH_PREFIX=rules
# PROTOCOLS_GRAPH_PREFIX=protocols

# NEW (add these)
DOCS_DIR=/storage03/Saboori/ActionPlan/Agents/held/docs
DOCUMENTS_COLLECTION=health_documents
GRAPH_PREFIX=health
RULE_DOCUMENT_NAMES=["guideline", "action_plan_template", "template"]
```

### Step 2: Consolidate Documents

Move all documents to a single directory:

```bash
# Create unified directory
mkdir -p /storage03/Saboori/ActionPlan/Agents/held/docs

# Copy all documents
cp /path/to/old/rules/*.md /storage03/Saboori/ActionPlan/Agents/held/docs/
cp /path/to/old/protocols/*.md /storage03/Saboori/ActionPlan/Agents/held/docs/

# Rename guideline documents to include "guideline" keyword if needed
mv emergency_plan_template.md emergency_plan_guideline.md
```

### Step 3: Clear Old Data

```bash
cd /storage03/Saboori/ActionPlan/Agents
python3 main.py clear-db --database both
```

**⚠️ Warning:** This deletes all existing data. Backup if needed!

### Step 4: Reinitialize and Ingest

```bash
# Initialize with new schema
python3 main.py init-db

# Ingest all documents with new unified approach
python3 main.py ingest

# Verify ingestion
python3 main.py stats
```

### Step 5: Test the System

```bash
# Generate a test action plan
python3 main.py generate --subject "test emergency response"

# Check logs for any issues
tail -f action_plan_orchestration.log
```

## Code Changes

### Agent Initialization

**Before:**
```python
orchestrator = OrchestratorAgent(llm_client, rules_hybrid_rag)
analyzer = AnalyzerAgent(llm_client, protocols_hybrid_rag)
```

**After:**
```python
orchestrator = OrchestratorAgent(llm_client, unified_hybrid_rag, unified_graph_rag)
analyzer = AnalyzerAgent(llm_client, unified_hybrid_rag, unified_graph_rag)
```

### Neo4j Queries

**Before:**
```cypher
MATCH (d:Document {type: 'rules'}) RETURN d
MATCH (d:Document {type: 'protocols'}) RETURN d
```

**After:**
```cypher
MATCH (d:Document {is_rule: true}) RETURN d   // Guidelines
MATCH (d:Document {is_rule: false}) RETURN d  // Protocols
MATCH (d:Document {type: 'health'}) RETURN d  // All documents
```

### Hierarchical Context

**New Feature:**
```python
# Get hierarchical path for a guideline section
hierarchy = graph_rag.get_section_hierarchy_string(node_id)
# Returns: "Document Name > Section > Subsection"
```

## Benefits of v2.1

### 1. **Simplified Management**
- One directory to manage
- One database to maintain
- Fewer configuration settings
- Easier deployment

### 2. **Better Traceability**
- Hierarchical paths for guideline citations
- Clear distinction between guidelines and protocols
- Automatic context enrichment

### 3. **Improved Search**
- Unified search across all documents
- Filter by `is_rule` when needed
- Seamless integration of guidelines and protocols

### 4. **Easier Maintenance**
- Single ingestion command
- Automatic document classification
- Consistent schema

## New Features

### 1. **Auto-Tagging**
Documents are automatically classified based on filename patterns. Customize via:

```python
# In .env
RULE_DOCUMENT_NAMES=["guideline", "template", "action_plan", "standard"]
```

### 2. **Hierarchical Enrichment**
For guideline documents, agents automatically receive:
- Full document hierarchy
- Parent section names
- Contextual path

Example in prompts:
```
Source: [Emergency Response Guideline > Triage Protocols > START Method]
Node: guideline_h15
Lines: 234-256
```

### 3. **Graph Hierarchy Queries**
New methods in GraphRAG:
- `get_rule_documents_with_hierarchy()`: Get all guidelines with structure
- `get_section_hierarchy_string(node_id)`: Get hierarchical path for a section

## Troubleshooting

### Issue: No documents found after migration

**Solution:**
```bash
# Check if documents exist
ls -la $DOCS_DIR/*.md

# Verify DOCS_DIR in .env
grep DOCS_DIR .env

# Re-run ingestion
python3 main.py ingest --docs-dir /path/to/docs
```

### Issue: Documents not tagged correctly

**Solution:**
```bash
# Update RULE_DOCUMENT_NAMES in .env
RULE_DOCUMENT_NAMES=["guideline", "template", "your_keyword"]

# Clear and re-ingest
python3 main.py clear-db --database neo4j
python3 main.py ingest
```

### Issue: Hierarchical paths not showing

**Solution:**
Ensure GraphRAG is passed to agents:
```python
# In workflows/orchestration.py
orchestrator = OrchestratorAgent(llm_client, unified_hybrid_rag, unified_graph_rag)
analyzer = AnalyzerAgent(llm_client, unified_hybrid_rag, unified_graph_rag)
```

### Issue: Old separate collections still exist

**Solution:**
```bash
# Clear ChromaDB completely
python3 main.py clear-db --database chromadb

# Reinitialize
python3 main.py init-db
python3 main.py ingest
```

## Backward Compatibility

### Breaking Changes
- Old ingestion commands with `--type`, `--rules-dir`, `--protocols-dir` no longer supported
- Separate collection queries will fail
- Agent initialization signatures changed

### Migration Path
Follow the migration steps above. No gradual migration supported - must fully migrate to v2.1.

## Testing Checklist

After migration, verify:

- [ ] Database initialization successful
- [ ] Documents ingested correctly
- [ ] Guidelines tagged with `is_rule: true`
- [ ] Protocols tagged with `is_rule: false`
- [ ] Hierarchical paths available for guidelines
- [ ] Action plan generation works
- [ ] Quality checker validates properly
- [ ] Source citations include hierarchy for guidelines

## Support

For issues or questions:
1. Check logs: `action_plan_orchestration.log`
2. Verify database stats: `python3 main.py stats`
3. Review this migration guide
4. Check updated README.md for v2.1 documentation

---

**Version:** 2.1  
**Migration Date:** October 15, 2025  
**Status:** Production Ready

