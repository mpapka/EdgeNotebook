#!/usr/bin/env python3
"""Pre-publish check: does every lab still line up with labHelpers.py?

Run from the repo root before ./publish.sh. It is static, so it needs no
kernel, no box, and no containers.

It exists because renaming a toolkit function is a live-migration problem,
not a find-and-replace. `dockerDaemonUp` became `podmanReachable`, and a
notebook that had been open since before the rename raised
`NameError: name 'podmanReachable' is not defined` even though every file on
disk was correct. These checks catch the static half of that; the loader's
importlib.reload covers the running-kernel half.

Checks:
  1. every function a notebook calls exists in labHelpers or the notebook
  2. no stale helper name survives in a hint string or markdown
  3. every lab reloads the toolkit before importing it
  4. every cell carries the id nbformat 4.5 requires
"""
import ast, builtins, glob, json, re, sys

RETIRED = ("dockerVersions", "dockerPs", "dockerLogs", "dockerDaemonUp")
BUILTIN = set(dir(builtins)) | {"get_ipython", "display", "HTML", "Image",
                                "Markdown", "In", "Out", "exit", "quit"}


def exportedBy(path):
    names = set()
    for node in ast.parse(open(path).read()).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
    return {n for n in names if not n.startswith("_")}


def boundIn(tree):
    """Every name a cell binds: assignments, imports, args, loops, with, except."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                bound |= {s.id for s in ast.walk(t) if isinstance(s, ast.Name)}
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            bound |= {s.id for s in ast.walk(node.target) if isinstance(s, ast.Name)}
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                bound.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            bound |= {s.id for s in ast.walk(node.target) if isinstance(s, ast.Name)}
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            bound |= {s.id for s in ast.walk(node.optional_vars) if isinstance(s, ast.Name)}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
            bound |= set(node.names)
    return bound


def main():
    public = exportedBy("labHelpers.py")
    failures = 0
    for path in sorted(glob.glob("lab*.ipynb")):
        nb = json.load(open(path))
        problems = []

        bound, used = set(), []
        for idx, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code":
                continue
            lines = [("" if l.lstrip().startswith(("!", "%", "?")) else l)
                     for l in "".join(c.get("source") or []).splitlines()]
            try:
                tree = ast.parse("\n".join(lines))
            except SyntaxError:
                continue
            bound |= boundIn(tree)
            for n in ast.walk(tree):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used.append((idx, n.id))
        for idx, name in sorted(set(used)):
            if name not in public and name not in bound and name not in BUILTIN:
                problems.append(f"cell {idx}: uses '{name}', which nothing defines")

        # join the real sources: json.dumps would escape the quotes inside
        # sys.modules["labHelpers"] and never match
        whole = "\n".join("".join(c.get("source") or []) for c in nb["cells"])
        for old in RETIRED:
            if re.search(rf'\b{old}\b', whole):
                problems.append(f"retired helper name '{old}' still appears")

        if 'importlib.reload(sys.modules["labHelpers"])' not in whole:
            problems.append("loader does not reload labHelpers; a republish will "
                            "break an open kernel")

        noId = sum(1 for c in nb["cells"] if "id" not in c)
        if noId:
            problems.append(f"{noId} cell(s) missing the nbformat 4.5 id")

        if problems:
            failures += len(problems)
            print(f"  {path}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"  {path:34s} ok ({len(nb['cells'])} cells)")

    print(f"\n  {'PASS' if not failures else str(failures) + ' PROBLEM(S)'}"
          f"  -- labHelpers exports {len(public)} public names")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
