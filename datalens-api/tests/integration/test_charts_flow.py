import os

import httpx
import pytest

pytestmark = pytest.mark.integration

BASE = os.environ.get("DATALENS_API_BASE", "http://127.0.0.1:8393")
TOKEN = os.environ["DL_API_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "x-dl-api-version": "2",
    "Content-Type": "application/json",
}

MIN_DATA = {
    "counter": 1,
    "salt": "itest-salt",
    "schemeVersion": 8,
    "tabs": [
        {
            "id": "t1",
            "title": "Tab",
            "items": [],
            "layout": [],
            "connections": [],
            "aliases": {},
        }
    ],
    "settings": {
        "silentLoading": False,
        "dependentSelectors": False,
        "expandTOC": False,
        "autoupdateInterval": None,
        "maxConcurrentRequests": None,
    },
}


def _rpc(client: httpx.Client, method: str, payload: dict) -> httpx.Response:
    return client.post(f"/rpc/{method}", headers=HEADERS, json=payload)


def test_dashboard_wizard_crud_roundtrip():
    workbook_id = None
    dashboard_id = None
    chart_id = None
    table_id = None
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        try:
            created_wb = _rpc(client, "createWorkbook", {"title": "itest-charts"})
            assert created_wb.status_code == 200, created_wb.text
            workbook_id = created_wb.json()["workbookId"]

            created_dash = _rpc(
                client,
                "createDashboard",
                {
                    "entry": {
                        "workbookId": workbook_id,
                        "name": "itest-dash",
                        "data": MIN_DATA,
                    }
                },
            )
            assert created_dash.status_code == 200, created_dash.text
            dashboard_id = created_dash.json()["entry"]["entryId"]
            assert dashboard_id
            assert created_dash.json()["entry"]["type"] == ""
            assert created_dash.json()["entry"]["data"]["schemeVersion"] == 8

            got_dash = _rpc(client, "getDashboard", {"dashboardId": dashboard_id})
            assert got_dash.status_code == 200, got_dash.text
            assert got_dash.json()["entry"]["entryId"] == dashboard_id

            created_chart = _rpc(
                client,
                "createWizardChart",
                {
                    "workbookId": workbook_id,
                    "name": "itest-wizard",
                    "template": "datalens",
                    "data": {"shared": {"title": "itest-wizard"}},
                },
            )
            assert created_chart.status_code == 200, created_chart.text
            chart_id = created_chart.json()["entryId"]
            assert chart_id
            assert created_chart.json()["type"] == "graph_wizard_node"

            got_chart = _rpc(client, "getWizardChart", {"chartId": chart_id})
            assert got_chart.status_code == 200, got_chart.text
            assert got_chart.json()["entryId"] == chart_id

            created_table = _rpc(
                client,
                "createWizardChart",
                {
                    "workbookId": workbook_id,
                    "name": "itest-wizard-table",
                    "template": "datalens",
                    "data": {
                        "shared": {
                            "title": "itest-wizard-table",
                            "visualization": {"id": "flatTable"},
                        }
                    },
                },
            )
            assert created_table.status_code == 200, created_table.text
            table_id = created_table.json()["entryId"]
            assert table_id
            assert created_table.json()["type"] == "table_wizard_node"
            got_table = _rpc(client, "getWizardChart", {"chartId": table_id})
            assert got_table.status_code == 200, got_table.text
            assert got_table.json()["type"] == "table_wizard_node"
            deleted_table = _rpc(client, "deleteWizardChart", {"chartId": table_id})
            assert deleted_table.status_code == 200, deleted_table.text
            table_id = None

            deleted_chart = _rpc(client, "deleteWizardChart", {"chartId": chart_id})
            assert deleted_chart.status_code == 200, deleted_chart.text
            assert deleted_chart.json() == {}
            chart_id = None

            deleted_dash = _rpc(
                client, "deleteDashboard", {"dashboardId": dashboard_id}
            )
            assert deleted_dash.status_code == 200, deleted_dash.text
            assert deleted_dash.json() == {}
            dashboard_id = None

            deleted_wb = _rpc(client, "deleteWorkbook", {"workbookId": workbook_id})
            assert deleted_wb.status_code == 200, deleted_wb.text
            workbook_id = None
        finally:
            if table_id:
                _rpc(client, "deleteWizardChart", {"chartId": table_id})
            if chart_id:
                _rpc(client, "deleteWizardChart", {"chartId": chart_id})
            if dashboard_id:
                _rpc(client, "deleteDashboard", {"dashboardId": dashboard_id})
            if workbook_id:
                _rpc(client, "deleteWorkbook", {"workbookId": workbook_id})
