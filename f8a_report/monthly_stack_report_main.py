"""Monthly stacks report."""

import logging
from datetime import datetime as dt, timedelta, date
from report_helper import ReportHelper
from v2.report_generator import StackReportBuilder

logger = logging.getLogger(__file__)


def main():
    """Generate the monthly stacks report."""
    report_builder_v2 = StackReportBuilder(ReportHelper)
    today = dt.today()

    # Generate a monthly venus report
    logger.info('Monthly Job Triggered')
    last_day_of_prev_month = date(today.year, today.month, 1) - timedelta(days=1)
    last_month_first_date = last_day_of_prev_month.strftime('%Y-%m-01')
    last_month_end_date = last_day_of_prev_month.strftime('%Y-%m-%d')

    # Monthly Report for v2
    logger.info('Generating Monthly report v2 from %s to %s',
                last_month_first_date, last_month_end_date)
    report_builder_v2.get_report(last_month_first_date, last_month_end_date, 'monthly')


if __name__ == '__main__':
    main()
