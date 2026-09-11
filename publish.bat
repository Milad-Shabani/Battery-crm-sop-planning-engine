@echo off
REM ============================================================
REM Publish this folder as a new public repo on github.com/Milad-Shabani
REM Requires: git, and GitHub CLI (gh) installed + logged in (gh auth login)
REM ============================================================

set REPO_NAME=battery-crm-sop-planning-engine
set "REPO_DESC=CRM-integrated S&OP planning engine for a battery manufacturer: Dynamics-365-style CRM pipeline blended into demand forecasting, capacity- and labor-constrained production planning (LP), MRP, and CRM funnel analytics, published to a formatted Excel workbook + live HTML dashboard."

REM --- adjust this to wherever you unzipped/cloned the project locally
cd /d "C:\Users\MILAD\Desktop\battery-crm-sop-planning-engine"

REM --- set your git identity (safe to run every time)
git config --global user.name "Milad Shabani"
git config --global user.email "MILAD.SHABANI6515@GMAIL.COM"

REM --- init only if not already a repo
if not exist ".git" (
    git init
    git branch -M main
)

REM --- remove any leftover remote from a previous attempt
git remote remove origin 2>nul

git add .
git commit -m "Initial commit: Battery CRM + S&OP Planning Engine"
git branch -M main

gh repo create %REPO_NAME% --public --source=. --remote=origin --push --description "%REPO_DESC%"

gh repo edit Milad-Shabani/%REPO_NAME% --add-topic crm --add-topic dynamics-365 --add-topic demand-forecasting --add-topic production-planning --add-topic linear-programming --add-topic excel --add-topic python

echo.
echo Done. Repo should now be live at:
echo https://github.com/Milad-Shabani/%REPO_NAME%
pause
