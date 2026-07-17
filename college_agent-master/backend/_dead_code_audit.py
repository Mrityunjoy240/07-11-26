"""Systematic dead code audit - finds unused symbols across the live codebase."""
import ast
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(r"C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master")
BACKEND = BASE / "backend"
APP = BACKEND / "app"
TESTS = [BACKEND / "tests", BASE / "tests"]
SCRIPTS = [BASE / "scripts"]

EXCLUDE_DIRS = {"venv", "node_modules", "__pycache__", ".git", ".pytest_cache", ".ruff_cache", "chroma_db"}

def get_all_py_files():
    """Get all production .py files."""
    files = []
    for root in [APP, BACKEND / "services", BACKEND / "utils"]:
        if root.exists():
            for f in root.rglob("*.py"):
                if not any(x in str(f) for x in EXCLUDE_DIRS):
                    files.append(f)
    return sorted(set(files))

def get_test_files():
    files = []
    for d in TESTS + SCRIPTS:
        if d.exists():
            for f in d.rglob("*.py"):
                if not any(x in str(f) for x in EXCLUDE_DIRS):
                    files.append(f)
    return sorted(set(files))

def get_all_scripts_py():
    files = []
    for d in SCRIPTS:
        if d.exists():
            for f in d.rglob("*.py"):
                if not any(x in str(f) for x in EXCLUDE_DIRS):
                    files.append(f)
    return sorted(set(files))


def extract_definitions(filepath):
    """Extract all function, class, and constant definitions from a file."""
    with open(filepath, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return [], [], [], []
    
    functions = []
    classes = []
    constants = []
    imports = []
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            # Skip dunder methods
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            functions.append((node.name, node.lineno))
            # Also find inner functions
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    functions.append((child.name, child.lineno))
        elif isinstance(node, ast.AsyncFunctionDef):
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            functions.append((node.name, node.lineno))
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append((child.name, child.lineno))
        elif isinstance(node, ast.ClassDef):
            classes.append((node.name, node.lineno))
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name.startswith("__") and child.name.endswith("__"):
                        continue
                    functions.append((child.name, child.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    constants.append((target.id, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name if alias.asname else alias.name, node.lineno, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                imports.append((full, node.lineno, alias.asname))
    
    return functions, classes, constants, imports


def search_symbol(symbol, search_files):
    """Search for a symbol in all files. Returns list of (file, line, context)."""
    results = []
    for filepath in search_files:
        try:
            with open(filepath, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if symbol in line:
                        results.append((filepath, i, line.strip()[:120]))
        except:
            pass
    return results


def is_imported_as(imp):
    """Check if an import has an alias."""
    return imp[2] is not None


# Collect all files
prod_files = get_all_py_files()
test_files = get_test_files()
all_py_files = prod_files + test_files

print(f"Found {len(prod_files)} production files, {len(test_files)} test/script files")
print(f"\nProduction files:")
for f in prod_files:
    print(f"  {f.relative_to(BASE)}")

# Extract all definitions
all_defs = {}  # symbol -> [(file, line, kind)]
for f in prod_files:
    funcs, classes, consts, imports = extract_definitions(f)
    for name, lineno in funcs + classes + consts:
        if name not in all_defs:
            all_defs[name] = []
        all_defs[name].append((f, lineno, "function" if name in [n for n, _ in funcs] else "class" if name in [n for n, _ in classes] else "const"))

# For each definition, check if it's used elsewhere
excluded_symbols = {"True", "False", "None", "self", "cls", "logger", "logging", "os", "re", "json", "time", "datetime", "typing", "List", "Dict", "Optional", "Any", "Tuple", "Set", "Callable", "Union"}

print(f"\n{'='*80}")
print("UNUSED FUNCTIONS / CLASSES / CONSTANTS")
print(f"{'='*80}")

unused_findings = []

for symbol, definitions in sorted(all_defs.items()):
    if symbol in excluded_symbols:
        continue
    if symbol.startswith("_") and len(symbol) < 3:
        continue
    if len(definitions) > 1:
        continue  # defined in multiple files -> definitely used
    
    filepath, lineno, kind = definitions[0]
    relpath = filepath.relative_to(BASE)
    
    # Search for symbol usage in all files
    refs = search_symbol(symbol, all_py_files)
    
    # Filter: exclude the definition line itself
    usage_refs = [r for r in refs if not (r[0] == filepath and r[1] == lineno)]
    
    if not usage_refs:
        unused_findings.append((symbol, relpath, lineno, kind))
        print(f"  {kind.upper()}: {symbol} at {relpath}:{lineno}")
    else:
        # Check if all references are from the same file (self-use) or in tests only
        same_file_refs = [r for r in usage_refs if r[0] == filepath]
        test_only_refs = [r for r in usage_refs if any(str(t) in str(r[0]) for t in TESTS)]
        other_refs = [r for r in usage_refs if r not in same_file_refs and r not in test_only_refs]
        
        if not other_refs and not test_only_refs and len(same_file_refs) <= 2:
            # Only referenced in its own file, likely internal use only
            # Still has callers so it's not dead
            pass

print(f"\nTotal potentially unused symbols: {len(unused_findings)}")

# Now check for unused imports
print(f"\n{'='*80}")
print("UNUSED IMPORTS")
print(f"{'='*80}")

for f in prod_files:
    relpath = f.relative_to(BASE)
    funcs, classes, consts, imports = extract_definitions(f)
    
    # Collect all names defined/referenced in this file
    defined_names = set()
    for name, _ in funcs + classes + consts:
        defined_names.add(name)
    
    # Read file content for reference checking
    with open(f, encoding="utf-8") as fh:
        content = fh.read()
    
    for imp_name, imp_lineno, alias in imports:
        # Get the actual name used in code
        used_name = alias if alias else imp_name.split(".")[-1]
        
        if used_name in defined_names:
            continue  # defined here
        
        # Check if the name is actually used in the file (excluding the import line)
        # Simple check: count occurrences, minus 1 for the import line
        count = content.count(used_name)
        
        if count <= 1:  # Only in the import itself
            print(f"  UNUSED IMPORT: '{used_name}' at {relpath}:{imp_lineno} (from {imp_name})")
