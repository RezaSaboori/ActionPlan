## Streamlit UI for Health Policy Action Plan Generator

A comprehensive, professional web interface for the multi-agent health policy action plan system.

### Features

#### 🏠 Overview Dashboard
- System health monitoring (Ollama, Neo4j, ChromaDB status)
- Database statistics and metrics
- Quick start guide and tips
- Visual charts for data distribution

#### 📊 Graph Explorer
- Interactive Neo4j graph visualization using streamlit-agraph
- Filter by document type (Guidelines/Protocols)
- Search nodes by title
- Click nodes to view detailed information
- Hierarchical path display for guidelines
- Zoom, pan, and layout controls

#### 📁 Document Management
- Multi-file markdown upload
- Auto-detection of document type (guideline vs protocol)
- Manual override for document tagging
- Live ingestion progress tracking
- Document list with search and filter
- View document details and graph relationships
- Delete documents with confirmation

#### ✨ Action Plan Generation
- Subject input with example suggestions
- **Live progress tracking** with step-by-step agent outputs:
  - Orchestrator: Topics and plan structure
  - Analyzer Phase 1 & 2: Context building and subject identification
  - Analyzer_D: Deep analysis with relevance scores
  - Extractor: Action extraction by subject
  - Quality Checker: Detailed scores and feedback
  - Prioritizer: Timeline and urgency assignment
  - Assigner: Responsibility matrix
  - Formatter: Final formatted plan
- Real-time quality scores visualization
- Retry indicators and error highlighting
- Download generated plans (Markdown)
- Copy to clipboard functionality

#### 📚 Plan History
- Browse all generated plans
- Search and filter by subject/filename
- Sort by date, name, or size
- View full plan with metadata
- Re-generate with same subject
- Delete plans with confirmation
- Export options (PDF, DOCX - expandable)

#### ⚙️ Settings
- View all configuration parameters
- Ollama, RAG, Workflow, Database settings
- .env file location display
- Settings documentation

### Installation

1. **Install dependencies:**
   ```bash
   cd /storage03/Saboori/ActionPlan/Agents
   pip install -r requirements.txt
   ```

2. **Verify backend setup:**
   ```bash
   python main.py check
   ```

3. **Initialize databases (if needed):**
   ```bash
   python main.py init-db
   ```

### Running the UI

#### Method 1: Direct Launch
```bash
streamlit run streamlit_app.py
```

#### Method 2: With Custom Port
```bash
streamlit run streamlit_app.py --server.port 8501
```

#### Method 3: Using Launcher Script
```bash
chmod +x launch_ui.sh
./launch_ui.sh
```

#### Method 4: Background Mode
```bash
nohup streamlit run streamlit_app.py > streamlit.log 2>&1 &
```

### Accessing the UI

Once running, open your browser and navigate to:
- Local: `http://localhost:8501`
- Network: `http://<your-server-ip>:8501`

### Usage Guide

#### First Time Setup

1. **Check System Status**
   - Click "🔄 Refresh Status" in sidebar
   - Ensure all systems are 🟢 connected
   - If not, check Ollama and Neo4j services

2. **Initialize Database**
   - Click "🔧 Init DB" in sidebar
   - Wait for confirmation

3. **Upload Documents**
   - Go to "📁 Documents" tab
   - Upload markdown files
   - Preview and adjust document types if needed
   - Click "🚀 Ingest Documents"
   - Monitor progress in real-time

4. **Generate Your First Plan**
   - Go to "✨ Generate Plan" tab
   - Enter a subject (e.g., "hand hygiene protocols")
   - Click "🚀 Generate Plan"
   - Watch the live progress as agents work
   - View quality scores for each stage
   - Download the final plan

#### Exploring the Graph

1. Go to "📊 Graph Explorer" tab
2. Select document type filter (All/Guidelines/Protocols)
3. Use search to find specific nodes
4. Click on nodes to view details in the sidebar
5. Explore relationships and hierarchies

#### Managing Plans

