"""Tests for classes from unknown_deps_report_helper module."""

from f8a_report.unknown_deps_report_helper import UnknownDepsReportHelper
from unittest import mock

uobj = UnknownDepsReportHelper()

past_unknown_deps = {'npm': [{"name": "lodash", "version": "2.40.1"},
                             {"name": "serve-static", "version": "1.7.1"}]}
ingested_epv = {'ingested_dependencies': 1,
                'report': {
                    'lodash 2.40.1': 'Unknown',
                    'serve-static 1.7.1': 'Ingested'
                },
                'total_previously_unknown_dependencies': 2}

result = {
    "stacks_summary": {
        "npm": {
            "unique_unknown_dependencies_with_frequency": {
                "lodash 2.1": 1,
                "blblh": 2

            }
        }

    }
}


def test_get_unknown_list():
    """Test the get_unknown_list function."""
    lst = uobj.get_unknown_list(result)
    assert len(lst['npm']) == 1


@mock.patch('f8a_report.unknown_deps_report_helper.UnknownDepsReportHelper.get_past_unknown_deps',
            return_value=past_unknown_deps)
@mock.patch('f8a_report.unknown_deps_report_helper.find_ingested_epv', return_value=ingested_epv)
def test_get_current_ingestion_status(_mock1, _mock2):
    """Test result collation success scenario."""
    result = uobj.get_current_ingestion_status()

    assert result['npm']['total_previously_unknown_dependencies'] == 2
    assert result['npm']['ingested_dependencies'] == 1
    assert result['npm']['report']['lodash 2.40.1'] == 'Unknown'
    assert result['npm']['report']['serve-static 1.7.1'] == 'Ingested'
