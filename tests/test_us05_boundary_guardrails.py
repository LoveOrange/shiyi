import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DEFAULT_DEPENDENCIES = frozenset(
    {
        "browser-cookie3",
        "chromadb",
        "google-auth-oauthlib",
        "keyring",
        "langchain",
        "llama-index",
        "numpy",
        "openai",
        "pandas",
        "playwright",
        "pyppeteer",
        "selenium",
        "torch",
        "transformers",
        "undetected-chromedriver",
    }
)
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "browser_cookie3",
        "chromadb",
        "google_auth_oauthlib",
        "keyring",
        "langchain",
        "llama_index",
        "numpy",
        "openai",
        "pandas",
        "playwright",
        "pyppeteer",
        "selenium",
        "torch",
        "transformers",
        "undetected_chromedriver",
    }
)


def test_default_install_has_no_credential_browser_or_heavy_optional_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dependencies = {_canonical_package_name(spec) for spec in pyproject["project"]["dependencies"]}

    assert dependencies.isdisjoint(FORBIDDEN_DEFAULT_DEPENDENCIES)


def test_default_shiyi_import_graph_avoids_browser_credential_runtime_packages() -> None:
    imported_roots: set[str] = set()
    for path in (ROOT / "src" / "shiyi").rglob("*.py"):
        imported_roots.update(_import_roots(path))

    assert imported_roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS)


def _canonical_package_name(spec: str) -> str:
    name = []
    for char in spec:
        if char.isalnum() or char in "-_.":
            name.append(char)
        else:
            break
    return "".join(name).lower().replace("_", "-")


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots
