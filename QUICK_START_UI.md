# Quick Start Guide - Streamlit UI

## Installation (5 minutes)

### Step 1: Install UI Dependencies
```bash
cd /storage03/Saboori/ActionPlan/Agents
pip install -r requirements.txt
```

This will install all Streamlit UI components:
- streamlit
- streamlit-agraph (for graph visualization)
- plotly (for charts)
- pandas (for data handling)
- And other necessary packages

### Step 2: Verify Backend Setup
```bash
# Check system status
python main.py check

# Initialize databases if needed
python main.py init-db

# Verify statistics
python main.py stats
```

### Step 3: Launch the UI
```bash
# Option 1: Direct launch
streamlit run streamlit_app.py

# Option 2: Using the launcher script
chmod +x launch_ui.sh
./launch_ui.sh

# Option 3: Custom port
streamlit run streamlit_app.py --server.port 8502
```

### Step 4: Access the UI
Open your browser and navigate to:
- **Local**: http://localhost:8501
- **Network**: http://YOUR_SERVER_IP:8501

## First Time Usage (10 minutes)

### 1. Check System Status
- Look at the **sidebar** (left side)
- Click **"🔄 Refresh Status"**
- Ensure all systems show 🟢 (green)
  - Ollama: Should be running
  - Neo4j: Should be running (check `docker ps | grep neo4j`)
  - ChromaDB: Should be accessible

### 2. Upload Documents
- Go to **"📁 Documents"** tab
- Click **"Upload & Ingest"** sub-tab
- Upload your markdown files (guidelines and protocols)
- Preview files and adjust document types if needed
- Click **"🚀 Ingest Documents"**
- Wait for progress to complete (watch the logs!)

### 3. Explore the Graph
- Go to **"📊 Graph Explorer"** tab
- Select document type filter (All/Guidelines/Protocols)
- Click on nodes to see details
- Explore the hierarchical structure

### 4. Generate Your First Action Plan
- Go to **"✨ Generate Plan"** tab
- Enter a subject (example: "hand hygiene protocol implementation")
- Click **"🚀 Generate Plan"**
- **Watch the magic happen!**
  - See each agent work in real-time
  - View quality scores for each stage
  - See intermediate outputs
- Download your plan when complete

### 5. Browse Plan History
- Go to **"📚 Plan History"** tab
- View all generated plans
- Click to read full plans
- Download or re-generate as needed

## Interface Overview

### Sidebar (Always Visible)
```
🏥 Action Plan Generator
─────────────────────────
🔌 System Status
   🟢 Ollama
   🟢 Neo4j
   🟢 ChromaDB
   
📊 Quick Stats
   Nodes: 347
   Relationships: 346
   Collections: 2
   Documents: 1,250
   
⚡ Quick Actions
   [🔧 Init DB]  [📊 Stats]
   
⚙️ Configuration
   Model: gpt-oss:20b
   Temperature: 0.1
   Top K: 5
   Max Retries: 3
   Quality Threshold: 0.7
```

### Main Tabs
1. **🏠 Overview**: Dashboard with system health and statistics
2. **📊 Graph Explorer**: Interactive Neo4j graph visualization
3. **📁 Documents**: Upload and manage documents
4. **✨ Generate Plan**: Create action plans with live progress
5. **📚 Plan History**: Browse all generated plans
6. **⚙️ Settings**: View all configuration parameters

## Features at a Glance

### ✅ Live Progress Tracking
Watch your action plan being generated in real-time:
```
⏳ Workflow Progress
├─ ✅ Orchestrator (completed)
│   └─ Topics: hand hygiene, PPE, infection control
├─ ⏳ Analyzer (in progress)
│   └─ Building context from 12 document nodes...
├─ ⏺️ Analyzer_D (pending)
├─ ⏺️ Extractor (pending)
└─ ⏺️ Formatter (pending)
```

### ✅ Quality Scores
See detailed quality metrics for each stage:
- Accuracy: ████████░░ 0.85
- Completeness: ███████░░░ 0.75
- Ethics: █████████░ 0.90
- Traceability: ████████░░ 0.82
- Actionability: ███████░░░ 0.78
- **Overall: 0.82 ✅ PASS**

