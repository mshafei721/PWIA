#!/bin/bash

# PWIA Project Setup Script
# This script sets up the Python virtual environment and installs dependencies

echo "🚀 Setting up PWIA project environment..."

# Check if Python 3.10+ is available
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version $python_version detected"

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp config/.env.example .env
    echo "⚠️  Please update .env with your API keys"
else
    echo "✅ .env file already exists"
fi

# Set up pre-commit hooks (if available)
if command -v pre-commit &> /dev/null; then
    echo "🔒 Setting up pre-commit hooks..."
    pre-commit install
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run the backend server:"
echo "  uvicorn backend.main:app --reload"
echo ""
echo "To run the agent:"
echo "  python -m agent.main --help"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "⚠️  Don't forget to update .env with your API keys!"