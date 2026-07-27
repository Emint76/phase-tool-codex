from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "phase_tool"
CORE = PACKAGE / "core.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        parts = [function.attr]
        value = function.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def test_core_has_no_contract_or_effect_specific_control_flow() -> None:
    source = CORE.read_text(encoding="utf-8")
    exact_forbidden = {
        "fixture_create.v1",
        "fixture_append.v1",
        "fixture_copy.v1",
        "exclusive_create",
        "append_record",
        "copy_blob",
    }
    assert exact_forbidden.isdisjoint(set(source.replace('"', " ").replace("'", " ").split()))
    tree = _tree(CORE)
    comparisons = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)]
    branch_literals = {
        constant.value
        for comparison in comparisons
        for constant in ast.walk(comparison)
        if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
    }
    assert exact_forbidden.isdisjoint(branch_literals)


def test_only_mechanism_boundary_owns_target_write_primitives() -> None:
    allowed_write_modules = {
        "mutation/exclusive_create.py",
        "evidence/__init__.py",
        "freeze/__init__.py",
    }
    forbidden_calls = {"os.open", "os.replace", "shutil.move", "write_bytes", "write_text", "unlink", "rename"}
    hits: list[tuple[str, int, str]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            terminal = name.rsplit(".", 1)[-1]
            if name == "os.open" or terminal in forbidden_calls:
                if relative not in allowed_write_modules:
                    hits.append((relative, node.lineno, name))
            if terminal == "open" and relative not in allowed_write_modules:
                modes = [arg.value for arg in node.args[1:2] if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
                modes += [
                    keyword.value.value
                    for keyword in node.keywords
                    if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)
                ]
                if any(set(mode) & set("wax+") for mode in modes):
                    hits.append((relative, node.lineno, f"open:{modes[0]}"))
    assert hits == []


def test_no_shell_exec_subprocess_or_dynamic_module_loading() -> None:
    forbidden_imports = {"subprocess", "runpy"}
    forbidden_calls = {"eval", "exec", "compile", "builtins.eval", "builtins.exec", "builtins.compile", "__import__", "builtins.__import__", "importlib.import_module", "subprocess.Popen", "subprocess.run", "os.system"}
    hits: list[tuple[str, int, str]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in forbidden_imports:
                        hits.append((relative, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] in forbidden_imports:
                hits.append((relative, node.lineno, node.module or ""))
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in forbidden_calls:
                    hits.append((relative, node.lineno, name))
    assert hits == []


def test_phase_core_exposes_one_top_level_lifecycle() -> None:
    tree = _tree(CORE)
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "PhaseCore"]
    assert len(classes) == 1
    public_runs = [node for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run"]
    assert len(public_runs) == 1
