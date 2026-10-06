from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_query_selector_single_is_never_used_as_collection():
    bad = []
    for number, line in enumerate(APP_JS.splitlines(), start=1):
        if re.search(r"(?<!\$)\$\([^;\n]*?\)\.(forEach|map|filter|some|every|reduce)\(", line):
            bad.append((number, line.strip()))
    assert bad == [], f"Single-element $() used as a collection: {bad[:20]}"


def test_every_sidebar_route_has_a_frontend_handler():
    routes = sorted(set(re.findall(r'data-route="([^"]+)"', INDEX)))
    core_block = APP_JS[APP_JS.index("const MODULES = {"):APP_JS.index("function badge")]
    core = set(re.findall(r"^\s{2}([a-z_]+):\s*\{", core_block, flags=re.MULTILINE))
    platform_match = re.search(r"const PLATFORM_MODULE_ROUTES = \[(.*?)\];", APP_JS, flags=re.DOTALL)
    platform = set(re.findall(r'"([^"]+)"', platform_match.group(1))) if platform_match else set()
    special = {
        "dashboard", "teamspaces", "activities", "ai", "developer", "security",
        "cpq", "setup-console", "setup", "settings", "reports", "dashboards",
    }
    missing = [route for route in routes if route not in core | platform | special]
    assert missing == [], f"Sidebar routes without renderRoute handling: {missing}"


def test_critical_navigation_runtime_contracts_exist():
    required = [
        "async function navigate(",
        "async function renderRoute()",
        "window.addEventListener(\"popstate\", renderRoute)",
        "document.addEventListener(\"click\"",
        "if (MODULES[parts[0]])",
        "if (PLATFORM_MODULE_ROUTES.includes(parts[0]))",
        "if (parts[0] === \"activities\"",
        "if (parts[0] === \"setup\"",
    ]
    missing = [item for item in required if item not in APP_JS]
    assert missing == []
