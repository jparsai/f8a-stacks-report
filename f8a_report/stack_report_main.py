"""Daily stacks report."""

import logging
from datetime import datetime as dt, timedelta
from helpers.report_helper import ReportHelper
from v2.report_generator import StackReportBuilder
from helpers.ingestion_helper import ingest_epv

logger = logging.getLogger(__file__)


def main():
    """Generate the daily stacks report."""
    r = ReportHelper()
    report_builder_v2 = StackReportBuilder(ReportHelper)
    today = dt.today()
    start_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
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

    # After all the reports are generated,
    # trigger ingestion flow for the packages which are missing a version from Graph DB.
    ingest_epv(missing_latest_nodes)

    return response


if __name__ == '__main__':
    main()
