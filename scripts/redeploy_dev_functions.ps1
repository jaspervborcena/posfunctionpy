<#
Redeploy Dev Functions Script

Usage:
  - To redeploy all functions to the dev project (quick):
      .\redeploy_dev_functions.ps1

  - To redeploy and explicitly set TARGET_PROJECT and TARGET_DATASET env vars
    for every function (this redeploys each function using gcloud):
      .\redeploy_dev_functions.ps1 -SetTarget

Notes:
- This script assumes you have both `firebase` and `gcloud` CLIs installed and
  authenticated locally, and that `gcloud` has the necessary permissions.
- The script uses `firebase use dev` and `firebase deploy --only functions` for
  a fast bulk deploy. If you want env vars set on function containers, pass
  `-SetTarget` which will enumerate functions via `gcloud` and redeploy each
  function with `--set-env-vars` (this may take longer).
- Adjust runtime/source/region flags if your functions use a different runtime
  or source layout.
#>
param(
    [switch]$SetTarget,
    [string]$DevProject = 'jasperpos-dev',
    [string]$DevDataset = 'tovrika_pos_dev',
    [string]$Region = 'asia-east1'
)

Write-Host "Starting redeploy for project: $DevProject (region: $Region)"

# Ensure we use the dev firebase project
Write-Host "Switching firebase to project alias 'dev' (if present)"
firebase use dev
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: 'firebase use dev' returned non-zero exit code. Ensure your firebase project alias 'dev' exists." -ForegroundColor Yellow
}

# Quick bulk deploy using firebase (uploads source and deploys all functions)
Write-Host "Running: firebase deploy --only functions"
firebase deploy --only functions
if ($LASTEXITCODE -ne 0) {
    Write-Host "firebase deploy returned non-zero exit code. Aborting further steps." -ForegroundColor Red
    exit $LASTEXITCODE
}

if ($SetTarget) {
    Write-Host "SetTarget specified — enumerating functions and updating env vars"

    # Get a list of function names in the dev project
    $funcNames = & gcloud functions list --project=$DevProject --regions=$Region --format="value(name)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "gcloud functions list failed. Ensure gcloud is installed, authenticated, and you have the correct permissions." -ForegroundColor Red
        exit 1
    }

    $funcNames = $funcNames | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    if (-not $funcNames) {
        Write-Host "No functions found in project $DevProject (region $Region)." -ForegroundColor Yellow
        exit 0
    }

    foreach ($fn in $funcNames) {
        Write-Host "Updating function $fn with TARGET_PROJECT and TARGET_DATASET"
        # NOTE: This will redeploy each function. It uses the current local source and
        # assumes the function's entry point and runtime are already correctly configured
        # in the existing deployment. If your deployment requires explicit --entry-point
        # or other flags, update this command accordingly.
        gcloud functions deploy $fn `
            --project=$DevProject `
            --region=$Region `
            --gen2 `
            --runtime=python313 `
            --source="./functions" `
            --set-env-vars="TARGET_PROJECT=$DevProject,TARGET_DATASET=$DevDataset"

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to redeploy function $fn (gcloud returned non-zero). Continuing with next function." -ForegroundColor Yellow
        } else {
            Write-Host "Successfully redeployed $fn with env vars"
        }
    }
}

Write-Host "Redeploy script finished."