from unittest.mock import patch

from app.models.ga4_connection import Ga4Connection


def test_report_returns_sorted_daily_sessions_and_keeps_summary_separate(
    client, admin_token, client_org, db
):
    connection = Ga4Connection(
        org_id=client_org.id,
        property_id="123456",
        property_name="Example Property",
        refresh_token="refresh-token",
        access_token="access-token",
    )
    db.add(connection)
    db.commit()

    summary_response = {
        "rows": [{
            "metricValues": [
                {"value": "12"},
                {"value": "8"},
                {"value": "0.625"},
                {"value": "91.2"},
            ]
        }]
    }
    daily_response = {
        "rows": [
            {
                "dimensionValues": [{"value": "20260703"}],
                "metricValues": [{"value": "7"}],
            },
            {
                "dimensionValues": [{"value": "20260701"}],
                "metricValues": [{"value": "0"}],
            },
            {
                "dimensionValues": [{"value": "20260702"}],
                "metricValues": [{"value": "5"}],
            },
        ]
    }

    with patch("app.services.ga4.get_valid_token", return_value="token"), patch(
        "app.services.ga4.run_report",
        side_effect=[summary_response, daily_response],
    ) as run_report:
        response = client.get(
            f"/api/seo/ga4/report?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "sessions": 12,
        "users": 8,
        "engagementRate": 62.5,
        "avgSessionDuration": 91.2,
    }
    assert payload["trend"] == [
        {"date": "2026-07-01", "value": 0},
        {"date": "2026-07-02", "value": 5},
        {"date": "2026-07-03", "value": 7},
    ]

    daily_payload = run_report.call_args_list[1].args[2]
    assert daily_payload["dateRanges"] == [{
        "startDate": "29daysAgo",
        "endDate": "today",
    }]
    assert daily_payload["dimensions"] == [{"name": "date"}]
    assert daily_payload["metrics"] == [{"name": "sessions"}]
    assert daily_payload["orderBys"] == [{
        "dimension": {"dimensionName": "date"},
        "desc": False,
    }]


def test_report_returns_empty_trend_without_fallback_data(
    client, admin_token, client_org, db
):
    connection = Ga4Connection(
        org_id=client_org.id,
        property_id="123456",
        refresh_token="refresh-token",
        access_token="access-token",
    )
    db.add(connection)
    db.commit()

    with patch("app.services.ga4.get_valid_token", return_value="token"), patch(
        "app.services.ga4.run_report",
        side_effect=[{}, {}],
    ):
        response = client.get(
            f"/api/seo/ga4/report?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.json()["trend"] == []
    assert response.json()["summary"]["sessions"] == 0

def test_staff_defaults_to_assigned_org(
    client, staff_token, staff_assignment, client_org, db
):
    db.add(
        Ga4Connection(
            org_id=client_org.id,
            property_id="staff-property",
            refresh_token="refresh-token",
        )
    )
    db.commit()

    response = client.get(
        "/api/seo/ga4/status",
        headers={"Authorization": f"Bearer {staff_token}"},
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["property_id"] == "staff-property"


def test_staff_cannot_select_unassigned_org(
    client, staff_token, staff_assignment, second_client_org
):
    response = client.get(
        f"/api/seo/ga4/status?org_id={second_client_org.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )

    assert response.status_code == 404


def test_select_property_validates_provider_property(client, admin_token, client_org, db):
    connection = Ga4Connection(
        org_id=client_org.id,
        refresh_token="refresh-token",
        access_token="access-token",
    )
    db.add(connection)
    db.commit()

    with patch("app.services.ga4.get_valid_token", return_value="token"), patch(
        "app.services.ga4.list_properties",
        return_value=[{"property": "properties/123456", "displayName": "Production GA4"}],
    ):
        response = client.post(
            f"/api/seo/ga4/property?org_id={client_org.id}",
            json={"property_id": "123456", "property_name": "Untrusted name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "property_id": "123456",
        "property_name": "Production GA4",
    }


def test_callback_records_connecting_user(client, admin_user, client_org, db):
    from app.core.redis_client import redis_client
    from app.services.seo_security import new_oauth_state

    state, payload = new_oauth_state("ga4", admin_user.id, client_org.id)
    redis_client.setex(f"ga4:state:{state}", 600, payload)
    tokens = {
        "refresh_token": "refresh-token",
        "access_token": "access-token",
        "expires_in": 3600,
    }

    with patch("app.services.ga4.exchange_code", return_value=tokens), patch(
        "app.services.ga4.list_properties",
        return_value=[{"property": "properties/123", "displayName": "Example"}],
    ):
        response = client.get(
            f"/api/seo/ga4/callback?code=test-code&state={state}",
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    connection = (
        db.query(Ga4Connection)
        .filter(Ga4Connection.org_id == client_org.id)
        .one()
    )
    assert connection.connected_by == admin_user.id

