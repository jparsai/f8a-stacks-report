"""Tests for main module."""

from f8a_report.stack_report_main import main
from unittest import mock
from freezegun import freeze_time
import datetime
from helpers.report_helper import ReportHelper


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


@mock.patch('f8a_report.stack_report_main.StackReportBuilder.get_report')
@mock.patch('f8a_report.stack_report_main.ReportHelper.get_report', return_value=[{}, True, {}])
def test_main(_mock1, _mock2):
    """Test the function main."""
    resp = main()
    assert (isinstance(resp, dict))


@mock.patch('f8a_report.stack_report_main.StackReportBuilder.get_report')
@mock.patch('f8a_report.stack_report_main.ReportHelper', return_value=MockReportHelper)
@freeze_time("2020-04-06")
def test_environment(_mock1, _mock2):
    """Test the Weekday 0, Monday and GENERATE_MANIFESTS functionality."""
    resp = main()
    assert datetime.datetime.today().weekday() == 0
    assert (isinstance(resp, tuple))
    assert _mock1().retrieve_stack_analyses_content()[0] is True