### ✅ Agent Outputs
View what each agent produced:
- **Orchestrator**: Plan structure and topics
- **Analyzer**: Context map and identified subjects
- **Analyzer_D**: Relevant document nodes
- **Extractor**: Extracted actions (table view)
- **Prioritizer**: Timeline visualization
- **Assigner**: Responsibility matrix
- **Formatter**: Final formatted plan

### ✅ Graph Visualization
Explore your knowledge graph:
- Filter by type (Guidelines/Protocols)
- Search nodes by title
- Click nodes for details
- See hierarchical relationships
- Color-coded visualization

### ✅ Document Management
Easy document handling:
- Drag-and-drop upload
- Auto-detection of document type
- Live ingestion progress
- Document list with search
- Delete with confirmation

## Troubleshooting

### UI Won't Start
```bash
# Check if port is in use
lsof -i :8501

# Kill existing process
kill -9 $(lsof -t -i:8501)

# Try different port
streamlit run streamlit_app.py --server.port 8502
```

### System Status Shows Red
```bash
# Ollama not running?
ollama list
ollama serve  # If not running

# Neo4j not running?
docker ps | grep neo4j
docker start neo4j

# ChromaDB issue?
# Check: ls -la chroma_storage/
```

### Generation Stuck
1. Check backend logs: `tail -f action_plan_orchestration.log`
2. Refresh the browser page
3. Try a simpler subject first
4. Verify documents are ingested

### No Documents Found
1. Upload documents via "📁 Documents" tab
2. Wait for ingestion to complete
3. Check "📊 Quick Stats" in sidebar for document count
4. Verify with: `python main.py stats`

## Tips for Best Results

1. **Be Specific**: Use specific subjects for better results
   - Good: "Hand hygiene protocol for emergency departments"
   - Bad: "Healthcare"

2. **Check Quality Scores**: Plans with < 0.7 may need review
   - Review the quality feedback
   - Try re-generating with more specific subject

3. **Explore the Graph**: Understand document structure before generating
   - See what documents you have
   - Check hierarchical relationships
   - Verify document types are correct

4. **Monitor Progress**: Watch the agents work
   - See what each agent produces
   - Understand the workflow
   - Identify bottlenecks

5. **Review Sources**: Check source citations in generated plans
   - Every action should have sources
   - Guidelines show hierarchical paths
   - Protocols show node IDs and line ranges

## Advanced Usage

### Background Mode
Run UI in background:
```bash
nohup streamlit run streamlit_app.py > streamlit.log 2>&1 &

# View logs
tail -f streamlit.log

# Stop
pkill -f streamlit
```

### Custom Configuration
Edit `.env` file for settings:
```bash
nano .env

# Key settings to adjust:
OLLAMA_MODEL=gpt-oss:20b  # Try cogito:8b for faster
OLLAMA_TEMPERATURE=0.1     # Lower = more deterministic
TOP_K_RESULTS=5            # More = more context
MAX_RETRIES=3              # More = more chances
QUALITY_THRESHOLD=0.7      # Lower = less strict
```

**Note**: Restart UI after editing `.env`

### Batch Processing
Generate multiple plans:
```python
# Create subjects.txt with one subject per line
subjects = [
    "hand hygiene protocols",
    "emergency triage procedures",
    "infection control measures"
]

# Use the UI to generate each one
# Plans are saved to action_plans/ directory
```

## Support & Documentation

- **UI Documentation**: `UI_README.md`
- **Implementation Details**: `STREAMLIT_UI_IMPLEMENTATION.md`
- **Backend Documentation**: `README.md`
- **Logs**: `streamlit.log` and `action_plan_orchestration.log`

## Keyboard Shortcuts

While in the UI:
- `Ctrl + R`: Refresh page
- `Ctrl + C`: (in terminal) Stop server
- `F11`: Full screen

## Next Steps

1. ✅ Start the UI
2. ✅ Check system status
3. ✅ Upload some documents
4. ✅ Generate your first plan
5. ✅ Explore the graph
6. ✅ Review plan history
7. 🎉 Start creating amazing health policy action plans!

---

**Questions?** Check the detailed documentation in `UI_README.md`

**Ready to start?** Run: `./launch_ui.sh`

🏥 Happy Planning! 🎯

