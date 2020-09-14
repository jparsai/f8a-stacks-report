"""Dynamic Manifest Generation."""

import logging
from datetime import datetime as dt, timedelta
from helpers.report_helper import ReportHelper
from helpers.manifest_helper import manifest_interface
import os

logger = logging.getLogger(__file__)


def main():
    """Generate the dynamic manifest file weekly."""
    r = ReportHelper()
    today = dt.today()

    start_date_wk = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date_wk = today.strftime('%Y-%m-%d')

    logger.info("Value of generate_manifest flag is %s",
                os.environ.get('GENERATE_MANIFESTS', 'False'))
    if os.environ.get('GENERATE_MANIFESTS', 'False') in ('True', 'true', '1'):
        logger.info('Generating Manifests based on last 1 week Stack Analyses calls.')
        stacks = r.retrieve_stack_analyses_content(start_date_wk, end_date_wk)
        manifest_interface(stacks)


if __name__ == '__main__':
    main()
