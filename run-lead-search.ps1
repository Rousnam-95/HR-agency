$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Starting HR staffing lead search (live web search + enrichment + Sheet delivery)..." -ForegroundColor Cyan
Write-Host "This can take a few minutes depending on how many companies it looks at." -ForegroundColor DarkGray
Write-Host ""

claude -p "Read docs/ROUTINE_PROMPT.md in this repo and carry out exactly the instructions under its '## PROMPT (verbatim)' heading. This is a one-shot live lead-generation search + enrichment + Sheet-delivery run for a B2B staffing sales pipeline. The .env file in this repo already has SHEET_WEBAPP_URL set -- use it as-is, don't overwrite it. Print a clear end-of-run summary." --permission-mode bypassPermissions

Write-Host ""
Write-Host "Done. Check the output/ folder for CSVs and your Google Sheet for new rows." -ForegroundColor Green
Read-Host "Press Enter to close this window"
