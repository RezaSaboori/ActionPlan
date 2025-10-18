#!/bin/bash
# Launcher script for Streamlit UI

echo "🏥 Health Policy Action Plan Generator - UI Launcher"
echo "=================================================="
echo ""

# Check if we're in the right directory
if [ ! -f "streamlit_app.py" ]; then
    echo "❌ Error: streamlit_app.py not found"
    echo "Please run this script from the Agents directory"
    exit 1
fi

# Check if Streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Error: Streamlit not found"
    echo "Installing Streamlit and dependencies..."
    pip install -r requirements.txt
fi

# Check system prerequisites
echo "🔍 Checking system prerequisites..."
echo ""

# Check Ollama
if command -v ollama &> /dev/null; then
    echo "✅ Ollama found"
else
    echo "⚠️  Ollama not found - please install Ollama"
fi

# Check Neo4j (Docker)
if docker ps | grep -q neo4j; then
    echo "✅ Neo4j running"
else
    echo "⚠️  Neo4j not running - start with: docker start neo4j"
fi

# Check Python dependencies
if python -c "import streamlit" 2>/dev/null; then
    echo "✅ Streamlit installed"
else
    echo "❌ Streamlit not installed"
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "=================================================="
echo "🚀 Starting Streamlit UI..."
echo "=================================================="
echo ""
echo "Access the UI at: http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

# Launch Streamlit
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address localhost \
    --server.headless true \
    --browser.gatherUsageStats false

