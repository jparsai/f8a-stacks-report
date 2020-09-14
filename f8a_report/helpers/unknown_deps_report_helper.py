"""Various functions related to ingestion of previously reported unknown dependencies."""

from datetime import datetime as dt, timedelta
from helpers.graph_report_generator import find_ingested_epv
from helpers.s3_helper import S3Helper
import logging

logger = logging.getLogger(__file__)


class UnknownDepsReportHelper:
    """Utility functions for reporting ingestion of reported unknown dependencies.

    Lists Previous Day Unknown Dependencies from Previous Day Daily Report
    """

    def __init__(self):
        """Init method for UnknownDepReportHelper."""
        self.s3 = S3Helper()

    @staticmethod
    def get_obj_key(past_date):
        """Get s3 object key."""
        logger.info("Building key for v1.")
        return f'daily/{past_date}.json'

    def get_unknown_list(self, result):
        """Create a list of unknown deps."""
        ecosystem_list = ['npm', 'maven', 'pypi']
        unknown_deps_list = {}
        for eco in ecosystem_list:
            deps = []
            if result:
                unknown_deps = result.get('stacks_summary', {}).get(eco, {}). \
                    get('unique_unknown_dependencies_with_frequency', {})
                for k, v in unknown_deps.items():
                    pkg_ver = k.split()
                    try:
                        pkg, ver = pkg_ver[0], pkg_ver[1]
                        deps.append({'name': pkg, 'version': ver})
                    except IndexError:
                        logger.info("Incorrect name value pair found in unknown list {}".format(k))
            unknown_deps_list[eco] = deps
        return unknown_deps_list

    def get_past_unknown_deps(self):
        """Retrieve the list of unknown deps."""
        logger.info("Fetching past unknown deps.")
        # find out the previous date
        today = dt.today()
        past_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')

        # Get the report of the previous date
        past_obj_key = self.get_obj_key(past_date)
        result = self.s3.read_json_object(bucket_name=self.s3.report_bucket_name,
                                          obj_key=past_obj_key)

        # Return the list of unknown dependencies found
        return self.get_unknown_list(result)

    def get_current_ingestion_status(self):
        """Generate ingestion report for previously unknown dependecies."""
        # Get the past unknown dependencies
        unknown_deps = self.get_past_unknown_deps()
        ingestion_report = {}

        # Check for the known one's among those
        for eco, deps in unknown_deps.items():
            ingestion_report[eco] = find_ingested_epv(eco, deps)
        # Report the ingested repositories
        return ingestion_report


class UnknownDepsReportHelperV2(UnknownDepsReportHelper):
    """Unknown Dep Report Helper for v2."""

    @staticmethod
    def get_obj_key(past_date):
        """Get s3 object key."""
        logger.info("Building key for v2.")
        return f'v2/daily/{past_date}.json'
