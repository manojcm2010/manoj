# tests/test_app.py

from app import app
from unittest.mock import patch

def test_home():
    client = app.test_client()

    with patch("app.fetch_projects") as mock_projects:
        mock_projects.return_value = []

        response = client.get("/")
        assert response.status_code == 200