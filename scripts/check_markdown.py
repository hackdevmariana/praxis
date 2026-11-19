"""Validate Markdown links, anchors, and minimal frontmatter conventions."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_DOC_RE = re.compile(r"docs/\d{2}-[^/]+\.md$")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_]+):\s*(.*)$")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def _targets() -> list[Path]:
    files = [
        ROOT / "README.md",
        ROOT / "TODO.md",
        ROOT / "CHANGELOG.md",
        ROOT / "tests" / "fixtures" / "README.md",
    ]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return files


def _iter_content_lines(path: Path):
    in_fence = False
    marker = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            if not in_fence:
                in_fence = True
                marker = stripped[:3]
            elif stripped.startswith(marker):
                in_fence = False
            continue
        if not in_fence:
            yield number, line


def _slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text.strip())


def _headings(path: Path) -> set[str]:
    slugs: set[str] = set()
    if path.suffix.lower() != ".md" or not path.is_file():
        return slugs
    for _, line in _iter_content_lines(path):
        match = HEADING_RE.match(line)
        if match is None:
            continue
        title = re.sub(r"\s+#+\s*$", "", match.group(2))
        slugs.add(_slugify(title))
    return slugs


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = FRONTMATTER_KEY_RE.match(line)
        if match is not None:
            values[match.group(1)] = match.group(2).strip().strip("\"'")
    return values


def _check_links(path: Path, errors: list[str]) -> None:
    headings: dict[Path, set[str]] = {}
    for number, line in _iter_content_lines(path):
        for match in LINK_RE.finditer(line):
            raw_target = match.group(1).strip().strip("<>")
            target = unquote(raw_target)
            if target.startswith(EXTERNAL_PREFIXES):
                continue
            path_part, separator, anchor = target.partition("#")
            if path_part:
                candidate = (path.parent / path_part).resolve()
                if not candidate.exists():
                    errors.append(f"{path.relative_to(ROOT)}:{number}: enlace roto: {raw_target}")
                    continue
            else:
                candidate = path
            if not separator or not anchor:
                continue
            if candidate.suffix.lower() != ".md":
                continue
            if candidate not in headings:
                headings[candidate] = _headings(candidate)
            if _slugify(anchor) not in headings[candidate]:
                errors.append(f"{path.relative_to(ROOT)}:{number}: ancla no encontrada: #{anchor}")


def _check_frontmatter(path: Path, errors: list[str]) -> None:
    relative = path.relative_to(ROOT).as_posix()
    values = _frontmatter(path)
    if NUMBERED_DOC_RE.search(relative):
        for key in ("estado", "version"):
            if key not in values:
                errors.append(f"{relative}:1: falta `{key}` en frontmatter")
        return
    tools_root = ROOT / "docs" / "tools"
    if path.parents and tools_root in path.parents and path.name != "README.md":
        for key in ("estado", "version", "tool"):
            if key not in values:
                errors.append(f"{relative}:1: falta `{key}` en frontmatter")
        expected = ".".join(path.relative_to(tools_root).with_suffix("").parts)
        if "tool" in values and values["tool"] != expected:
            errors.append(
                f"{relative}:1: `tool` no coincide con la ruta: {values['tool']} != {expected}"
            )


def main() -> int:
    files = _targets()
    errors: list[str] = []
    for path in files:
        if not path.exists():
            errors.append(f"{path.relative_to(ROOT)}: fichero no encontrado")
            continue
        _check_links(path, errors)
        _check_frontmatter(path, errors)

    if errors:
        print("\n".join(errors))
        print(f"ERROR: {len(errors)} problema(s) en {len(files)} ficheros Markdown")
        return 1
    print(f"OK: {len(files)} ficheros Markdown validados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
