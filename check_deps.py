from __future__ import annotations

import sys as _sys

_here = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]
if _sys.path:
    head = _sys.path[0]
    if head in {"", ".", _here}:
        _sys.path.pop(0)

import argparse
import ast
import os
import re
from dataclasses import dataclass
from importlib import metadata
from importlib import util as importlib_util


_KIND_RANK = {"optional": 0, "conditional": 1, "required": 2}
_KIND_BY_RANK = {v: k for k, v in _KIND_RANK.items()}


def _combine_kind(outer: str, inner: str) -> str:
    return _KIND_BY_RANK[min(_KIND_RANK[outer], _KIND_RANK[inner])]


def _is_ignored_dir(dir_name: str) -> bool:
    return dir_name in {".git", "__pycache__", ".venv", "venv", "env", ".mypy_cache", ".pytest_cache"}


def _iter_py_files(root: str, *, include_tests: bool) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _is_ignored_dir(d)]
        rel = os.path.relpath(dirpath, root)
        if not include_tests and (rel == "tests" or rel.startswith("tests" + os.sep)):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    out.sort()
    return out


def _exc_names(ex: ast.expr | None) -> set[str]:
    if ex is None:
        return set()
    if isinstance(ex, ast.Name):
        return {ex.id}
    if isinstance(ex, ast.Attribute):
        return {ex.attr}
    if isinstance(ex, ast.Tuple):
        names: set[str] = set()
        for elt in ex.elts:
            names |= _exc_names(elt)
        return names
    return set()


def _block_has_raise(block: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=block, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
    return False


def _block_has_import(block: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=block, type_ignores=[])):
        if isinstance(node, ast.Import | ast.ImportFrom):
            return True
    return False


def _try_body_kind(node: ast.Try) -> str:
    if not node.handlers:
        return "required"
    handler_names: set[str] = set()
    handler_raises = False
    for h in node.handlers:
        handler_names |= _exc_names(h.type)
        if _block_has_raise(h.body) or _block_has_import(h.body):
            handler_raises = True
    if {"ImportError", "ModuleNotFoundError"} & handler_names:
        return "conditional" if handler_raises else "optional"
    if "Exception" in handler_names or "BaseException" in handler_names or not handler_names:
        return "conditional" if handler_raises else "optional"
    return "required"


@dataclass(frozen=True)
class ImportHit:
    module: str
    file: str
    line: int
    kind: str


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self._file_path = file_path
        self._hits: list[ImportHit] = []
        self._kind_stack: list[str] = ["required"]

    @property
    def hits(self) -> list[ImportHit]:
        return self._hits

    def _add(self, mod: str, line: int) -> None:
        if not mod:
            return
        top = mod.split(".", 1)[0]
        if top == "__future__":
            return
        self._hits.append(ImportHit(module=top, file=self._file_path, line=line, kind=self._kind_stack[-1]))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            return
        if node.module:
            self._add(node.module, node.lineno)

    def visit_Try(self, node: ast.Try) -> None:
        prev_kind = self._kind_stack[-1]
        body_kind = _combine_kind(prev_kind, _try_body_kind(node))
        self._kind_stack.append(body_kind)
        for stmt in node.body:
            self.visit(stmt)
        self._kind_stack.pop()

        self._kind_stack.append(prev_kind)
        for h in node.handlers:
            self.visit(h)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)
        self._kind_stack.pop()


def _collect_imports(py_path: str) -> list[ImportHit]:
    with open(py_path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src, filename=py_path)
    v = _ImportCollector(py_path)
    v.visit(tree)
    return v.hits


def _read_requirements(req_path: str) -> list[str]:
    reqs: list[str] = []
    if not req_path or not os.path.isfile(req_path):
        return reqs
    with open(req_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("-r", "--requirement", "-e", "--editable")):
                continue
            if line.startswith(("--index-url", "--extra-index-url", "--find-links")):
                continue
            reqs.append(line)
    return reqs


_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


def _req_name(req_line: str) -> str:
    m = _REQ_NAME_RE.match(req_line)
    if not m:
        return req_line.strip()
    return m.group(1)


def _dist_installed(dist_name: str) -> tuple[bool, str | None]:
    try:
        v = metadata.version(dist_name)
        return True, v
    except Exception:
        return False, None


def _module_spec(mod: str):
    try:
        return importlib_util.find_spec(mod)
    except Exception:
        return None


def _spec_origin(spec) -> str | None:
    if spec is None:
        return None
    if getattr(spec, "origin", None):
        return spec.origin
    locs = getattr(spec, "submodule_search_locations", None)
    if locs:
        try:
            return next(iter(locs))
        except Exception:
            return None
    return None


