#!/usr/bin/env bash
# ============================================================
# Publish this folder as a new public repo on github.com/Milad-Shabani
# Requires: git, and GitHub CLI (gh) installed + logged in (gh auth login)
# ============================================================
set -euo pipefail

REPO_NAME="battery-crm-sop-planning-engine"
REPO_DESC="CRM-integrated S&OP planning engine for a battery manufacturer: Dynamics-365-style CRM pipeline blended into demand forecasting, capacity- and labor-constrained production planning (LP), MRP, and CRM funnel analytics, published to a formatted Excel workbook + live HTML dashboard."

# --- adjust this to wherever you unzipped/cloned the project locally
cd "$HOME/Desktop/battery-crm-sop-planning-engine"

# --- set your git identity (safe to run every time)
git config --global user.name "Milad Shabani"
git config --global user.email "MILAD.SHABANI6515@GMAIL.COM"

# --- init only if not already a repo
if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

# --- remove any leftover remote from a previous attempt
git remote remove origin 2>/dev/null || true

git add .
git commit -m "Initial commit: Battery CRM + S&OP Planning Engine" || echo "(nothing new to commit)"
git branch -M main

gh repo create "$REPO_NAME" --public --source=. --remote=origin --push --description "$REPO_DESC"

gh repo edit "Milad-Shabani/$REPO_NAME" \
    --add-topic crm \
    --add-topic dynamics-365 \
    --add-topic demand-forecasting \
    --add-topic production-planning \
    --add-topic linear-programming \
    --add-topic excel \
    --add-topic python

echo
echo "Done. Repo should now be live at:"
echo "https://github.com/Milad-Shabani/$REPO_NAME"
