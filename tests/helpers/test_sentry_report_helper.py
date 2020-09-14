"""Tests for classes from sentry_report_helper module."""

from f8a_report.helpers.sentry_report_helper import SentryReportHelper
import responses

sobj = SentryReportHelper()

sentry_issues_res = [{
    "lastSeen": "2019-05-15T06:50:10Z",
    "id": "12666",
    "metadata": {
        "type": "TypeError",
        "value": "must be str, not list"
    }
}]

sentry_tags_res = {
    "eventID": "7d61317b877d405abce221ef73bd11ed",
    "message": "import_epv() failed with error: must be str, not list",
    "id": "723486",
    "type": "error",
    "metadata": {
        "type": "TypeError",
        "value": "must be str, not list"
    },
    "tags": [
        {
            "value": "bayesian-data-importer-52-fgp4f",
            "key": "server_name"
        }
    ],
    "entries": [
        {
            "type": "message",
            "data": {
                "message": "import_epv() failed with error: must be str, not list"
            }
        },
        {
            "type": "exception",
            "data": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "function": "import_epv_http",
                                    "lineNo": 228,
                                    "filename": "/src/data_importer.py",
                                    "context": [
                                        [
                                            228,
                                            " report = _import_keys_from_s3_http()"
                                        ]
                                    ]
                                }
                            ]
                        },
                    }
                ],
            }
        }
    ]
}

sentry_tags_res_nostack = {
    "eventID": "7d61317b877d405abce221ef73bd11ed",
    "message": "import_epv() failed with error: must be str, not list",
    "id": "723486",
    "type": "error",
    "metadata": {
        "type": "TypeError",
        "value": "must be str, not list"
    },
    "tags": [
        {
            "value": "bayesian-data-importer-52-fgp4f",
            "key": "server_name"
        }
    ],
    "entries": [
        {
            "type": "message",
            "data": {
                "message": "import_epv() failed with error: must be str, not list"
            }
        },
        {
            "type": "breadcrumbs"
        }
    ]
}


@responses.activate
def test_retrieve_sentry_logs_success():
    """Test retrieve sentry logs."""
    responses.add(responses.GET, 'https://sentry.devshift.net/api/0/projects/'
                                 'sentry/fabric8-analytics-production/issues/'
                                 '?statsPeriod=24h', json=sentry_issues_res, status=200)
    responses.add(responses.GET, 'https://sentry.devshift.net/api/0/issues/'
                                 '12666/events/latest/', json=sentry_tags_res, status=200)
    res = sobj.retrieve_sentry_logs('2019-05-14', '2019-05-15')
    expected_output = {"error_report": {"bayesian-data-importer":
                                        {"total_errors": 1, "errors":
                                            [{"id": "12666", "last_seen":
                                                "2019-05-15T06:50:10Z",
                                                "bayesian-data-importer-52-fgp4f":
                                                    "TypeError: must be str, not list",
                                                "stacktrace": "File /src/data_importer.py,"
                                                " Line 228, Function import_epv_http, "
                                                "Statement  report = _import_keys_from_s3_http()"
                                                              " || "}]}}}
    assert (res == expected_output)


def test_retrieve_sentry_logs_failure():
    """Test retrieve sentry logs."""
    res = sobj.retrieve_sentry_logs('2019-05-14', '2019-05-15')
    assert (res == {})


@responses.activate
def test_retrieve_sentry_logs_nostacktrace():
    """Test retrieve sentry logs."""
    responses.add(responses.GET, 'https://sentry.devshift.net/api/0/projects/'
                                 'sentry/fabric8-analytics-production/issues/'
                                 '?statsPeriod=24h',
                  json=sentry_issues_res, status=200)
    responses.add(responses.GET, 'https://sentry.devshift.net/api/0/issues/'
                                 '12666/events/latest/', json=sentry_tags_res_nostack, status=200)
    res = sobj.retrieve_sentry_logs('2019-05-14', '2019-05-15')
    expected_output = {"error_report": {"bayesian-data-importer":
                                        {"total_errors": 1, "errors":
                                            [{"id": "12666", "last_seen":
                                                "2019-05-15T06:50:10Z",
                                                "bayesian-data-importer-52-fgp4f":
                                                    "TypeError: must be str, not list",
                                                "stacktrace": "Not Available"}]}}}
    assert (res == expected_output)
