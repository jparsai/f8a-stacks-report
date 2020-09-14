"""Retraining pipeline initiation."""
import logging
from datetime import datetime as dt, timedelta
from helpers.report_helper import ReportHelper

logger = logging.getLogger(__file__)


def main():
    """Retraining pipeline initiation."""
    r = ReportHelper()
    today = dt.today()

    # Weekly re-training of models
    start_date_wk = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date_wk = today.strftime('%Y-%m-%d')

    logger.info('Weekly Job Triggered')
    try:
        r.re_train(start_date_wk, end_date_wk, 'weekly', retrain=True)
    except Exception as e:
        logger.exception("Exception in Retraining")
        raise e


if __name__ == '__main__':
    main()
