"""Tests for classes from ingestion_helper module."""

import responses
from f8a_report.helpers.ingestion_helper import ingest_epv
import os

_APP_SECRET_KEY = os.getenv('APP_SECRET_KEY', 'not-set')
_INGESTION_API_URL = "http://{host}:{port}/{endpoint}".format(
    host=os.environ.get("INGESTION_SERVICE_HOST", "bayesian-jobs"),
    port=os.environ.get("INGESTION_SERVICE_PORT", "34000"),
    endpoint='ingestions/epv')

ingestion_resp = {
    "dispacher_ids":
        [
            "3ae8c79a-4dfb-49ee-b574-e147f1b5a95c",
            "95e342ff-ab5e-42a0-85c0-a22a72beb5a6"
        ],
    "message": "Allingestion flows are initiated"
}


@responses.activate
def test_ingest_epv():
    """Test retrieve sentry logs."""
    responses.add(
        responses.POST,
        _INGESTION_API_URL,
        json=ingestion_resp,
        status=201
    )

    res = ingest_epv({})

    assert (res.status_code == 201)
    assert (res.json() == ingestion_resp)
