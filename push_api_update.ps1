# === CONFIGURATION ===
# Change to your project directory
Set-Location "C:\J3Q\API"

# === START SCRIPT ===
Write-Host "🚀 Starting Git push routine..." -ForegroundColor Cyan

# Show current branch and status
Write-Host "`n=== Checking Git status ===" -ForegroundColor Yellow
git status

# Check if there are any changes to commit
$changes = git status --porcelain
if (-not $changes) {
    Write-Host "`n✅ No changes detected. Nothing to commit or push." -ForegroundColor Green
    Pause
    exit
}

# Stage all changes (including deletions)
Write-Host "`n=== Staging changes ===" -ForegroundColor Yellow
git add -A

# Commit with a timestamped message
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "`n=== Committing changes ===" -ForegroundColor Yellow
git commit -m "Auto-update: $timestamp"

# Push to GitHub
Write-Host "`n=== Pushing to GitHub ===" -ForegroundColor Yellow
git push origin master

# Final confirmation
Write-Host "`n✅ Push complete!" -ForegroundColor Green
Pause
