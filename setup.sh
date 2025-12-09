#!/bin/bash

# Azure AI Foundry KYC Orchestrator Setup Script
echo "🚀 Setting up Azure AI Foundry KYC Orchestrator..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3.8+ and try again."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed. Please install Node.js 16+ and try again."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Setup backend
echo "📦 Setting up backend..."
echo "Creating Python virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

# Setup frontend
echo "📦 Setting up frontend..."
cd frontend

echo "Installing Node.js dependencies..."
npm install

cd ..

echo "✅ Setup complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Configure your Azure credentials in .env file:"
echo "   - AZURE_OPENAI_ENDPOINT"
echo "   - AZURE_OPENAI_API_KEY"
echo "   - AZURE_OPENAI_DEPLOYMENT_NAME"
echo ""
echo "2. Start the backend server:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. In a new terminal, start the frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open http://localhost:3000 in your browser"
echo ""
echo "📋 Your .env file should look like:"
echo "AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/"
echo "AZURE_OPENAI_API_KEY=your-api-key-here"
echo "AZURE_OPENAI_DEPLOYMENT_NAME=gpt-35-turbo"
echo ""
echo "🎉 Happy coding!"