def _is_third_party_origin(origin: str | None) -> bool:
    if not origin:
        return False
    o = origin.replace("\\", "/").lower()
    return "/site-packages/" in o or "/dist-packages/" in o


def _format_hit(hit: ImportHit, root: str) -> str:
    try:
        rel = os.path.relpath(hit.file, root)
    except Exception:
        rel = hit.file
    return f"{rel}:{hit.line}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="check_deps.py")
    ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--requirements", default="requirements.txt")
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--strict", action="store_true", help="将 optional 也视为必须安装")
    ap.add_argument("--ignore", action="append", default=[], help="忽略的顶层模块名（可重复）")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    req_path = args.requirements
    if not os.path.isabs(req_path):
        req_path = os.path.join(root, req_path)

    pkg_name = os.path.basename(root)

    req_lines = _read_requirements(req_path)
    req_names = [_req_name(x) for x in req_lines]
    req_names_norm = {n.lower().replace("_", "-") for n in req_names}

    print(f"项目根目录: {root}")
    print(f"requirements: {req_path if os.path.isfile(req_path) else '(未找到)'}")
    print("")

    missing_required_dists: list[str] = []
    if req_names:
        print("== requirements.txt 依赖检查 ==")
        for name in req_names:
            ok, ver = _dist_installed(name)
            if ok:
                print(f"[OK] {name} ({ver})")
            else:
                print(f"[MISSING] {name}")
                missing_required_dists.append(name)
        print("")

    py_files = _iter_py_files(root, include_tests=args.include_tests)
    hits: list[ImportHit] = []
    for p in py_files:
        try:
            hits.extend(_collect_imports(p))
        except Exception as e:
            rel = os.path.relpath(p, root)
            print(f"[WARN] 解析失败: {rel} ({e})")

    ignored = {m.strip() for m in args.ignore if m.strip()}
    ignored |= {pkg_name}

    by_module: dict[str, list[ImportHit]] = {}
    for h in hits:
        if h.module in ignored:
            continue
        by_module.setdefault(h.module, []).append(h)

    results: list[tuple[str, str, bool, bool, str | None, list[str]]] = []
    for mod, mod_hits in sorted(by_module.items()):
        spec = _module_spec(mod)
        origin = _spec_origin(spec)
        installed = spec is not None
        third_party = _is_third_party_origin(origin)
        if not third_party and installed:
            continue
        kind_rank = min(_KIND_RANK[h.kind] for h in mod_hits)
        kind = _KIND_BY_RANK[kind_rank]
        declared = (mod.lower().replace("_", "-") in req_names_norm) or (mod.lower() in {n.lower() for n in req_names})
        examples = [_format_hit(h, root) for h in mod_hits[:8]]
        results.append((mod, kind, installed, declared, origin, examples))

    missing_mods: list[str] = []
    undeclared_mods: list[str] = []

    print("== 源码 import 依赖检查（第三方/缺失） ==")
    if not results:
        print("[OK] 未发现第三方 import，或均已安装")
    for mod, kind, installed, declared, origin, examples in results:
        status = "OK" if installed else "MISSING"
        declared_s = "declared" if declared else "undeclared"
        origin_s = origin or "-"
        print(f"[{status}] {mod} ({kind}, {declared_s})  origin={origin_s}")
        if examples:
            print("  " + ", ".join(examples))
        if not installed:
            missing_mods.append(mod)
        if not declared:
            undeclared_mods.append(mod)
    print("")

    vendor_candidate = os.path.join(root, "rpi_hid-1.2.5")
    if "rpi_hid" in by_module and not os.path.isdir(vendor_candidate):
        print("== vendoring 检查 ==")
        print(f"[WARN] 代码会尝试使用本地目录 rpi_hid-1.2.5，但当前未找到: {vendor_candidate}")
        print("")

    errors: list[str] = []
    if missing_required_dists:
        errors.append("requirements.txt 中声明的依赖未安装: " + ", ".join(sorted(set(missing_required_dists))))

    if missing_mods:
        effective_missing = []
        for mod, kind, installed, _, _, _ in results:
            if not installed:
                if kind == "optional" and not args.strict:
                    continue
                effective_missing.append(mod)
        if effective_missing:
            errors.append("源码中 import 的依赖缺失: " + ", ".join(sorted(set(effective_missing))))

    if undeclared_mods:
        errors.append("源码中 import 的依赖未在 requirements.txt 声明: " + ", ".join(sorted(set(undeclared_mods))))

    if errors:
        print("== 结论 ==")
        for e in errors:
            print(f"[FAIL] {e}")
        return 1

    print("== 结论 ==")
    print("[OK] 依赖检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
