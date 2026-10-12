"""OpenAPI schema covers every endpoint."""

import pytest
import yaml
from django.test import Client


@pytest.mark.django_db
def test_schema_and_swagger_ui_serve():
    c = Client()
    assert c.get("/api/docs/").status_code == 200
    assert c.get("/api/redoc/").status_code == 200
    schema = yaml.safe_load(c.get("/api/schema/").content.decode())
    paths = schema["paths"]
    for expected in (
        "/api/trips/plan/",
        "/api/geocode/autocomplete/",
        "/api/forecast/corridor/",
        "/api/health/",
    ):
        assert expected in paths, f"missing in schema: {expected}"
    # trip-plan POST documents the request body
    post = paths["/api/trips/plan/"]["post"]
    assert "origin" in str(post)
    assert schema["info"]["title"].startswith("Weather-Aware")
