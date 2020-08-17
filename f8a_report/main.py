"""Entry file for the main functionality."""

import logging
from datetime import datetime as dt, timedelta, date
from report_helper import ReportHelper
from v2.report_generator import StackReportBuilder
from manifest_helper import manifest_interface
import os
import requests

logger = logging.getLogger(__file__)

_INVOKE_API_WORKERS = os.environ.get("INVOKE_API_WORKERS", "1")
_WORKER_ADMINISTRATION_REGION = os.environ.get("WORKER_ADMINISTRATION_REGION", "api")
_INGESTION_SERVICE_HOST = os.environ.get("INGESTION_SERVICE_HOST", "bayesian-jobs")
_INGESTION_SERVICE_PORT = os.environ.get("INGESTION_SERVICE_PORT", "34000")
_INGESTION_SERVICE_ENDPOINT = "api/v1/ingest-epv"
_APP_SECRET_KEY = os.getenv('APP_SECRET_KEY', 'not-set')


def time_to_generate_monthly_report(today):
    """Check whether it is the right time to generate monthly report."""
    # We will make three attempts to generate the monthly report every month
    return today.day in (1, 2, 3)


def main():
    """Generate the weekly and monthly stacks report."""
    r = ReportHelper()
    report_builder_v2 = StackReportBuilder(ReportHelper)
    today = dt.today()
    start_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    missing_latest_nodes = {}

    # Daily Venus Report v1
    logger.info(f'Generating Daily report v1 from {start_date} to {end_date}')
    try:
        response, ingestion_results, missing_latest_nodes = r.get_report(start_date,
                                                                   end_date, 'daily', retrain=False)
        logger.info('Daily report v1 Processed.')
    except Exception as e:
        logger.error(f"Error Generating v1 report. {e}")

    # Daily Venus Report v2
    logger.info(f'Generating Daily report v2 from {start_date} to {end_date}')
    try:
        report_builder_v2.get_report(start_date, end_date, 'daily')
        logger.info('Daily report v2 Processed.')
    except Exception as e:
        logger.error(f"Error Generating v2 report. {e}")

    # Regular Cleaning up of celery_taskmeta tables
    r.cleanup_db_tables()
    # Weekly re-training of models
    start_date_wk = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date_wk = today.strftime('%Y-%m-%d')
    if today.weekday() == 0:
        logger.info('Weekly Job Triggered')
        # try:
        #     r.re_train(start_date_wk, end_date_wk, 'weekly', retrain=True)
        # except Exception as e:
        #     logger.error("Exception in Retraining {}".format(e))
        #     pass
        logger.info(os.environ.get('GENERATE_MANIFESTS', 'False'))
        if os.environ.get('GENERATE_MANIFESTS', 'False') in ('True', 'true', '1'):
            logger.info('Generating Manifests based on last 1 week Stack Analyses calls.')
            stacks = r.retrieve_stack_analyses_content(start_date_wk, end_date_wk)
            manifest_interface(stacks)

    # Generate a monthly venus report
    if time_to_generate_monthly_report(today):
        logger.info('Monthly Job Triggered')
        last_day_of_prev_month = date(today.year, today.month, 1) - timedelta(days=1)
        last_month_first_date = last_day_of_prev_month.strftime('%Y-%m-01')
        last_month_end_date = last_day_of_prev_month.strftime('%Y-%m-%d')

        # Monthly Report for v1
        logger.info(f'Generating Monthly report v1 from '
                    f'{last_month_first_date} to {last_month_end_date}')
        r.get_report(last_month_first_date, last_month_end_date, 'monthly', retrain=False)

        # Monthly Report for v2
        logger.info(f'Generating Monthly report v2 from '
                    f'{last_month_first_date} to {last_month_end_date}')
        report_builder_v2.get_report(last_month_first_date, last_month_end_date, 'monthly')

    return missing_latest_nodes


if __name__ == '__main__':
    missing_latest_nodes = main()

    # Initializing Selinon queues and celery workers
    if _INVOKE_API_WORKERS == "1":
        _INGESTION_API_URL = "http://{host}:{port}/{endpoint}".format(
            host=_INGESTION_SERVICE_HOST,
            port=_INGESTION_SERVICE_PORT,
            endpoint=_INGESTION_SERVICE_ENDPOINT)

        for eco, items in missing_latest_nodes.items():

            input_json = {
                "flow_arguments": [],
                "flow_name": "bayesianApiFlow"
            }

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

            if _WORKER_ADMINISTRATION_REGION != 'api':
                input_json["flow_name"] = 'bayesianFlow'

            logger.info("Invoking service for ingestion flow for = {}"
                        .format(input_json))

            response = requests.post(_INGESTION_API_URL, json=input_json,
                                     headers={'auth_token': _APP_SECRET_KEY})

            logger.info("Ingestion API is invoked with response code {} "
                        "and response is : {}".format(response.status_code, response.json()))
