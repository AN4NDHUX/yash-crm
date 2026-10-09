from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tier0_backend_is_layered():
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    required = [
        ROOT / "app" / "models.py",
        ROOT / "app" / "schemas.py",
        ROOT / "app" / "database.py",
        ROOT / "app" / "services" / "core.py",
        ROOT / "app" / "services" / "security.py",
    ]
    assert all(path.is_file() for path in required)
    assert "class Base(DeclarativeBase)" not in main
    assert "class Lead(TimestampMixin, Base)" not in main
    assert "class RecordPayload(BaseModel)" not in main
    assert "from app.models import *" in main
    assert "from app.schemas import *" in main
    assert "from app.services.core import *" in main
    assert "from app.services.security import *" in main
    assert len(main.encode("utf-8")) < 320_000


def test_tier0_frontend_is_layered():
    app_js = ROOT / "static" / "js" / "app.js"
    required = [
        ROOT / "static" / "js" / "core" / "http.js",
        ROOT / "static" / "js" / "core" / "runtime.js",
        ROOT / "static" / "js" / "features" / "pricing.js",
        ROOT / "static" / "js" / "features" / "modules.js",
        ROOT / "static" / "js" / "features" / "setup.js",
        ROOT / "static" / "js" / "features" / "ai.js",
    ]
    assert all(path.is_file() for path in required)
    source = app_js.read_text(encoding="utf-8")
    assert 'from "./core/runtime.js"' in source
    assert 'from "./features/setup.js"' in source
    assert 'from "./features/ai.js"' in source
    assert len(source.encode("utf-8")) < 160_000


def test_tier0_css_is_layered_entrypoint():
    app_css = ROOT / "static" / "css" / "app.css"
    source = app_css.read_text(encoding="utf-8")
    imports = [
        '@import url("./foundation.css");',
        '@import url("./workspace.css");',
        '@import url("./motion.css");',
        '@import url("./modules.css");',
        '@import url("./components.css");',
        '@import url("./spacing.css");',
    ]
    assert source.splitlines() == imports
    for name in ["foundation.css", "workspace.css", "motion.css", "modules.css", "components.css", "spacing.css"]:
        path = ROOT / "static" / "css" / name
        assert path.is_file()
        assert path.stat().st_size > 0
