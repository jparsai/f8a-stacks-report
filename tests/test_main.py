"""Tests for main module."""

from f8a_report.main import time_to_generate_monthly_report, main
from unittest import mock
import os
from freezegun import freeze_time
import datetime
from f8a_report.report_helper import ReportHelper


class TodayMockClass:
    """Mock class for `today` from datetime module."""

    def __init__(self, day):
        """Construct the class and initialize day attribute."""
        self.day = day


class MockReportHelper(ReportHelper):
    """Mock Report Helper."""

    @staticmethod
    def get_report(*args, **kwargs):
        """Mock Get Report."""
        return args, kwargs

    @staticmethod
    def re_train(*args, **kwargs):
        """Mock re-train."""
        return args, kwargs

    @staticmethod
    def cleanup_db_tables(*args, **kwargs):
        """Mock cleanup_db_tables."""
        return args, kwargs

    @staticmethod
    def retrieve_stack_analyses_content(*args, **kwargs):
        """Mock retrieve_stack_analyses_content."""
        return True, args, kwargs


def test_time_to_generate_monthly_report():
    """Test the function time_to_generate_monthly_report."""
    today = TodayMockClass(1)
    assert time_to_generate_monthly_report(today) is True

    today = TodayMockClass(30)
    assert time_to_generate_monthly_report(today) is False


@mock.patch('f8a_report.main.StackReportBuilder.get_report')
@mock.patch('f8a_report.main.ReportHelper.get_report', return_value=[{}, True, {}])
@mock.patch('f8a_report.main.ReportHelper.re_train', return_value=True)
@mock.patch('f8a_report.main.ReportHelper.retrieve_stack_analyses_content', return_value=True)
@mock.patch('f8a_report.main.manifest_interface', return_value=True)
def test_main(_mock1, _mock2, _mock3, _mock4, _mock5):
    """Test the function main."""
    _mock5.return_value = ("response_v2", "ingestion_results_v2")
    resp = main()
    assert (isinstance(resp, dict))


@mock.patch('f8a_report.main.StackReportBuilder.get_report')
@mock.patch('f8a_report.main.ReportHelper', return_value=MockReportHelper)
@mock.patch('f8a_report.main.manifest_interface', return_value=True)
@freeze_time("2020-04-06")
def test_environment(_mock1, _mock2, _mock3):
    """Test the Weekday 0, Monday and GENERATE_MANIFESTS functionality."""
    _mock3.return_value = ("response_v2", "ingestion_results_v2")
    resp = main()
    assert datetime.datetime.today().weekday() == 0
    assert (isinstance(resp, dict))
    assert _mock2().retrieve_stack_analyses_content()[0] is True
    assert os.environ.get('GENERATE_MANIFESTS') in ['True', 'False']
