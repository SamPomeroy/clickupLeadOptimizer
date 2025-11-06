#!/bin/bash

# Setup script for clickupLeadOptimizer
# Run this from your ~/forge/aise/ directory

echo "🚀 Setting up clickupLeadOptimizer..."

# Create the project structure
mkdir -p clickupLeadOptimizer/{scripts,config,data,exports,logs}

cd clickupLeadOptimizer

echo "✅ Created project structure"

# Create a simple README
cat > README.md << 'EOF'
# ClickUp Lead Optimizer

Comprehensive lead enrichment and scoring system for multiple products (Compass, Upcurve, and future products).

## Quick Start
1. Edit config/config.json with your ClickUp API key
2. Run: `python scripts/pipeline.py --sample 10` for testing
3. Run: `python scripts/pipeline.py` for full processing
4. Review exports and import back to ClickUp after approval

Created for Banyan Labs sales optimization.
EOF

echo "📁 Project structure created at: $(pwd)"
echo ""
echo "Next steps:"
echo "1. Copy the Python scripts to clickupLeadOptimizer/scripts/"
echo "2. Edit config files with your API keys"
echo "3. Install requirements: pip install -r requirements.txt"
echo "4. Run test: python scripts/pipeline.py --sample 10"
