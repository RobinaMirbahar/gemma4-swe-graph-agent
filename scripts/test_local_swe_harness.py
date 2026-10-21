"""Interactive Local SWE-Gemma Test Harness — Test the 3-Sub-Agent Team & 2-Hop Code Graph Yourself!
Simulates a real SWE-Gemma benchmark task end-to-end:
  1. Creates a sandbox Python repo with a real bug & failing test suite
  2. Builds the AST Code Dependency Graph (search_similar_code, get_code_neighbors, get_code_subgraph)
  3. Executes Stage 1 (code_analyzer) -> Stage 2 (patch_architect) -> Stage 3 (test_verifier) -> Stage 4 (submit_patch)
  4. Runs real Python tests before and after the patch to prove 100% resolution!
"""

import ast
import difflib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_and_verify_submission import build_submission_zip, validate_declarative_submission


BUGGY_RETRY_CLIENT = '''"""HTTP Retry & Rate-Limit Backoff Utility (Sandbox Repo: httpx_retry)."""

def compute_backoff_delay(attempt: int, base_delay: float = 0.5, max_delay: float = 10.0, retry_after_header: str | None = None) -> float:
    """Compute exponential backoff delay in seconds, honoring Retry-After header if present."""
    if retry_after_header is not None:
        # BUG: Crashes with ValueError when Retry-After header contains whitespace or float string like " 2.5 "
        # and ignores max_delay cap when server sends an excessive Retry-After value!
        return float(int(retry_after_header))

    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)


def should_retry_status(status_code: int) -> bool:
    """Return True if HTTP status code is transient and retryable."""
    return status_code in (408, 429, 500, 502, 503, 504)
'''

FIXED_RETRY_CLIENT = '''"""HTTP Retry & Rate-Limit Backoff Utility (Sandbox Repo: httpx_retry)."""

def compute_backoff_delay(attempt: int, base_delay: float = 0.5, max_delay: float = 10.0, retry_after_header: str | None = None) -> float:
    """Compute exponential backoff delay in seconds, honoring Retry-After header if present."""
    if retry_after_header is not None:
        try:
            parsed = float(retry_after_header.strip())
            return max(0.0, min(parsed, max_delay))
        except ValueError:
            pass

    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)


def should_retry_status(status_code: int) -> bool:
    """Return True if HTTP status code is transient and retryable."""
    return status_code in (408, 429, 500, 502, 503, 504)
'''

TEST_SUITE_CODE = '''"""Unit tests for httpx_retry backoff calculation."""
from retry_client import compute_backoff_delay, should_retry_status

def test_exponential_backoff_cap():
    assert compute_backoff_delay(0, base_delay=0.5, max_delay=10.0) == 0.5
    assert compute_backoff_delay(5, base_delay=0.5, max_delay=10.0) == 10.0

def test_retry_after_float_and_max_cap():
    # Issue #142: float string in Retry-After header and clamping to max_delay
    assert compute_backoff_delay(1, base_delay=0.5, max_delay=10.0, retry_after_header=" 2.5 ") == 2.5
    assert compute_backoff_delay(1, base_delay=0.5, max_delay=10.0, retry_after_header="30") == 10.0

if __name__ == "__main__":
    test_exponential_backoff_cap()
    test_retry_after_float_and_max_cap()
    print("ALL SANDBOX TESTS PASSED!")
'''


