"""Compute the transitive local-import and JSON-file closure of the kept roots.

Usage:
    python tools/keep_set.py
"""

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

KEPT_ROOTS = [
    ROOT / "studio" / "__init__.py",
    ROOT / "studio" / "state.py",
    ROOT / "studio" / "server.py",
    ROOT / "studio" / "desktop.py",
    ROOT / "mcp_server" / "server.py",
    HERE / "local_api.py",
    HERE / "giveaways.py",
    HERE / "look_cards.py",
    HERE / "refine_image.py",
    HERE / "vision_lint.py",
    HERE / "history.py",
    HERE / "pricing.py",
    HERE / "scene_variety.py",
    HERE / "realism_lint.py",
    HERE / "generate_image.py",
    HERE / "upscale_image.py",
    HERE / "keep_set.py",
]


def tool_modules():
    return {p.stem: p for p in HERE.glob("*.py")}


def imports_in_file(path: Path, known_tools: set[str]) -> set[str]:
    found = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in known_tools:
                    found.add(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in known_tools:
                found.add(top)
    return found


def json_files_in_file(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'[\'"]([A-Za-z0-9_]+\.json)[\'"]', text))


def compute_closure():
    modules = tool_modules()
    known = set(modules.keys())
    visited_files = set()
    kept_tools = set()
    kept_json = set()

    queue = [p.resolve() for p in KEPT_ROOTS if p.exists()]
    while queue:
        current = queue.pop(0)
        if current in visited_files:
            continue
        visited_files.add(current)
        if current.parent == HERE and current.suffix == ".py":
            kept_tools.add(current.name)
        for j in json_files_in_file(current):
            if (HERE / j).exists():
                kept_json.add(j)
        for mod_name in imports_in_file(current, known):
            target = modules[mod_name].resolve()
            if target not in visited_files:
                queue.append(target)

    all_tools = sorted(p.name for p in HERE.glob("*.py"))
    all_json = sorted(p.name for p in HERE.glob("*.json"))

    delete_tools = sorted(set(all_tools) - kept_tools)
    delete_json = sorted(set(all_json) - kept_json)

    return {
        "kept_tools": sorted(kept_tools),
        "kept_json": sorted(kept_json),
        "delete_tools": delete_tools,
        "delete_json": delete_json,
    }


def main():
    report = compute_closure()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
