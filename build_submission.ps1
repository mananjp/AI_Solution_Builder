# AI Solution Builder — Comprehensive Submission Package Builder
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

$ErrorActionPreference = "Stop"
$srcRoot = "d:\git\AI_Solution_Builder"
$targetDir = "d:\git\AI_Solution_Builder_Submission"
$zipPath = "d:\git\AI_Solution_Builder_Submission_20261001.zip"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "   AI Solution Builder — Final Submission Package Builder" -ForegroundColor Cyan
Write-Host "   CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# Clean target directory if exists
if (Test-Path $targetDir) {
    Write-Host "Cleaning existing submission folder: $targetDir" -ForegroundColor Gray
    Remove-Item $targetDir -Recurse -Force
}
New-Item -ItemType Directory -Path $targetDir | Out-Null

# ── 0. Root Presentation & Navigation Files ──
Write-Host "[0/9] Copying root handover documents..." -ForegroundColor Yellow
$rootFiles = @("00_START_HERE.html", "SUBMISSION.md", "GITHUB_ACCESS.md", "README.md")
foreach ($rf in $rootFiles) {
    $src = Join-Path $srcRoot $rf
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $targetDir $rf) -Force
    }
}
Write-Host "  Root documents copied." -ForegroundColor Green

# ── 1. Clean Source Code ──
Write-Host "[1/9] Packaging complete clean source code..." -ForegroundColor Yellow
$srcDest = Join-Path $targetDir "01_Source_Code"
New-Item -ItemType Directory -Path $srcDest | Out-Null

$excludeDirs = @(
    ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache", "__pycache__",
    "node_modules", ".next", ".data", "builds", "b6d29a91112e",
    "mvp_builder_fix", ".venv", ".venv-old", "sutra_os", ".gradle", "build"
)
$excludeFiles = @(".env", "AI_Solution_Builder_Voiceover.mp4", "*.pyc", "*.zip")

$xdArgs = $excludeDirs | ForEach-Object { "/XD", $_ }
$xfArgs = $excludeFiles | ForEach-Object { "/XF", $_ }

& robocopy $srcRoot $srcDest /E /NFL /NDL /NJH /NJS /NC /NS /NP @xdArgs @xfArgs | Out-Null
Write-Host "  Source code packaged." -ForegroundColor Green

# ── 2. Project Manuals ──
Write-Host "[2/9] Packaging project manuals..." -ForegroundColor Yellow
$manualsDest = Join-Path $targetDir "02_Project_Manuals"
New-Item -ItemType Directory -Path $manualsDest | Out-Null

$manualsSrc = Join-Path $srcRoot "docs\manuals"
if (Test-Path $manualsSrc) {
    Copy-Item "$manualsSrc\*.md" $manualsDest -Force
}
Write-Host "  Project manuals packaged." -ForegroundColor Green

# ── 3. Technical Documentation & Architecture ──
Write-Host "[3/9] Packaging documentation & architecture records..." -ForegroundColor Yellow
$docsDest = Join-Path $targetDir "03_Documentation"
New-Item -ItemType Directory -Path $docsDest | Out-Null

$docsList = @(
    "SUBMISSION.md",
    "README.md",
    "AUDIT.md",
    "AUDIT_UI_STATES.md",
    "AI_Solution_Builder_Alignment_Check.md",
    "AI_Solution_Builder_Implementation_Plan_v2.md",
    "deploy_plan.md",
    "security_scanning_plan.md"
)
foreach ($d in $docsList) {
    $src = Join-Path $srcRoot $d
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $docsDest $d) -Force
    }
}

$adrSrc = Join-Path $srcRoot "docs\adr"
if (Test-Path $adrSrc) {
    $adrDest = Join-Path $docsDest "architecture_decision_records"
    New-Item -ItemType Directory -Path $adrDest | Out-Null
    Copy-Item "$adrSrc\*" $adrDest -Recurse -Force
}
$secDoc = Join-Path $srcRoot "docs\security-scanning.md"
if (Test-Path $secDoc) {
    Copy-Item $secDoc (Join-Path $docsDest "security-scanning.md") -Force
}
Write-Host "  Documentation packaged." -ForegroundColor Green

# ── 4. Database Assets ──
Write-Host "[4/9] Packaging database assets & DDL..." -ForegroundColor Yellow
$dbDest = Join-Path $targetDir "04_Database_Assets"
New-Item -ItemType Directory -Path $dbDest | Out-Null

$schemaSql = Join-Path $srcRoot "backend\schema.sql"
if (Test-Path $schemaSql) {
    Copy-Item $schemaSql (Join-Path $dbDest "schema.sql") -Force
}

$alembicSrc = Join-Path $srcRoot "backend\alembic"
if (Test-Path $alembicSrc) {
    Copy-Item $alembicSrc (Join-Path $dbDest "alembic_migrations") -Recurse -Force
}

$modelsSrc = Join-Path $srcRoot "backend\app\models"
if (Test-Path $modelsSrc) {
    $modelsDest = Join-Path $dbDest "orm_models"
    New-Item -ItemType Directory -Path $modelsDest | Out-Null
    Copy-Item "$modelsSrc\*.py" $modelsDest -Force
}

