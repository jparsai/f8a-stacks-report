"""Tests for classes from cve_report_helper module."""
import pytest
import json
from unittest import mock
from f8a_report.helpers.cve_helper import CVE
from datetime import datetime as dt
from requests.exceptions import Timeout

cve = CVE()
cve_stats = {"github_stats": {"open_count": {}}}


with open('tests/data/github_data.json', 'r') as f:
    github_api_response = json.load(f)


def mock_github_get(*_args, **_kwargs):
    """Mock the call to the insights service."""
    class MockResponse:
        """Mock response object."""

        def __init__(self, json_data, status_code):
            """Create a mock json response."""
            self.json_data = json_data
            self.status_code = status_code
            self.headers = {'X-RateLimit-Remaining': 3, 'X - RateLimit - Reset': 5}

        def json(self):
            """Get the mock json response."""
            return self.json_data

    return MockResponse(github_api_response, 200)


def mock_graph_post_error(*_args, **_kwargs):
    """Mock the call to the insights service."""
    class MockResponse:
        """Mock response object."""

        def __init__(self, json_data, status_code):
            """Create a mock json response."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Get the mock json response."""
            return self.json_data

    with open('tests/data/graph_cve_data.json', 'r') as f:
        graph_cve_response = json.loads(f.read())

    return MockResponse(graph_cve_response, 500)


def mock_graph_post(*_args, **_kwargs):
    """Mock the call to the insights service."""
    class MockResponse:
        """Mock response object."""

        def __init__(self, json_data, status_code):
            """Create a mock json response."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Get the mock json response."""
            return self.json_data

    with open('tests/data/graph_cve_data.json', 'r') as f:
        graph_cve_response = json.loads(f.read())

    return MockResponse(graph_cve_response, 200)


@mock.patch('f8a_report.helpers.cve_helper.CVE.call_github_api')
def test_get_cveids_from_cvedb_prs(_mock1):
    """Test get CVEs from CVEDB PRs."""
    _mock1.side_effect = [github_api_response, ValueError]
    cve_prs = cve.get_cveids_from_cvedb_prs(updated_on=dt.today().strftime('%Y-%m-%d'))
    assert cve_prs is not None
    assert len(cve_prs) == 1

    with pytest.raises(ValueError):
        cve_prs = cve.get_cveids_from_cvedb_prs(updated_on=dt.today().strftime('%Y-%m-%d'))
        assert cve_prs is None


@mock.patch('requests.Session.post')
def test_validate_cveids_in_graph(_mock1):
    """Test valid and invalid graph responses."""
    # Test a valid use-case
    _mock1.side_effect = mock_graph_post
    ingested, missed = cve.validate_cveids_in_graph(cve_ids=['CVE-2017-1000116'])
    assert len(missed) == 0
    assert ingested is not None
    assert len(ingested) == 1

    # Test an invalid status-code 500 use-case
    _mock1.side_effect = mock_graph_post_error
    ingested, missed = cve.validate_cveids_in_graph(cve_ids=['CVE-2017-1000116'])
    assert len(missed) == 0
    assert len(ingested) == 0

    # Test a requests timeout use-case
    _mock1.side_effect = Timeout
    ingested, missed = cve.validate_cveids_in_graph(cve_ids=['CVE-2017-1000116'])
    assert len(missed) == 0
    assert len(ingested) == 0


@mock.patch('f8a_report.helpers.cve_helper.CVE.call_github_api')
def test_get_fp_cves_count(_mock1):
    """Test fp CVEs count."""
    _mock1.side_effect = [github_api_response, ValueError]

    fp_cves_count = cve.get_fp_cves_count(updated_on=dt.today().strftime('%Y-%m-%d'))
    assert fp_cves_count == 1

    with pytest.raises(ValueError):
        fp_cves_count = cve.get_fp_cves_count(updated_on=dt.today().strftime('%Y-%m-%d'))
        assert fp_cves_count is None


@mock.patch('requests.get')
def test_call_github_api(_mock1):
    """Test call github api."""
    # Test valid response from github
    _mock1.side_effect = mock_github_get
    gh_resp = cve.call_github_api('')
    assert gh_resp is not None

    # Tests a requests timeout exception
    _mock1.side_effect = Timeout
    with pytest.raises(ValueError):
        cve.call_github_api('')


@mock.patch('f8a_report.helpers.cve_helper.CVE.call_github_api')
def test_get_open_cves_count(_mock1):
    """Test open CVEs count."""
    # Test a valid test case
    _mock1.return_value = github_api_response
    cve_stat = cve.get_open_cves_count(updated_on=dt.today().strftime('%Y-%m-%d'))
    assert cve_stat is not None


@mock.patch('f8a_report.helpers.cve_helper.CVE.get_open_cves_count', return_value=cve_stats)
@mock.patch('f8a_report.helpers.cve_helper.CVE.get_fp_cves_count', return_value=2)
@mock.patch('f8a_report.helpers.cve_helper.CVE.get_cveids_from_cvedb_prs', return_value=[
    'CVE-2017-1000116'])
@mock.patch('f8a_report.helpers.cve_helper.CVE.validate_cveids_in_graph', return_value=(1, 0))
def test_generate_cve_report(_mock1, _mock2, _mock3, _mock4):
    """Test CVE generat report."""
    cve_report = cve.generate_cve_report(dt.today().strftime('%Y-%m-%d'))
    assert cve_report is not None
