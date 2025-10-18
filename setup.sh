#!/bin/bash
# Setup script for LLM Agent Orchestration System

set -e

echo "=========================================="
echo "LLM Agent Orchestration - Setup"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo -e "  ${GREEN}✓${NC} Python 3.9+ detected"
else
    echo -e "  ${RED}✗${NC} Python 3.9+ required"
    exit 1
fi

# Check if in correct directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}✗${NC} Please run this script from the Agents directory"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} Python dependencies installed"

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${YELLOW}!${NC} Please edit .env file to configure your settings"
    echo "  Required: Set RULES_DOCS_DIR and PROTOCOLS_DOCS_DIR"
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p action_plans
mkdir -p logs
echo -e "${GREEN}✓${NC} Directories created"

# Check Ollama
echo ""
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Ollama is running"
    
    # Check for llama3.1 model
    if curl -s http://localhost:11434/api/tags | grep -q "llama3.1"; then
        echo -e "${GREEN}✓${NC} llama3.1 model found"
    else
        echo -e "${YELLOW}!${NC} llama3.1 model not found"
        echo "  Run: ollama pull llama3.1"
    fi
else
    echo -e "${RED}✗${NC} Ollama is not running"
    echo "  Install: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Start: ollama serve"
fi

# Check Neo4j
echo ""
echo "Checking Neo4j..."
if docker ps | grep -q neo4j; then
    echo -e "${GREEN}✓${NC} Neo4j container is running"
elif docker ps -a | grep -q neo4j; then
    echo -e "${YELLOW}!${NC} Neo4j container exists but is not running"
    echo "  Start: docker start neo4j"
else
    echo -e "${YELLOW}!${NC} Neo4j container not found"
    echo "  Run: docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest"
fi

# Check ChromaDB
echo ""
echo "Checking ChromaDB..."
if [ -d "./chroma_storage" ]; then
    echo -e "${GREEN}✓${NC} ChromaDB storage directory exists"
else
    echo -e "${YELLOW}!${NC} ChromaDB storage directory not found"
    echo "  It will be created automatically on first use"
fi

# Summary
echo ""
echo "=========================================="
echo "Setup Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file:"
echo "   nano .env"
echo ""
echo "2. Set your document directories:"
echo "   RULES_DOCS_DIR=/path/to/rules/docs"
echo "   PROTOCOLS_DOCS_DIR=/path/to/protocols/docs"
echo ""
echo "3. Run ingestion:"
echo "   python main.py ingest --type both"
echo ""
echo "4. Generate your first action plan:"
echo "   python main.py generate --subject \"your subject here\""
echo ""
echo "For quick start guide: cat QUICKSTART.md"
echo "For full documentation: cat README.md"
echo ""
echo -e "${GREEN}Setup complete!${NC}"

