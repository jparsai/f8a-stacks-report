"""Tests DB Gateway v2."""

from unittest import TestCase
from f8a_report.v2.db_gateway import ReportQueries
from tests.helpers.test_stack_report_helper import MockPostgres


class MyMockPostgres(MockPostgres):
    """Mocker for Postgres."""

    @staticmethod
    def rowcount():
        """Added Mock Instance Method."""
        return 1


class TestReportQueries(TestCase):
    """Test namespace for Reporting Queries."""

    @classmethod
    def setUp(cls):
        """Initialise class with required params."""
        cls.ReportQueries = ReportQueries()
        cls.worker = 'stack_aggregator_v2'

    def test_get_worker_results_v2_exception(self):
        """Test Worker Results Exception."""
        stack_ids = ('09aa6480a3ce477881109d9635c30257',)
        self.assertRaises(Exception,
                          self.ReportQueries.get_worker_results_v2,
                          self.worker, stack_ids)

    def test_get_worker_results_v2(self):
        """Test Worker Results Exception."""
        stack_ids = ('09aa6480a3ce477881109d9635c30257',)
        self.ReportQueries.cursor = MyMockPostgres()
        result = self.ReportQueries.get_worker_results_v2(self.worker, stack_ids)
        self.assertIsNotNone(result)

    def test_retrieve_stack_analyses_ids(self):
        """Test Retrieve Stack Analyses."""
        self.ReportQueries.cursor = MockPostgres()
        ids = self.ReportQueries.retrieve_stack_analyses_ids('2018-10-09', '2018-10-09')
        self.assertIsNotNone(ids)

    def test_retrieve_stack_analyses_ids_exception(self):
        """Test Retrieve Stack Analyses."""
        self.ReportQueries.cursor = MockPostgres()
        self.assertRaises(ValueError,
                          self.ReportQueries.retrieve_stack_analyses_ids,
                          '201-10-09', '18-10-09')

    def test_retrieve_ingestion_results(self):
        """Test Retrieve Ingestion Results."""
        self.ReportQueries.cursor = MockPostgres()
        ids = self.ReportQueries.retrieve_ingestion_results('2018-10-09', '2018-10-19')
        self.assertIsNotNone(ids)