1. Go to "📚 Plan History" tab
2. Search for plans by subject or filename
3. Click "👁️ View Plan" to read the full content
4. Download, re-generate, or delete as needed

### Configuration

Settings are loaded from `.env` file. Key parameters:

```bash
# Ollama
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_TEMPERATURE=0.1

# RAG
TOP_K_RESULTS=5
CHUNK_SIZE=400

# Workflow
MAX_RETRIES=3
QUALITY_THRESHOLD=0.7
```

Edit `.env` and restart the UI to apply changes.

### Troubleshooting

#### UI Won't Start
```bash
# Check if port is in use
lsof -i :8501

# Use different port
streamlit run streamlit_app.py --server.port 8502
```

#### Connection Errors
- Ensure Ollama is running: `ollama list`
- Check Neo4j: `docker ps | grep neo4j`
- Verify ChromaDB: Check `chroma_storage` directory

#### Slow Performance
- Reduce `max_nodes` in Graph Explorer
- Limit `top_k` results in settings
- Use faster Ollama model (e.g., `cogito:8b`)

#### Generation Stuck
- Check logs: `tail -f action_plan_orchestration.log`
- Refresh the page and try again
- Verify database contains documents

### Features Highlights

✅ **Real-time Progress Tracking**
- Watch each agent work in real-time
- See intermediate outputs at each stage
- Quality scores with visual feedback
- Automatic retry indicators

✅ **Interactive Graph Visualization**
- Powered by streamlit-agraph
- Filter, search, and explore
- Node details on click
- Relationship traversal

✅ **Smart Document Management**
- Auto-tagging based on filename
- Live ingestion progress
- Hierarchical summarization tracking
- Vector embedding status

✅ **Professional UI/UX**
- Custom CSS styling
- Responsive design
- Health policy themed colors
- Intuitive navigation

### Architecture

```
streamlit_app.py              # Main application
├── ui/
│   ├── components/
│   │   ├── sidebar.py         # System status & controls
│   │   ├── database_stats.py  # Database dashboard
│   │   ├── graph_viz.py       # Graph visualization
│   │   ├── document_manager.py # Document upload/management
│   │   ├── plan_generator.py  # Plan generation with live progress
│   │   └── plan_viewer.py     # Plan history browser
│   ├── utils/
│   │   ├── state_manager.py   # Session state management
│   │   ├── workflow_tracker.py # Progress tracking
│   │   └── formatting.py      # UI formatting helpers
│   └── styles/
│       └── custom.css         # Custom styling
```

### Technology Stack

- **Streamlit**: Modern Python web framework
- **streamlit-agraph**: Graph visualization
- **Plotly**: Interactive charts
- **Pandas**: Data manipulation
- **Neo4j Python Driver**: Graph database queries
- **Threading**: Background workflow execution

### Best Practices

1. **System Status**: Always check system status before generating plans
2. **Document Quality**: Upload well-formatted markdown documents
3. **Subject Specificity**: Be specific with subjects for better results
4. **Quality Scores**: Review quality feedback if score < 0.7
5. **Graph Exploration**: Use graph explorer to understand document structure

### Advanced Features

#### Background Generation
Plans generate in background thread, allowing UI to update in real-time

#### Session State Management
Persistent state across interactions for smooth UX

#### Auto-refresh
Automatic progress updates during generation (2s intervals)

#### Custom Styling
Professional healthcare-themed design with custom CSS

### Support

For issues or questions:
1. Check `streamlit.log` for errors
2. Review backend logs: `action_plan_orchestration.log`
3. Verify system status in sidebar
4. Check database statistics

### Future Enhancements

- [ ] PDF export functionality
- [ ] DOCX export functionality  
- [ ] Plan comparison tool
- [ ] Advanced graph filtering
- [ ] Custom agent configuration
- [ ] Batch plan generation
- [ ] User authentication
- [ ] Plan versioning

### Version

**UI Version**: 1.0.0
**Backend Version**: 2.1
**Status**: Production Ready ✅

---

Built with ❤️ for health policy professionals

