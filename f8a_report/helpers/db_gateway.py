#!/usr/bin/env python3
# Copyright © 2020 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Author: Deepak Sharma <deepshar@redhat.com>
#
"""In version 2, All Database Queries will be written here only."""

from helpers.report_helper import Postgres
from psycopg2 import sql
import logging
import json
from datetime import datetime as dt
from f8a_utils.user_token_utils import UserStatus

logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


def validate_and_process_date(date):
    """Validate the date format and apply the format YYYY-MM-DDTHH:MI:SSZ."""
    try:
        dt.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect data format, should be YYYY-MM-DD")
    return date


class ReportQueries(Postgres):
    """Namespace for All RDS Queries used in Reporting."""

    worker_results = sql.SQL('SELECT {} FROM {} WHERE {} IN (%s) AND {} = \'%s\' '
                             'AND {}->\'_audit\'->>\'version\' = \'%s\'').format(
        sql.Identifier('task_result'), sql.Identifier('worker_results'),
        sql.Identifier('external_request_id'), sql.Identifier('worker'),
        sql.Identifier('task_result')
    )

    get_stack_ids = sql.SQL('SELECT {} FROM {} WHERE {} BETWEEN \'%s\' AND \'%s\'').format(
        sql.Identifier('id'),
        sql.Identifier('stack_analyses_request'),
        sql.Identifier('submitTime')
    )

    get_ingestion_query = sql.SQL('SELECT EC.NAME, PK.NAME, VR.IDENTIFIER FROM ANALYSES AN,'
                                  ' PACKAGES PK, VERSIONS VR, ECOSYSTEMS EC WHERE'
                                  ' AN.STARTED_AT >= \'%s\' AND AN.STARTED_AT < \'%s\''
                                  ' AND AN.VERSION_ID = VR.ID AND VR.PACKAGE_ID = PK.ID'
                                  ' AND PK.ECOSYSTEM_ID = EC.ID')

    def __init__(self):
        """Class Constructor."""
        super().__init__()

    def get_worker_results_v2(self, worker, stack_ids) -> dict:
        """Retrieve results for selected worker from RDB."""
        # convert the elements of the id_list to sql.Literal
        # so that the SQL query statement contains the IDs within quotes
        id_list = list(map(sql.Literal, stack_ids))
        ids = sql.SQL(', ').join(id_list).as_string(self.conn)

        query = self.worker_results

        # Selecting only versions = v2
        self.cursor.execute(query.as_string(self.conn) % (ids, worker, 'v2'))
        data = json.dumps(self.cursor.fetchall())
        if not self.cursor.rowcount:
            raise Exception(f'No Data has been found for v2 stack analyses for worker {worker} ')

        logger.info(f'Successfully retrieved results for {worker}.')

        return data

    def retrieve_stack_analyses_ids(self, start_date, end_date) -> list:
        """Retrieve results for stack analyses requests."""
        try:
            # start_date from which data is to be fetched
            start_date = validate_and_process_date(start_date)
            # end_date up to which data is to be fetched
            end_date = validate_and_process_date(end_date)
        except ValueError:
            # checks Invalid date format
            raise ValueError("Invalid date format")
        query = self.get_stack_ids
        self.cursor.execute(query.as_string(self.conn) % (start_date, end_date))
        rows = self.cursor.fetchall()
        id_list = [row[0] for row in rows]
        return id_list

    def retrieve_ingestion_results(self, start_date, end_date) -> dict:
        """Retrieve results for selected worker from RDB."""
        logger.info('Retrieving ingestion results.')
        # Query to fetch the EPVs that were ingested on a particular day
        query = self.get_ingestion_query
        self.cursor.execute(query.as_string(self.conn) % (start_date, end_date))
        data = json.dumps(self.cursor.fetchall())

        return data


class TokenValidationQueries(Postgres):
    """Snyk Token Validation Queries."""

    def __init__(self):
        """Class Constructor."""
        super().__init__()

    def get_registered_user_tokens(self) -> dict:
        """Tokens for registered users."""
        try:
            get_registered_user_sql = \
                sql.SQL("select user_id, snyk_api_token from user_details where status=\'%s\'")
            self.cursor.execute(get_registered_user_sql.as_string(self.conn)
                                % UserStatus.REGISTERED.name)
            result = self.cursor.fetchall()
            user_id_token_dict = {row[0]: row[1] for row in result}
            return user_id_token_dict
        finally:
            self.conn.close()

    def update_users_to_unregistered(self, unregistered_users: list):
        """Update status of unregistered users."""
        try:
            unregistered_user_sql = \
                sql.SQL("update user_details set status=\'%s\', updated_date= NOW() "
                        "where user_id in (%s)")
            id_list = list(map(sql.Literal, unregistered_users))
            ids = sql.SQL(', ').join(id_list).as_string(self.conn)

            self.cursor.execute(unregistered_user_sql.as_string(self.conn) %
                                (UserStatus.EXPIRED.name, ids))

            self.conn.commit()
        finally:
            self.conn.close()
