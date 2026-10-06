from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_viewport_and_pwa_metadata_present():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in html
    assert 'width=device-width' in html
    assert 'initial-scale=1' in html
    assert 'rel="manifest"' in html
    assert 'apple-mobile-web-app-capable' in html


def test_responsive_breakpoints_cover_phone_tablet_and_desktop_drawer():
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1000px)" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 480px)" in css
    assert "@media (hover: none) and (pointer: coarse)" in css
    assert "min-height: 44px" in css
    assert "100dvh" in css
    assert "env(safe-area-inset-bottom)" in css


def test_wide_tables_scroll_instead_of_breaking_mobile_layout():
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".table-wrap, .data-table-wrap" in css
    assert "overflow-x: auto" in css
    assert "-webkit-overflow-scrolling: touch" in css


def test_mobile_drawer_contract_is_wired():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="menu-toggle"' in html
    assert 'id="sidebar-close"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'aria-controls="sidebar"' in html
    assert 'window.matchMedia("(max-width: 1000px)")' in html


def test_reduced_motion_is_supported():
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_mobile_routes_disable_blur_prone_compositor_effects():
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "Mobile rendering stability"
    assert marker in css
    mobile = css[css.index(marker):]
    assert "-webkit-backdrop-filter: none !important" in mobile
    assert "backdrop-filter: none !important" in mobile
    assert "animation: none !important" in mobile
    assert "filter: none !important" in mobile
    assert ".drawer-backdrop" in mobile
