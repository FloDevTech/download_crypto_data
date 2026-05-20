param()

$ErrorActionPreference = "Stop"
$exitCode = 0

function Ok($message) {
    Write-Host "[OK]    $message" -ForegroundColor Green
}

function Warn($message) {
    Write-Host "[WARN]  $message" -ForegroundColor Yellow
}

function Fail($message) {
    Write-Host "[FAIL]  $message" -ForegroundColor Red
}

function Run-Python {
    param([string[]]$Arguments)
    & python @Arguments
}

Write-Host "== 1. Verificando entorno =="

try {
    $pythonVersion = Run-Python @("--version") 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "python no esta instalado"
    }
    Ok "python -> $pythonVersion"
}
catch {
    Fail "python no esta instalado o no esta disponible en PATH"
    exit 1
}

$versionOk = Run-Python @("-c", "import sys; print(int(sys.version_info >= (3, 9)))")
if ($LASTEXITCODE -ne 0 -or $versionOk.Trim() -ne "1") {
    Fail "Se requiere Python >= 3.9"
    exit 1
}
Ok "Version de Python compatible"

Write-Host ""
Write-Host "== 2. Verificando archivos base del arnes =="

$requiredFiles = @(
    "AGENTS.md",
    "feature_list.json",
    "progress/current.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
    "docs/specs.md",
    "CHECKPOINTS.md"
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        Fail "Falta archivo base: $file"
        $exitCode = 1
    }
    else {
        Ok "Existe $file"
    }
}

Write-Host ""
Write-Host "== 3. Validando feature_list.json y specs =="

$validationCode = @'
import json, os, sys

try:
    with open("feature_list.json", encoding="utf-8") as fh:
        data = json.load(fh)

    valid = {"pending", "spec_ready", "in_progress", "done", "blocked"}
    in_progress = [f for f in data["features"] if f["status"] == "in_progress"]

    if len(in_progress) > 1:
        print(f"[FAIL]  Hay {len(in_progress)} features en in_progress (maximo 1)")
        sys.exit(1)

    requires_spec = {"spec_ready", "in_progress", "done"}
    spec_errors = []

    for feature in data["features"]:
        if feature["status"] not in valid:
            print(f"[FAIL]  Estado invalido en feature {feature['id']}: {feature['status']}")
            sys.exit(1)

        if feature.get("sdd") and feature["status"] in requires_spec:
            spec_dir = os.path.join("specs", feature["name"])
            for filename in ("requirements.md", "design.md", "tasks.md"):
                path = os.path.join(spec_dir, filename)
                if not os.path.isfile(path):
                    spec_errors.append(
                        f"feature {feature['id']} ({feature['name']}) en {feature['status']} sin {path}"
                    )

    if spec_errors:
        for error in spec_errors:
            print(f"[FAIL]  {error}")
        sys.exit(1)

    print(f"[OK]    feature_list.json valido ({len(data['features'])} features)")
    print("[OK]    Specs presentes para features sdd con estado no-pending")
except SystemExit:
    raise
except Exception as exc:
    print(f"[FAIL]  feature_list.json o specs invalidos: {exc}")
    sys.exit(1)
'@

$validationCode | python -
if ($LASTEXITCODE -ne 0) {
    $exitCode = 1
}

Write-Host ""
Write-Host "== 4. Ejecutando tests =="

if (Test-Path -LiteralPath "tests" -PathType Container) {
    & python -m unittest discover -s tests -v
    if ($LASTEXITCODE -eq 0) {
        Ok "Todos los tests pasan"
    }
    else {
        Fail "Hay tests rotos"
        $exitCode = 1
    }
}
else {
    Warn "Carpeta tests/ no existe todavia"
}

Write-Host ""
Write-Host "== 5. Resumen =="

if ($exitCode -eq 0) {
    Ok "Entorno listo. Podes empezar a trabajar."
}
else {
    Fail "Entorno NO esta listo. Resolve los errores antes de avanzar."
}

exit $exitCode
