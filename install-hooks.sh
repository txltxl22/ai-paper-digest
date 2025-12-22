#!/bin/bash
#
# Install git hooks for this repository
# This script configures git to use the hooks in the hooks/ directory

set -e

echo "Installing git hooks..."
echo "======================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Get the repository root
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# Check if hooks directory exists
if [ ! -d "hooks" ]; then
    echo "❌ Error: hooks/ directory not found"
    exit 1
fi

# Make sure the pre-commit hook is executable
if [ -f "hooks/pre-commit" ]; then
    chmod +x hooks/pre-commit
    echo "✅ Made hooks/pre-commit executable"
else
    echo "❌ Error: hooks/pre-commit not found"
    exit 1
fi

# Configure git to use the hooks directory
git config core.hooksPath hooks

echo "✅ Git hooks installed successfully!"
echo ""
echo "The pre-commit hook will now run font-size checks on staged files and run tests before each commit."
echo "To uninstall, run: git config --unset core.hooksPath"
echo ""

