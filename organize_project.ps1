Write-Host "🔧 Organizando estructura del proyecto..." -ForegroundColor Cyan

# 1. Crear carpetas necesarias
Write-Host "`n📁 Creando carpetas..." -ForegroundColor Yellow
$folders = @('templates', 'static/css', 'static/js', 'static/python')
foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        Write-Host "  ✓ Creada: $folder" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Ya existe: $folder" -ForegroundColor Gray
    }
}

# 2. Mover index.html a templates/
Write-Host "`n📄 Moviendo archivos HTML..." -ForegroundColor Yellow
$htmlPaths = @(
    "static/html/index.html",
    "static/index.html",
    "index.html"
)

$moved = $false
foreach ($path in $htmlPaths) {
    if (Test-Path $path) {
        Move-Item $path templates/index.html -Force
        Write-Host "  ✓ Movido: $path → templates/index.html" -ForegroundColor Green
        $moved = $true
        break
    }
}

if (-not $moved -and (Test-Path "templates/index.html")) {
    Write-Host "  ✓ index.html ya está en templates/" -ForegroundColor Gray
}

# 3. Limpiar carpetas vacías
Write-Host "`n🧹 Limpiando carpetas vacías..." -ForegroundColor Yellow
if (Test-Path "static/html") {
    $items = Get-ChildItem "static/html" -Force
    if ($items.Count -eq 0) {
        Remove-Item "static/html" -Force
        Write-Host "  ✓ Eliminada: static/html (vacía)" -ForegroundColor Green
    }
}

# 4. Verificar estructura final
Write-Host "`n✅ Estructura final:" -ForegroundColor Cyan
Write-Host ""
Get-ChildItem -Directory | ForEach-Object {
    Write-Host "📁 $($_.Name)" -ForegroundColor Blue
    Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  └─ $($_.Name)" -ForegroundColor Gray
    }
}

# 5. Git add
Write-Host "`n📦 Preparando commit..." -ForegroundColor Yellow
git add templates/
git add static/
git status --short

Write-Host "`n✨ ¡Listo! Ejecuta:" -ForegroundColor GreenWrite-Host "Organizando estructura del proyecto..." -ForegroundColor Cyan

# 1. Crear carpetas necesarias
Write-Host "`nCreando carpetas..." -ForegroundColor Yellow
$folders = @('templates', 'static/css', 'static/js', 'static/python')
foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        Write-Host "  Creada: $folder" -ForegroundColor Green
    } else {
        Write-Host "  Ya existe: $folder" -ForegroundColor Gray
    }
}

# 2. Mover index.html a templates/
Write-Host "`nMoviendo archivos HTML..." -ForegroundColor Yellow
$htmlPaths = @(
    "static/html/index.html",
    "static/index.html",
    "index.html"
)

$moved = $false
foreach ($path in $htmlPaths) {
    if (Test-Path $path) {
        Move-Item $path templates/index.html -Force
        Write-Host "  Movido: $path a templates/index.html" -ForegroundColor Green
        $moved = $true
        break
    }
}

if (-not $moved -and (Test-Path "templates/index.html")) {
    Write-Host "  index.html ya esta en templates/" -ForegroundColor Gray
}

# 3. Limpiar carpetas vacias
Write-Host "`nLimpiando carpetas vacias..." -ForegroundColor Yellow
if (Test-Path "static/html") {
    $items = Get-ChildItem "static/html" -Force
    if ($items.Count -eq 0) {
        Remove-Item "static/html" -Force
        Write-Host "  Eliminada: static/html (vacia)" -ForegroundColor Green
    }
}

# 4. Verificar estructura final
Write-Host "`nEstructura final:" -ForegroundColor Cyan
Write-Host ""
Get-ChildItem -Directory | ForEach-Object {
    Write-Host "Carpeta: $($_.Name)" -ForegroundColor Blue
    Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor Gray
    }
}

# 5. Git add
Write-Host "`nPreparando commit..." -ForegroundColor Yellow
git add templates/
git add static/
git status --short

Write-Host "`nListo! Ejecuta:" -ForegroundColor Green
Write-Host "  git commit -m `"Organize project structure`"" -ForegroundColor White
Write-Host "  git push origin main" -ForegroundColor White
Write-Host "  git commit -m `"Organize project structure`"" -ForegroundColor White
Write-Host "  git push origin main" -ForegroundColor White