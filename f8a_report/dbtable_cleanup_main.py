"""Daily clean up of DB tables."""

import logging
from helpers.report_helper import ReportHelper

logger = logging.getLogger(__file__)


def main():
    """Regular clean up of database tables."""
    r = ReportHelper()

    try:
        r.cleanup_db_tables()
    except Exception as e:
        logger.exception("Exception encountered when  trying to clean up DB tables")
        raise e


if __name__ == '__main__':
    main()
