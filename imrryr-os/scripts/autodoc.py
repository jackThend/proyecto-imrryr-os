#!/usr/bin/env python3
"""
autodoc.py — Motor de Autodocumentación de Proyectos
======================================================
Fase 2.4: Genera/actualiza archivos de estado .md en cada proyecto,
resumiendo tecnologías, decisiones lógicas y pendientes.

Uso:
    python scripts/autodoc.py                          # actualiza todos
    python scripts/autodoc.py --project imrryr-os      # solo un proyecto
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "docs" / "proyectos"


def log(msg: str) -> None:
    print(f"[autodoc] {msg}", flush=True)


def git_log(project_path: Path, days: int = 1) -> str:
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return ""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_path), "log", f"--since={days}.day", "--oneline", "--no-decorate"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return ""
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


EXCLUDE_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".run", "dist", "build", ".next"}

def _rglob_skip(project_path: Path, pattern: str) -> list[Path]:
    """rglob that skips excluded directories."""
    results = []
    for p in project_path.rglob(pattern):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(project_path).parts):
            continue
        results.append(p)
    return results

def list_technologies(project_path: Path) -> list[str]:
    techs = set()
    for pattern, lang in [
        ("*.py", "Python"), ("*.js", "JavaScript"), ("*.ts", "TypeScript"),
        ("*.tsx", "React/TypeScript"), ("*.rs", "Rust"), ("*.go", "Go"),
        ("*.java", "Java"), ("*.rb", "Ruby"), ("*.php", "PHP"),
        ("*.yaml", "YAML"), ("*.yml", "YAML"), ("*.json", "JSON"),
        ("*.md", "Markdown"), ("*.sql", "SQL"), ("*.html", "HTML"),
        ("*.css", "CSS"), ("*.sh", "Shell"), ("*.ps1", "PowerShell"),
    ]:
        if _rglob_skip(project_path, pattern):
            techs.add(lang)

    if (project_path / "package.json").exists():
        try:
            pkg = json.loads((project_path / "package.json").read_text(encoding="utf-8"))
            techs.add("Node.js")
            if "react" in str(pkg.get("dependencies", {})) or "react" in str(pkg.get("devDependencies", {})):
                techs.add("React")
            if "next" in str(pkg.get("dependencies", {})):
                techs.add("Next.js")
        except (json.JSONDecodeError, OSError):
            pass

    if (project_path / "requirements.txt").exists():
        techs.add("Python")
    if (project_path / "Cargo.toml").exists():
        techs.add("Rust")
    if (project_path / "go.mod").exists():
        techs.add("Go")

    return sorted(techs)


def generate_status(project_path: Path, project_name: str) -> str:
    techs = list_technologies(project_path)
    git_commits = git_log(project_path)

    lines = [
        f"# Estado del Proyecto: {project_name}",
        f"",
        f"> Generado: {date.today().isoformat()}",
        f"> Autodocumentación automática (scripts/autodoc.py)",
        f"",
        f"## Tecnologías detectadas",
        f"",
    ]
    for t in techs:
        lines.append(f"- {t}")

    lines.extend([
        f"",
        f"## Commits recientes (últimas 24h)",
        f"",
    ])

    if git_commits:
        lines.append("```")
        lines.append(git_commits)
        lines.append("```")
    else:
        lines.append("*Sin actividad reciente*")

    lines.extend([
        f"",
        f"## Estructura del proyecto",
        f"",
    ])

    # List top-level dirs
    for entry in sorted(project_path.iterdir()):
        if entry.name.startswith(".") or entry.name.startswith("__") or entry.name in EXCLUDE_DIRS:
            continue
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"- {entry.name}{suffix}")

    lines.extend([
        f"",
        f"---",
        f"_Actualizado: {date.today().isoformat()} por Imrryr OS_",
    ])

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Motor de autodocumentación de proyectos")
    ap.add_argument("--project", "-p", help="Nombre del proyecto (subcarpeta en docs/proyectos/)")
    args = ap.parse_args()

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    projects = {}
    if args.project:
        projects[args.project] = ROOT
    else:
        # Auto-detect: busca carpetas con .git o package.json o requirements.txt
        for entry in sorted(ROOT.iterdir()):
            if entry.is_dir() and not entry.name.startswith((".", "_", "node_modules", ".venv")):
                if (entry / ".git").exists() or (entry / "package.json").exists() or (entry / "requirements.txt").exists():
                    projects[entry.name] = entry

    if not projects:
        log("No se detectaron proyectos.")
        return 1

    for name, path in projects.items():
        status = generate_status(path, name)
        status_file = PROJECTS_DIR / f"{name}.md"
        status_file.write_text(status, encoding="utf-8")
        log(f"Estado actualizado: {status_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
