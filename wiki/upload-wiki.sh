#!/bin/bash
set -e

echo "=== TerraformManager Wiki Upload Script ==="
echo ""
echo "This script will upload all wiki pages to GitHub."
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed"
    exit 1
fi

# Create temporary directory for wiki clone
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Clone wiki repository (this will initialize it if empty)
echo "Cloning wiki repository..."
if ! git clone https://github.com/ilyafedotov-ops/TerraformManager.wiki.git "$TEMP_DIR" 2>/dev/null; then
    echo ""
    echo "========================================================================"
    echo "IMPORTANT: Wiki needs to be initialized first!"
    echo "========================================================================"
    echo ""
    echo "Please follow these steps:"
    echo ""
    echo "1. Visit: https://github.com/ilyafedotov-ops/TerraformManager/wiki"
    echo "2. Click 'Create the first page'"
    echo "3. Enter 'Home' as the title"
    echo "4. Paste the content from: wiki/Home.md"
    echo "5. Click 'Save Page'"
    echo "6. Run this script again"
    echo ""
    echo "========================================================================"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Copy all wiki files from the wiki directory (excluding README.md)
echo "Copying wiki files from $SCRIPT_DIR..."
for file in "$SCRIPT_DIR"/*.md; do
    filename=$(basename "$file")
    if [ "$filename" != "README.md" ]; then
        echo "  $filename"
        cp "$file" "$TEMP_DIR/"
    fi
done

# Configure git
cd "$TEMP_DIR"
git config user.name "$(git config --global user.name || echo 'Wiki Bot')"
git config user.email "$(git config --global user.email || echo 'wiki@local')"

# Add all files
echo "Adding files to git..."
git add *.md

# Check if there are changes
if git diff --staged --quiet; then
    echo "No changes detected. Wiki is already up to date."
else
    # Commit changes
    echo "Committing changes..."
    git commit -m "docs: update wiki documentation

- Add Home page with navigation and overview
- Add Getting Started guide with installation instructions
- Add Architecture overview with system design
- Add CLI Reference with all commands
- Add API Reference with complete endpoint documentation
- Add Configuration reference with environment variables
- Add Generators guide for Terraform code generation
- Add Authentication guide with JWT flow
- Add Development guide for contributors
- Add Deployment guide for production
- Add Troubleshooting guide for common issues
- Add Knowledge Base guide for RAG system"

    # Push to GitHub
    echo "Pushing to GitHub..."
    git push origin master

    echo ""
    echo "✅ Wiki pages uploaded successfully!"
    echo ""
    echo "View your wiki at: https://github.com/ilyafedotov-ops/TerraformManager/wiki"
fi

# Cleanup
cd -
rm -rf "$TEMP_DIR"
echo "Cleaned up temporary directory"

echo ""
echo "Done!"
