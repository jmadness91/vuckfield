"""World-Builder integrity check. Stdlib only; run from anywhere: python world-builder/check.py

Fails (exit 1) on anything that would make the next session start from a broken or misleading state.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_SECTIONS = ["## Now", "## Done this session", "## Next", "## Blocked / waiting on user"]
STATE_MAX_LINES = 100
REGION_KEYS = {"id", "name", "crs", "bbox_bng", "origin_bng", "terrain", "landmarks", "acceptance"}


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    return dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)


def check() -> list[str]:
    errors: list[str] = []

    for p in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        fm = {k.strip(): v.strip() for k, v in frontmatter(p).items()}
        if fm.get("name") != p.stem or not fm.get("description"):
            errors.append(f"{p.relative_to(ROOT)}: frontmatter needs name={p.stem!r} and a description")

    for p in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        fm = {k.strip(): v.strip() for k, v in frontmatter(p).items()}
        if fm.get("name") != p.parent.name or not fm.get("description"):
            errors.append(f"{p.relative_to(ROOT)}: frontmatter needs name={p.parent.name!r} and a description")

    state = ROOT / "world-builder" / "STATE.md"
    if not state.exists():
        errors.append("world-builder/STATE.md missing")
    else:
        text = state.read_text(encoding="utf-8")
        errors += [f"STATE.md: missing section {s!r}" for s in STATE_SECTIONS if s not in text]
        if len(text.splitlines()) > STATE_MAX_LINES:
            errors.append(f"STATE.md: {len(text.splitlines())} lines > {STATE_MAX_LINES}; move detail to memory/")
        if not re.search(r"Last updated: \d{4}-\d{2}-\d{2}", text):
            errors.append("STATE.md: needs 'Last updated: YYYY-MM-DD'")

    numbers = [int(n) for n in re.findall(r"^## D(\d+):", (ROOT / "world-builder/memory/decisions.md").read_text(), re.M)]
    if numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"decisions.md: numbering must be 1..n in order, got {numbers}")

    for p in sorted((ROOT / "regions").glob("*.json")):
        raw = json.loads(p.read_text())
        missing = REGION_KEYS - raw.keys()
        if missing:
            errors.append(f"{p.relative_to(ROOT)}: missing keys {sorted(missing)}")
        if raw.get("id") != p.stem:
            errors.append(f"{p.relative_to(ROOT)}: id must equal filename")
        build = ROOT / "build" / "regions" / p.stem
        manifest = build / "manifest.json"
        if not manifest.exists():
            errors.append(f"{p.relative_to(ROOT)}: not built (no {manifest.relative_to(ROOT)})")
            continue
        m = json.loads(manifest.read_text())
        if m.get("region") != p.stem:
            errors.append(f"{manifest.relative_to(ROOT)}: region field {m.get('region')!r} != {p.stem!r}")
        for key, info in m.get("files", {}).items():
            f = build / info["file"]
            if not f.exists():
                errors.append(f"{manifest.relative_to(ROOT)}: {key} -> {info['file']} missing")
            elif f.stat().st_size != info["bytes"]:
                errors.append(f"{f.relative_to(ROOT)}: size differs from manifest (hand-edited or stale)")
        built_landmarks = {lm["id"] for lm in m.get("landmarks", [])}
        for lm in raw.get("landmarks", []):
            if lm["id"] not in built_landmarks:
                errors.append(f"{manifest.relative_to(ROOT)}: landmark {lm['id']!r} not built; rebuild region")

    return errors


def main() -> int:
    errors = check()
    for e in errors:
        print(f"FAIL {e}")
    print("world-builder check:", "OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
