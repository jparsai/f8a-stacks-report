"""Test module for classes and functions found in the report_generator module."""

from f8a_report.helpers.graph_report_generator import execute_gremlin_dsl, \
    generate_report_for_unknown_epvs, generate_report_for_latest_version, \
    generate_report_for_cves, find_ingested_epv, rectify_latest_version
from unittest import mock
from datetime import date


def mock_post_with_payload_check(*_args, **kwargs):
    """Mock the call to the Gremlin service."""
    class MockResponse:
        """Mock response object."""

        def __init__(self, json_data, status_code):
            """Create a mock json response."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Get the mock json response."""
            return self.json_data
    # return the empty payload send to the mocked service
    resp = kwargs["json"]
    return MockResponse(resp, 200)


def mock_response():
    """Generate data for mock response."""
    x = {
        "result": {
            "data": [
                {
                    "pecosystem": ["maven"],
                    "pname": ["io.vertx:vertx-web"],
                    "version": ["3.6.3"]
                }
            ]
        }

    }
    return x


def mock_response1():
    """Generate data for mock1 response."""
    x = {
        "result": {
            "data": [
                {
                    "ecosystem": ["maven"],
                    "name": ["io.vertx:vertx-web"],
                    "latest_version": ["3.6.3"],
                    "latest_version_last_updated": ["19470815"]
                },
                {
                    "ecosystem": ["npm"],
                    "name": ["lodash"],
                    "latest_version": ["2.39.2"]
                },
                {
                    "ecosystem": ["npm"],
                    "name": ["test-hooks"],
                    "latest_version": ["1.1.1"],
                    "latest_version_last_updated": ["19470814"]
                }
            ]
        }

    }
    return x


def mock_response2():
    """Generate data for mock2 response."""
    x = {
        "result": {
            "data": [
                {
                    "a": {
                        "cve_id": [
                            "CVE-2013-4310"
                        ]
                    },
                    "b": {
                        "pname": [
                            "org.apache.struts:struts2-core"
                        ],
                        "version": [
                            "2.0.5"
                        ]
                    }
                },
                {
                    "a": {
                        "cve_id": [
                            "CVE-2013-4310"
                        ]
                    },
                    "b": {
                        "pname": [
                            "org.apache.struts:struts2-core"
                        ],
                        "version": [
                            "2.0.7"
                        ]
                    }
                }
            ]
        }

    }
    return x


def mock_response3():
    """Generate data for mock response."""
    x = {
        "result": {
            "data": [
                {
                    "pname": ["serve-static"],
                    "pecosystem": ["npm"],
                    "version": ["1.7.1"]
                }
            ]
        }

    }
    return x


@mock.patch("f8a_report.helpers.graph_report_generator.execute_gremlin_dsl")
def test_generate_report_for_unknown_epvs(mocker):
    """Test generate_report_for_unknown_epvs function."""
    mocker.return_value = mock_response()
    epv_list = [{
                    "ecosystem": "maven",
                    "name": "io.vertx:vertx-web",
                    "version": "3.6.3"
                },
                {
                    "ecosystem": "npm",
                    "name": "lodash",
                    "version": "2.40.1"
                }]
    out = generate_report_for_unknown_epvs(epv_list)
    assert out['maven@DELIM@io.vertx:vertx-web@DELIM@3.6.3'] == "true"
    assert out['npm@DELIM@lodash@DELIM@2.40.1'] == "false"


@mock.patch("f8a_report.helpers.graph_report_generator.execute_gremlin_dsl")
def test_generate_report_for_latest_version(mocker):
    """Test generate_report_for_latest_version function."""
    mocker.return_value = mock_response1()
    epv_list = [{
                    "ecosystem": "maven",
                    "name": "io.vertx:vertx-web"
                },
                {
                    "ecosystem": "npm",
                    "name": "lodash"
                },
                {
                    "ecosystem": "npm",
                    "name": "test-hooks"
                }]
    out = generate_report_for_latest_version(epv_list, date(1947, 8, 15))
    assert out['maven@DELIM@io.vertx:vertx-web']['known_latest_version'] == "3.6.3"
    assert out['npm@DELIM@lodash']['known_latest_version'] == "2.39.2"
    assert out['maven@DELIM@io.vertx:vertx-web']['actual_latest_version'] == "3.6.3"
    assert out['npm@DELIM@lodash']['actual_latest_version'] is not None
    assert out['npm@DELIM@lodash']['actual_latest_version'] != "2.39.2"
    assert out['npm@DELIM@test-hooks']['actual_latest_version'] == "1.1.1"


@mock.patch("f8a_report.helpers.graph_report_generator.execute_gremlin_dsl")
def test_generate_report_for_cves(mocker):
    """Test generate_report_for_cves function."""
    mocker.return_value = mock_response2()
    cve_data = {
        "CVE-2013-4310": {
            "ecosystem": "maven",
            "packages": [
                {
                    "name": "org.apache.struts:struts2-core",
                    "versions": ["2.0.5", "2.0.6"]
                }
            ]
        }
    }
    out = generate_report_for_cves(cve_data)
    assert out['CVE-2013-4310@DELIM@org.apache.struts:struts2-core@DELIM@2.0.5'] == \
        "Found"
    assert out['CVE-2013-4310@DELIM@org.apache.struts:struts2-core@DELIM@2.0.6'] == \
        "Not Found"
    assert out['CVE-2013-4310@DELIM@org.apache.struts:struts2-core@DELIM@2.0.7'] == \
        "False Positive"


@mock.patch('requests.Session.post', side_effect="")
def test_execute_gremlin_dsl(mocker):
    """Test the function execute_gremlin_dsl."""
    mocker.return_value = ""
    query_str = "g.V().has('ecosystem', eco).has('name',pkg).valueMap()"
    payload = {
        'gremlin': query_str,
        'bindings': {
            'eco': 'maven',
            'pkg': 'io.vertx:vertx-web'
        }
    }
    out = execute_gremlin_dsl(payload)
    assert out is None


@mock.patch("f8a_report.helpers.graph_report_generator.execute_gremlin_dsl")
def test_find_ingested_epv(mocker):
    """Test the function find_ingested_epv."""
    mocker.return_value = mock_response3()
    epv_list = [{
                    "name": "serve-static",
                    "version": "1.7.1"
                },
                {
                    "name": "lodash",
                    "version": "2.40.1"
                }]
    out = find_ingested_epv('npm', epv_list)

    assert out['total_previously_unknown_dependencies'] == 2
    assert out['ingested_dependencies'] == 1
    assert out['report']['lodash 2.40.1'] == 'Unknown'
    assert out['report']['serve-static 1.7.1'] == 'Ingested'


@mock.patch('requests.post', side_effect=mock_post_with_payload_check)
def test_rectify_latest_version(mocker):
    """Test the function rectify_latest_version."""
    mocker.return_value = ""
    lst = [
        {
            "package": "io.vertx:vertx-web",
            "actual_latest_version": "3.7.9"
        }
    ]
    resp = rectify_latest_version(lst, "maven")
    assert resp == "Success"


@mock.patch('requests.post', side_effect=mock_post_with_payload_check)
def test_rectify_latest_version2(mocker):
    """Test the function rectify_latest_version."""
    mocker.return_value = ""
    lst = {'express 4.0.0': 2, 'npm 6.2.0': 2, 'serve-static 1.7.1': 2}
    resp = rectify_latest_version(lst, "npm", True)
    assert resp == "Success"
