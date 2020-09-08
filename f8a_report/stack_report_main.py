"""Daily stacks report."""

import logging
from datetime import datetime as dt, timedelta
from report_helper import ReportHelper
from v2.report_generator import StackReportBuilder
import os
import requests

logger = logging.getLogger(__file__)

_INVOKE_API_WORKERS = os.environ.get("INVOKE_API_WORKERS", "1")
_WORKER_ADMINISTRATION_REGION = os.environ.get("WORKER_ADMINISTRATION_REGION", "api")
_INGESTION_SERVICE_HOST = os.environ.get("INGESTION_SERVICE_HOST", "bayesian-jobs")
_INGESTION_SERVICE_PORT = os.environ.get("INGESTION_SERVICE_PORT", "34000")
_INGESTION_SERVICE_ENDPOINT = "api/v1/ingest-epv"
_APP_SECRET_KEY = os.getenv('APP_SECRET_KEY', 'not-set')


def main():
    """Generate the daily stacks report."""
    r = ReportHelper()
    report_builder_v2 = StackReportBuilder(ReportHelper)
    today = dt.today()
    start_date = (today - timedelta(days=500)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    missing_latest_nodes = {}

    # Daily Venus Report v1
    logger.info('Generating Daily report v1 from %s to %s', start_date, end_date)
    try:
        response, ingestion_results, missing_latest_nodes = r.get_report(
            start_date, end_date, 'daily', retrain=False)
        logger.info('Daily report v1 Processed.')
    except Exception:
        logger.exception("Error Generating v1 report")

    # Daily Venus Report v2
    logger.info('Generating Daily report v2 from %s to %s', start_date, end_date)
    try:
        report_builder_v2.get_report(start_date, end_date, 'daily')
        logger.info('Daily report v2 Processed.')
    except Exception as e:
        logger.exception("Error Generating v2 report")
        raise e

    return missing_latest_nodes


if __name__ == '__main__':
    missing_latest_nodes = main()

    """
    Initializing Selinon queues and celery workers.

    If report has packages which are missing any version from Db, ingestion flow
    for such packages will be triggered to ingest requested version into Graph DB
    using Jobs API.
    """
    if _INVOKE_API_WORKERS == "1":
        _INGESTION_API_URL = "http://{host}:{port}/{endpoint}".format(
            host=_INGESTION_SERVICE_HOST,
            port=_INGESTION_SERVICE_PORT,
            endpoint=_INGESTION_SERVICE_ENDPOINT)

        # Make ingestion API call for each ecosystem having list packages
        # and details will be set in dictionary
        for eco, items in missing_latest_nodes.items():

            input_json = {
                "flow_arguments": [],
                "flow_name": "bayesianApiFlow"
            }

            # Create list objects of each package for current eco system.
            for item in items:
                logger.info("Creating request data for ingestion flow for eco= {}, pkg= {}, ver= {}"
                            .format(eco, item['package'], item['version']))

                temp_json = {
                    "ecosystem": eco,
                    "force": True,
                    "force_graph_sync": False,
                    "name": item['package'],
                    "recursive_limit": 0,
                    "version": item['version']
                }

                input_json['flow_arguments'].append(temp_json)

            # Change the flow name from default
            if _WORKER_ADMINISTRATION_REGION != 'api':
                input_json["flow_name"] = 'bayesianFlow'

            logger.info("Invoking service for ingestion flow for = {}"
                        .format(input_json))

            # Make API call and set token which will be used for authentication.
            response = requests.post(_INGESTION_API_URL, json=input_json,
                                     headers={'auth_token': _APP_SECRET_KEY})

            logger.info("Ingestion API is invoked with response code {} "
                        "and response is : {}".format(response.status_code, response.json()))
