#!/bin/bash
echo "🚀 Setting up PDF Extraction Service..."
echo "========================================="

# Navigate to the service directory
cd pdf-service-runner

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.9+ first."
    exit 1
fi

echo "✅ Python found: $(python --version)"

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p outputs
mkdir -p pdfs
mkdir -p patterns

echo "✅ Directories created"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the service:"
echo "  cd pdf-service-runner"
echo "  python start_service.py"
echo ""
echo "Or use the batch script on Windows:"
echo "  double-click start_service.bat"
echo ""
echo "The service will be available at: http://localhost:8000"
echo "API docs will be available at: http://localhost:8000/docs"
