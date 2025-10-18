#!/bin/bash
# Restart Streamlit UI cleanly to avoid ChromaDB conflicts

echo "🔄 Restarting Streamlit UI..."
echo "================================"

# Kill any existing Streamlit processes
echo "1. Stopping existing Streamlit processes..."
pkill -f "streamlit run" 2>/dev/null
sleep 2

# Clear Python cache to ensure fresh imports
echo "2. Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# Optional: Clear ChromaDB lock files (if any)
if [ -d "./chroma_storage" ]; then
    echo "3. Checking ChromaDB storage..."
    # Remove any lock files that might exist
    find ./chroma_storage -name "*.lock" -delete 2>/dev/null
fi

echo "4. Starting Streamlit..."
echo "================================"
echo ""

# Start Streamlit
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address localhost \
    --server.headless true \
    --browser.gatherUsageStats false

