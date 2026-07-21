#!/bin/bash
# Run once from the root of your project: bash setup.sh

echo "Creating folder structure..."
mkdir -p backend/agents backend/tools backend/memory backend/api
mkdir -p frontend/app frontend/components

echo "Creating __init__.py files..."
touch backend/__init__.py
touch backend/agents/__init__.py
touch backend/tools/__init__.py
touch backend/memory/__init__.py
touch backend/api/__init__.py

echo "Creating .env from example..."
cp .env.example .env

echo "Setting up Python virtual environment..."
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Backend setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add your GROQ_API_KEY to .env"
echo "  2. Terminal 1: source venv/bin/activate && uvicorn backend.api.main:app --reload --port 8000"
echo "  3. Terminal 2: cd frontend && npm install && npm run dev"
echo "  4. Open http://localhost:3000"