$schemasSrc = Join-Path $srcRoot "backend\app\schemas"
if (Test-Path $schemasSrc) {
    $schemasDest = Join-Path $dbDest "api_schemas"
    New-Item -ItemType Directory -Path $schemasDest | Out-Null
    Copy-Item "$schemasSrc\*.py" $schemasDest -Force
}
Write-Host "  Database assets packaged." -ForegroundColor Green

# ── 5. Environment Configuration ──
Write-Host "[5/9] Packaging environment templates & container configs..." -ForegroundColor Yellow
$envDest = Join-Path $targetDir "05_Environment_Configuration"
New-Item -ItemType Directory -Path $envDest | Out-Null

$envFiles = @(
    ".env.example",
    "docker-compose.yml",
    "render.yaml",
    "fly.toml",
    "app.Dockerfile",
    "backend.Dockerfile",
    "builder.Dockerfile",
    ".dockerignore"
)
foreach ($ef in $envFiles) {
    $src = Join-Path $srcRoot $ef
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $envDest $ef) -Force
    }
}
Copy-Item (Join-Path $srcRoot "backend\requirements.txt") (Join-Path $envDest "backend_requirements.txt") -Force
Copy-Item (Join-Path $srcRoot "backend\requirements-dev.txt") (Join-Path $envDest "backend_requirements-dev.txt") -Force
Copy-Item (Join-Path $srcRoot "frontend\package.json") (Join-Path $envDest "frontend_package.json") -Force
Write-Host "  Environment configuration packaged." -ForegroundColor Green

# ── 6. AI & Third-Party Details ──
Write-Host "[6/9] Packaging AI & third-party integration specifications..." -ForegroundColor Yellow
$aiDest = Join-Path $targetDir "06_AI_and_Third_Party_Details"
New-Item -ItemType Directory -Path $aiDest | Out-Null

$aiDoc = Join-Path $srcRoot "docs\AI_AND_THIRD_PARTY_INTEGRATIONS.md"
if (Test-Path $aiDoc) {
    Copy-Item $aiDoc (Join-Path $aiDest "AI_AND_THIRD_PARTY_INTEGRATIONS.md") -Force
}
Write-Host "  AI and third-party details packaged." -ForegroundColor Green

# ── 7. Presentation Assets ──
Write-Host "[7/9] Packaging presentation assets & video..." -ForegroundColor Yellow
$presDest = Join-Path $targetDir "07_Presentation_Assets"
New-Item -ItemType Directory -Path $presDest | Out-Null

$presAssets = @(
    "AI Solution Builder (1).png",
    "AI Solution Builder.pdf",
    "AI Solution Builder_ End-to-End Implementation Pla.pdf",
    "AI_Solution_Builder_Voiceover.mp4"
)
foreach ($pa in $presAssets) {
    $src = Join-Path $srcRoot $pa
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $presDest $pa) -Force
    }
}
Write-Host "  Presentation assets packaged." -ForegroundColor Green

# ── 8. GitHub & CI/CD ──
Write-Host "[8/9] Packaging GitHub access & CI/CD workflows..." -ForegroundColor Yellow
$ciDest = Join-Path $targetDir "08_GitHub_and_CI_CD"
New-Item -ItemType Directory -Path $ciDest | Out-Null

$ghAccess = Join-Path $srcRoot "GITHUB_ACCESS.md"
if (Test-Path $ghAccess) {
    Copy-Item $ghAccess (Join-Path $ciDest "GITHUB_ACCESS.md") -Force
}

$ghWorkflows = Join-Path $srcRoot ".github"
if (Test-Path $ghWorkflows) {
    Copy-Item $ghWorkflows $ciDest -Recurse -Force
}
Write-Host "  GitHub & CI/CD packaged." -ForegroundColor Green

# ── 9. Automated Test Suite ──
Write-Host "[9/9] Packaging automated test suite..." -ForegroundColor Yellow
$testDest = Join-Path $targetDir "09_Test_Suite"
New-Item -ItemType Directory -Path $testDest | Out-Null

$testsSrc = Join-Path $srcRoot "backend\tests"
if (Test-Path $testsSrc) {
    Copy-Item "$testsSrc\*.py" $testDest -Force
    $fixturesSrc = Join-Path $testsSrc "fixtures"
    if (Test-Path $fixturesSrc) {
        Copy-Item $fixturesSrc (Join-Path $testDest "fixtures") -Recurse -Force
    }
}
Write-Host "  Test suite packaged." -ForegroundColor Green

Write-Host ""
Write-Host "Submission folder created at: $targetDir" -ForegroundColor Cyan
Write-Host ""

# ── Create ZIP Archive ──
Write-Host "Creating compressed archive ($zipPath)..." -ForegroundColor Yellow
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Compress-Archive -Path "$targetDir\*" -DestinationPath $zipPath -Force

$zipItem = Get-Item $zipPath
$zipSizeMb = [math]::Round($zipItem.Length / 1MB, 2)

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "   SUBMISSION PACKAGE GENERATION COMPLETE!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "  Uncompressed Folder: $targetDir" -ForegroundColor White
Write-Host "  Compressed Archive:  $zipPath ($zipSizeMb MB)" -ForegroundColor White
Write-Host ""
Write-Host "Folder Structure:" -ForegroundColor Cyan
Get-ChildItem -Path $targetDir | ForEach-Object {
    Write-Host "  - $($_.Name)" -ForegroundColor White
}
Write-Host ""
