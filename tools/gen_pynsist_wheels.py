# -*- coding: utf-8 -*-
"""
Generate a complete Pynsist 'pypi_wheels' block from requirements.txt.
- Resolves full dependency tree using the CURRENT ENVIRONMENT's installed packages.
- Pins each package to the installed version (what Pynsist will fetch as wheels).
- Ignores comments, blank lines, and non-requirement directives in requirements.txt.

Usage:
    python tools/gen_pynsist_wheels.py requirements.txt > wheels.txt
"""

import sys
import re
from collections import deque
from typing import Dict, Set, List

# Python 3.9: importlib.metadata is available as stdlib
try:
    from importlib.metadata import distributions, Distribution
except ImportError:
    from importlib_metadata import distributions, Distribution  # type: ignore

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
except Exception:
    print(
        "ERROR: This script requires 'packaging' installed in the current env.",
        file=sys.stderr,
    )
    sys.exit(1)

NON_REQ_LINE = re.compile(r"^\s*(#|$|-r\s|--|https?://)")


def parse_requirements(path: str) -> List[Requirement]:
    reqs: List[Requirement] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if NON_REQ_LINE.match(line):
                continue
            # allow simple environment markers; Requirement will parse them
            try:
                reqs.append(Requirement(line))
            except Exception:
                # skip lines that aren't valid requirements (e.g., local paths)
                pass
    return reqs


def build_index() -> Dict[str, Distribution]:
    idx: Dict[str, Distribution] = {}
    for dist in distributions():
        name = canonicalize_name(dist.metadata["Name"])
        idx[name] = dist
    return idx


def expand_deps(
    top_level: List[Requirement], idx: Dict[str, Distribution]
) -> Dict[str, str]:
    """Return {project_name: version} for all reachable deps from top_level."""
    wanted: Set[str] = set()
    queue: deque[str] = deque()

    # seed with top-level names
    for r in top_level:
        name = canonicalize_name(r.name)
        wanted.add(name)
        queue.append(name)

    seen: Set[str] = set()
    while queue:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)

        dist = idx.get(name)
        if not dist:
            # package not installed in env: warn to stderr
            print(
                f"WARNING: requirement '{name}' is not installed in the current environment.",
                file=sys.stderr,
            )
            continue

        requires = dist.metadata.get_all("Requires-Dist") or []
        for req_line in requires:
            try:
                req = Requirement(req_line)
            except Exception:
                continue
            # evaluate simple markers; if markers present and not satisfied, skip
            if req.marker and not req.marker.evaluate():
                continue
            dep_name = canonicalize_name(req.name)
            if dep_name not in wanted:
                wanted.add(dep_name)
                queue.append(dep_name)

    # Build pinned versions from installed distributions
    pinned: Dict[str, str] = {}
    for name in wanted:
        dist = idx.get(name)
        if dist:
            # use normalized project name as published (for pretty output)
            project_name = dist.metadata["Name"]
            pinned[project_name] = dist.version
        else:
            # leave unresolved (will be missing)
            pinned[name] = "MISSING"
    return pinned


def main():
    if len(sys.argv) != 2:
        print("Usage: python gen_pynsist_wheels.py requirements.txt", file=sys.stderr)
        sys.exit(2)

    reqs = parse_requirements(sys.argv[1])
    if not reqs:
        print("ERROR: No valid requirements parsed.", file=sys.stderr)
        sys.exit(3)

    idx = build_index()
    pinned = expand_deps(reqs, idx)

    # Deterministic, case-insensitive sort by project name
    items = sorted(pinned.items(), key=lambda kv: kv[0].lower())

    # Print in a format directly pasteable under 'pypi_wheels ='
    for name, version in items:
        if version == "MISSING":
            # Keep it visible so you can decide what to do
            print(f"# {name}  <-- MISSING in this env")
        else:
            print(f"{name}=={version}")


if __name__ == "__main__":
    main()
