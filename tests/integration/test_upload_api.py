"""
tests/integration/test_upload_api.py
FastAPI integration tests for file upload and schema endpoints.
Storage and schema ingestion are mocked.
"""

import io
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_upload_and_ingest(mocker):
    mocker.patch(
        "api.routers.upload.upload_file",
        return_value="https://test.supabase.co/storage/v1/object/public/user-uploads/uuid/test.csv",
    )
    mocker.patch("api.routers.upload.ingest_schema", return_value=1)


@pytest.mark.integration
class TestUploadEndpoint:
    def test_upload_csv_returns_200(self, api_client, mock_upload_and_ingest):
        csv_data = b"id,name,amount\n1,Alice,100\n2,Bob,200\n"
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("data.csv", io.BytesIO(csv_data), "text/csv")},
            data={"user_id": "test-user"},
        )
        assert resp.status_code == 200

    def test_upload_returns_connector_id(self, api_client, mock_upload_and_ingest):
        csv_data = b"id,name\n1,Alice\n"
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("data.csv", io.BytesIO(csv_data), "text/csv")},
            data={"user_id": "test-user"},
        )
        body = resp.json()
        assert "connector_id" in body
        assert body["connector_id"].startswith("csv:")

    def test_upload_returns_tables_ingested(self, api_client, mock_upload_and_ingest):
        csv_data = b"x,y\n1,2\n"
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("data.csv", io.BytesIO(csv_data), "text/csv")},
            data={"user_id": "test-user"},
        )
        assert resp.json()["tables_ingested"] == 1

    def test_unsupported_file_type_rejected(self, api_client):
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            data={"user_id": "test-user"},
        )
        assert resp.status_code == 415

    def test_sqlite_upload_accepted(self, api_client, mocker):
        mocker.patch(
            "api.routers.upload.upload_file",
            return_value="https://test.supabase.co/storage/v1/object/public/user-uploads/uuid/db.sqlite",
        )
        mocker.patch("api.routers.upload.ingest_schema", return_value=3)
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("db.sqlite", io.BytesIO(b"SQLite format 3\x00"), "application/x-sqlite3")},
            data={"user_id": "test-user"},
        )
        assert resp.status_code == 200
        assert resp.json()["file_type"] == "sqlite"

    def test_file_too_large_rejected(self, api_client):
        # 51 MB of zeros as a "csv"
        big = b"a,b\n" + b"1,2\n" * (13 * 1024 * 1024)  # ~52 MB
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
            data={"user_id": "test-user"},
        )
        assert resp.status_code == 413

    def test_extension_detection_for_csv(self, api_client, mock_upload_and_ingest):
        """CSV detected by .csv extension even with generic content-type."""
        csv_data = b"a,b\n1,2\n"
        resp = api_client.post(
            "/api/upload/file",
            files={"file": ("data.csv", io.BytesIO(csv_data), "application/octet-stream")},
            data={"user_id": "test-user"},
        )
        assert resp.status_code == 200
        assert resp.json()["file_type"] == "csv"


@pytest.mark.integration
class TestSchemaEndpoint:
    def test_get_schema_returns_tables(self, api_client, in_memory_sqlite_connector, mocker):
        mocker.patch("api.routers.schema.get_connector", return_value=in_memory_sqlite_connector)
        resp = api_client.get("/api/schema/csv:http://fake")
        assert resp.status_code == 200
        body = resp.json()
        assert "tables" in body
        assert len(body["tables"]) > 0

    def test_ingest_schema_endpoint(self, api_client, mocker):
        mocker.patch("api.routers.schema.ingest_schema", return_value=2)
        resp = api_client.post("/api/schema/ingest", json={"connector_id": "neon:public"})
        assert resp.status_code == 200
        assert resp.json()["tables_ingested"] == 2

    def test_invalid_connector_returns_400(self, api_client):
        resp = api_client.get("/api/schema/unknown:bad_connector")
        assert resp.status_code == 400