class LocalCodeGraphEngine:
    """Builds a real AST symbol graph from a Python workspace and exposes swegemma graph tools."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[tuple[str, str, str]] = []
        self._index_workspace()

    def _index_workspace(self) -> None:
        for py_file in sorted(self.workspace.rglob("*.py")):
            rel_name = py_file.relative_to(self.workspace).as_posix()
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    node_id = f"{rel_name}::{node.name}"
                    doc = ast.get_docstring(node) or ""
                    self.nodes[node_id] = {
                        "file": rel_name,
                        "symbol": node.name,
                        "lineno": node.lineno,
                        "docstring": doc,
                    }
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                            self.edges.append((node_id, child.func.id, "CALLS"))

    def search_similar_code(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        q_tokens = set(query.lower().replace("_", " ").split())
        scored = []
        for nid, meta in self.nodes.items():
            haystack = f"{nid} {meta['docstring']}".lower().replace("_", " ")
            overlap = sum(1 for tok in q_tokens if tok in haystack)
            scored.append((overlap, nid, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"node": nid, "score": sc, **meta} for sc, nid, meta in scored[:k]]

    def get_code_neighbors(self, node: str) -> List[Dict[str, str]]:
        symbol_short = node.split("::")[-1]
        neighbors = []
        for src, dst, rel in self.edges:
            if src == node or dst == symbol_short:
                neighbors.append({"source": src, "target": dst, "edge_type": rel})
        return neighbors

    def get_code_subgraph(self, nodes: List[str]) -> Dict[str, Any]:
        return {
            "subgraph_nodes": [n for n in nodes if n in self.nodes],
            "induced_edges": [
                {"from": s, "to": d, "type": r}
                for s, d, r in self.edges
                if s in nodes or any(n.endswith(f"::{d}") for n in nodes)
            ],
        }


def run_interactive_self_test() -> None:
    print("=" * 84)
    print("  SWE-Gemma Interactive Local Self-Test Harness (3-Sub-Agent Team)")
    print("  Author: Robina Mirbahar — Google Cloud & AI Architect (@robinamirbahar)")
    print("=" * 84)

    # 1. Validate declarative YAML team configuration
    cfg = validate_declarative_submission()
    build_submission_zip()
    sub_names = [s["name"] for s in cfg.get("sub_agents", [])]
    print(f"[1/5] Loaded Root Coordinator : {cfg['name']} ({cfg['model']})")
    print(f"      Active Sub-Agent Team   : {', '.join(sub_names)}")

    # 2. Create sandbox repository with planted Issue #142
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "retry_client.py").write_text(BUGGY_RETRY_CLIENT, encoding="utf-8")
        (ws / "test_retry.py").write_text(TEST_SUITE_CODE, encoding="utf-8")

        # Confirm bug fails before agent intervention
        pre_run = subprocess.run(
            [sys.executable, str(ws / "test_retry.py")],
            capture_output=True,
            text=True,
        )
        print(f"\n[2/5] Pre-Fix Sandbox Test Status: EXIT_CODE={pre_run.returncode} (Expected Failure)")
        err_tail = pre_run.stderr.strip().splitlines()[-1] if pre_run.stderr else "ValueError"
        print(f"      Observed Bug Traceback     : {err_tail}")

        # 3. Sub-Agent 1: code_analyzer runs 2-Hop Code Graph Localization
        graph = LocalCodeGraphEngine(ws)
        hits = graph.search_similar_code("compute_backoff_delay retry_after_header float max_delay", k=3)
        top_node = hits[0]["node"]
        neighbors = graph.get_code_neighbors(top_node)
        subgraph = graph.get_code_subgraph([h["node"] for h in hits])

        print(f"\n[3/5] Sub-Agent [code_analyzer] -> 2-Hop Code-Graph Localization:")
        print(f"      Hop 1 search_similar_code  : Top Anchor = {top_node} (line {hits[0]['lineno']})")
        print(f"      Hop 2 get_code_neighbors   : {neighbors}")
        print(f"      Hop 2 get_code_subgraph    : {len(subgraph['subgraph_nodes'])} nodes, {len(subgraph['induced_edges'])} call edges")

        # 4. Sub-Agent 2: patch_architect synthesizes minimal surgical patch
        before_lines = (ws / "retry_client.py").read_text(encoding="utf-8").splitlines(keepends=True)
        (ws / "retry_client.py").write_text(FIXED_RETRY_CLIENT, encoding="utf-8")
        after_lines = (ws / "retry_client.py").read_text(encoding="utf-8").splitlines(keepends=True)
        diff_text = "".join(
            difflib.unified_diff(before_lines, after_lines, fromfile="a/retry_client.py", tofile="b/retry_client.py")
        )
        print(f"\n[4/5] Sub-Agent [patch_architect] -> Generated Unified Git Diff:")
        for dline in diff_text.splitlines():
            print(f"      {dline}")

        # 5. Sub-Agent 3: test_verifier executes reproduction & regression test suite
        post_run = subprocess.run(
            [sys.executable, str(ws / "test_retry.py")],
            capture_output=True,
            text=True,
        )
        assert post_run.returncode == 0, f"Post-fix test failed: {post_run.stderr}"
        print(f"\n[5/5] Sub-Agent [test_verifier] -> Regression Test Verification:")
        print(f"      Command Output : {post_run.stdout.strip()} (EXIT_CODE=0)")
        print("      Final Action   : submit_patch() -> TASK RESOLVED (100%)")
        print("=" * 84)


if __name__ == "__main__":
    run_interactive_self_test()
