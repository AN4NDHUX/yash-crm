from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.platform_catalog import PLATFORM_RESOURCES, SETUP_NAVIGATION


def test_master_setup_groups_are_registered():
    required = {
        "General", "Security Control", "Channels", "Customization", "Automation",
        "Process Management", "Experience Center", "Data Administration", "Marketplace",
        "Developer Hub", "Apex", "CPQ",
    }
    assert required.issubset(SETUP_NAVIGATION)


def test_all_setup_links_resolve_to_real_resources_or_special_pages():
    special = {"users", "audit_log", "import", "import_history", "export", "recycle_bin", "duplicates", "approval_processes", "blueprints", "workflow_rules"}
    unresolved = []
    for group, links in SETUP_NAVIGATION.items():
        for resource, label in links:
            if resource not in PLATFORM_RESOURCES and resource not in special:
                unresolved.append((group, resource, label))
    assert unresolved == []


def test_master_feature_surfaces_exist():
    required = {
        "email_channels", "telephony", "business_messaging", "webforms", "portals",
        "wizards", "kiosk_builder", "page_designer", "home_customization", "translations",
        "cadences", "review_processes", "connected_workflows", "signals", "command_center",
        "segmentation", "data_backup", "storage", "sandboxes", "copy_customization",
        "data_quality", "migration", "marketplace_integrations", "oauth_clients", "api_usage",
        "circuits", "style_ui", "apex_agents", "apex_data_enrichment", "apex_prediction",
        "apex_recommendation", "apex_communication", "apex_vision", "apex_notifications",
        "apex_voc", "apex_models", "apex_presentation", "apex_studio", "apex_competitors",
    }
    assert required.issubset(PLATFORM_RESOURCES)
