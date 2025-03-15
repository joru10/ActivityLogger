#!/bin/bash
# Script to remove sensitive data from Git history while keeping the files locally

echo "This script will remove sensitive data from Git history."
echo "Your files will remain on your local machine, but will be removed from Git tracking."
echo "This is a destructive operation for Git history. Make sure you have a backup if needed."
echo ""
read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Operation cancelled."
    exit 1
fi

# Add the .gitignore file
git add .gitignore
git commit -m "Add .gitignore to prevent sensitive data leakage"

# Remove sensitive files from Git tracking but keep them locally
echo "Removing database files from Git tracking..."
git rm --cached backend/activity_logs.db
git rm --cached backend/activity_logs.db.backup
git rm --cached backend/**/*.db
git rm --cached backend/**/*.sqlite
git rm --cached backend/**/*.sqlite3

echo "Removing storage directories from Git tracking..."
git rm -r --cached storage/ 2>/dev/null || true
git rm -r --cached backend/storage/ 2>/dev/null || true

echo "Removing reports with personal information from Git tracking..."
git rm -r --cached reports/ 2>/dev/null || true
git rm -r --cached backend/reports/ 2>/dev/null || true

echo "Removing backup files from Git tracking..."
git rm -r --cached backend/backups/ 2>/dev/null || true
git rm --cached "**/*.backup" 2>/dev/null || true

echo "Removing Python cache files from Git tracking..."
git rm -r --cached __pycache__/ 2>/dev/null || true
git rm -r --cached backend/__pycache__/ 2>/dev/null || true
git rm -r --cached "**/__pycache__/" 2>/dev/null || true
git rm -r --cached .pytest_cache/ 2>/dev/null || true
git rm --cached "**/*.pyc" 2>/dev/null || true

echo "Removing OS specific files from Git tracking..."
git rm --cached .DS_Store 2>/dev/null || true
git rm --cached "**/.DS_Store" 2>/dev/null || true

echo "Removing log files from Git tracking..."
git rm -r --cached logs/ 2>/dev/null || true
git rm -r --cached backend/logs/ 2>/dev/null || true
git rm --cached "**/*.log" 2>/dev/null || true

echo "Removing node_modules from Git tracking..."
git rm -r --cached node_modules/ 2>/dev/null || true
git rm -r --cached backend/node_modules/ 2>/dev/null || true

# Commit the changes
git commit -m "Remove sensitive files from Git tracking while keeping them locally"

echo ""
echo "Sensitive files have been removed from Git tracking but kept locally."
echo "To push these changes to GitHub, use: git push origin main --force"
echo "WARNING: This will rewrite history on GitHub. Make sure collaborators are aware."
