"""Various utility functions used across the repo."""

import os
import datetime
import json
import logging
import psycopg2
import psycopg2.extras
import itertools
import requests
import heapq
from operator import itemgetter
from datetime import datetime as dt
from psycopg2 import sql
from collections import Counter
from graph_report_generator import generate_report_for_unknown_epvs, \
    generate_report_for_latest_version, rectify_latest_version
from s3_helper import S3Helper
from unknown_deps_report_helper import UnknownDepsReportHelper
from sentry_report_helper import SentryReportHelper
from cve_helper import CVE

logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


class Postgres:
    """Postgres connection session handler."""

    def __init__(self):
        """Initialize the connection to Postgres database."""
        conn_string = "host='{host}' dbname='{dbname}' user='{user}' password='{password}'".\
            format(host=os.getenv('PGBOUNCER_SERVICE_HOST', 'bayesian-pgbouncer'),
                   dbname=os.getenv('POSTGRESQL_DATABASE', 'coreapi'),
                   user=os.getenv('POSTGRESQL_USER', 'coreapi'),
                   password=os.getenv('POSTGRESQL_PASSWORD', 'coreapi'))
        self.conn = psycopg2.connect(conn_string)
        self.cursor = self.conn.cursor()


class ReportHelper:
    """Stack Analyses report helper functions."""

    def __init__(self):
        """Init method for the Report helper class."""
        self.s3 = S3Helper()
        self.pg = Postgres()
        self.conn = self.pg.conn
        self.cursor = self.pg.cursor
        self.unknown_deps_helper = UnknownDepsReportHelper()
        self.sentry_helper = SentryReportHelper()
        self.npm_model_bucket = os.getenv('NPM_MODEL_BUCKET')
        self.maven_model_bucket = os.getenv('MAVEN_MODEL_BUCKET')
        self.pypi_model_bucket = os.getenv('PYPI_MODEL_BUCKET')
        self.golang_model_bucket = os.getenv('GOLANG_MODEL_BUCKET')
        self.maven_training_repo = os.getenv(
            'MAVEN_TRAINING_REPO', 'https://github.com/fabric8-analytics/f8a-hpf-insights')
        self.npm_training_repo = os.getenv(
            'NPM_TRAINING_REPO',
            'https://github.com/fabric8-analytics/fabric8-analytics-npm-insights')
        self.golang_training_repo = os.getenv(
            'GOLANG_TRAINING_REPO', 'https://github.com/fabric8-analytics/f8a-golang-insights')
        self.pypi_training_repo = os.getenv(
            'PYPI_TRAINING_REPO', 'https://github.com/fabric8-analytics/f8a-pypi-insights')

        self.emr_api = os.getenv('EMR_API', 'http://f8a-emr-deployment:6006')

    def cleanup_db_tables(self):
        """Cleanup RDS data tables on a periodic basis."""
        try:
            # Number of days to retain the celery task_meta data
            num_days_metadata = os.environ.get('KEEP_DB_META_NUM_DAYS', '7')
            # query to delete the celery task_meta data
            query = sql.SQL('DELETE FROM celery_taskmeta '
                            'WHERE DATE_DONE <= NOW() - interval \'%s day\';')
            logger.info('Starting to clean up Celery Meta tables')
            # Execute the query
            self.cursor.execute(query.as_string(self.conn) % (num_days_metadata))
            # Log the message returned from db cursor
            logger.info('%r' % self.cursor.statusmessage)
            logger.info('Cleanup of Celery Meta tables complete')

            # Number of days to retain the celery woker_result data
            num_days_workerdata = os.environ.get('KEEP_WORKER_RESULT_NUM_DAYS', '60')
            # query to delete the worker_result data
            query = sql.SQL('DELETE FROM worker_results '
                            'WHERE ended_at <= NOW() - interval \'%s day\';')
            logger.info('Starting to clean up Worker Result data tables')
            # Execute the query
            self.cursor.execute(query.as_string(self.conn) % (num_days_workerdata))
            # Log the message returned from db cursor
            logger.info('%r' % self.cursor.statusmessage)
            logger.info('Cleanup of Worker Result data tables complete')
        except Exception as e:
            logger.error('CleanupDatabaseError: %r' % e)

    def validate_and_process_date(self, some_date):
        """Validate the date format and apply the format YYYY-MM-DDTHH:MI:SSZ."""
        try:
            dt.strptime(some_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Incorrect data format, should be YYYY-MM-DD")
        return some_date

    def retrieve_stack_analyses_ids(self, start_date, end_date):
        """Retrieve results for stack analyses requests."""
        try:
            # start_date from which data is to be fetched
            start_date = self.validate_and_process_date(start_date)
            # end_date up to which data is to be fetched
            end_date = self.validate_and_process_date(end_date)
        except ValueError:
            # checks Invalid date format
            raise ValueError("Invalid date format")
        # Query to fetch Stack Analysis Ids from start_date to end_date
        query = sql.SQL('SELECT {} FROM {} WHERE {} BETWEEN \'%s\' AND \'%s\'').format(
            sql.Identifier('id'),
            sql.Identifier('stack_analyses_request'),
            sql.Identifier('submitTime')
        )
        # Executing Query
        self.cursor.execute(query.as_string(self.conn) % (start_date, end_date))
        # Fetching all results
        rows = self.cursor.fetchall()
        # Appending all the stack-ids in a list
        id_list = []
        for row in rows:
            for col in row:
                id_list.append(col)

        return id_list

    @staticmethod
    def get_time_delta(start_date, end_date):
        """Get Timedelta object."""
        return dt.strptime(end_date, '%Y-%m-%d') - dt.strptime(start_date, '%Y-%m-%d')

    def retrieve_stack_analyses_content(self, start_date, end_date):
        """Retrieve results for stack analyses requests."""
        try:
            # start_date from which data is to be fetched
            start_date = self.validate_and_process_date(start_date)
            # end_date up to which data is to be fetched
            end_date = self.validate_and_process_date(end_date)
        except ValueError:
            # checks Invalid date format
            raise ValueError("Invalid date format")

        # Query to fetch Stack Analysis manifests data from start_date to end_date
        query = sql.SQL('SELECT {} FROM {} WHERE {} BETWEEN \'%s\' AND \'%s\'').format(
            sql.Identifier('requestJson'), sql.Identifier('stack_analyses_request'),
            sql.Identifier('submitTime')
        )
        # Executing Query
        self.cursor.execute(query.as_string(self.conn) % (start_date, end_date))
        # Fetching all results
        return self.cursor.fetchall()

    def flatten_list(self, alist):
        """Convert a list of lists to a single list."""
        return list(itertools.chain.from_iterable(alist))

    def datediff_in_millisecs(self, start_date, end_date):
        """Return the difference of two datetime strings in milliseconds."""
        format = '%Y-%m-%dT%H:%M:%S.%f'
        return (dt.strptime(end_date, format) -
                dt.strptime(start_date, format)).microseconds / 1000

    def populate_key_count(self, in_list=[]):
        """Generate a dict with the frequency of list elements."""
        out_dict = {}
        try:
            for item in in_list:
                if type(item) == dict:
                    logger.error('Unexpected key encountered %r' % item)
                    continue

                if item in out_dict:
                    out_dict[item] += 1
                else:
                    out_dict[item] = 1
        except (IndexError, KeyError, TypeError) as e:
            logger.exception('Error: %r' % e)
            return {}
        return out_dict

    def set_unique_stack_deps_count(self, unique_stacks_with_recurrence_count):
        """Set the dependencies count against the identified unique stacks."""
        out_dict = {}
        for key in unique_stacks_with_recurrence_count.items():
            new_dict = {}
            for stack in key[1].items():
                new_dict[stack[0]] = len(stack[0].split(','))
            out_dict[key[0]] = new_dict
        return out_dict

    def normalize_deps_list(self, deps):
        """Flatten the dependencies dict into a list."""
        normalized_list = []
        for dep in deps:
            normalized_list.append('{package} {version}'.format(package=dep['package'],
                                                                version=dep['version']))
        return sorted(normalized_list)

    def collate_raw_data(self, unique_stacks_with_recurrence_count, frequency):
        """Collate previous raw data with this week/month data."""
        result = {}

        # Get collated user input data
        collated_user_input_obj_key = 'user-input-data/collated-{freq}.json'.format(freq=frequency)
        collated_user_input = self.s3.read_json_object(bucket_name=self.s3.report_bucket_name,
                                                       obj_key=collated_user_input_obj_key) or {}

        for eco in unique_stacks_with_recurrence_count.keys() | collated_user_input.keys():
            result.update({eco: {
                "user_input_stack": dict(
                            Counter(unique_stacks_with_recurrence_count.get(eco)) +
                            Counter(collated_user_input.get(eco, {}).get('user_input_stack')))
            }})

        # Store user input collated data back to S3
        self.s3.store_json_content(content=result, bucket_name=self.s3.report_bucket_name,
                                   obj_key=collated_user_input_obj_key)

        # Get collated big query data
        collated_big_query_obj_key = 'big-query-data/collated.json'
        collated_big_query_data = self.s3.read_json_object(bucket_name=self.s3.report_bucket_name,
                                                           obj_key=collated_big_query_obj_key) or {}

        for eco in collated_big_query_data.keys():
            if result.get(eco):
                result[eco]["bigquery_data"] = collated_big_query_data.get(eco)
            else:
                result[eco] = {"bigquery_data": collated_big_query_data.get(eco)}
        return result

    def invoke_emr_api(self, bucket_name, ecosystem, data_version, github_repo):
        """Invoke EMR Retraining API to start the retraining process."""
        payload = {
            'bucket_name': bucket_name,
            'github_repo': github_repo,
            'ecosystem': ecosystem,
            'data_version': data_version
        }

        logger.info('bucket_name for {eco}: {buck}'.format(eco=ecosystem, buck=bucket_name))
        logger.info('github_repo for {eco}: {git}'.format(eco=ecosystem, git=github_repo))
        logger.info('data_version for {eco}: {data}'.format(eco=ecosystem, data=data_version))

        try:
            # Invoke EMR API to run the retraining
            resp = requests.post(url=self.emr_api + '/api/v1/runjob', json=payload)
            logger.info(resp.json())
            # Check for status code
            # If status is not success, log it as an error
            if resp.status_code == 200:
                logger.info('Successfully invoked EMR API for {eco} ecosystem \n {resp}'.format(
                    eco=ecosystem, resp=resp.json()))
            else:
                logger.error('Error received from EMR API for {eco} ecosystem \n {resp}'.format(
                    eco=ecosystem, resp=resp.json()))
        except Exception as e:
            logger.error('Failed to invoke EMR API for {eco}, error: %r'.format(eco=ecosystem) % e)

    def get_training_data_for_ecosystem(self, eco, stack_dict):
        """Get Training data for an ecosystem."""
        unique_stacks = {}
        package_dict_for_eco = {
            "user_input_stack": [],
            "bigquery_data": []
        }
        for stack_type, stacks in stack_dict.items():
            for package_string in stacks:
                package_list = [x.strip().split(' ')[0]
                                for x in package_string.split(',')]
                stack_str = "".join(package_list)
                if stack_str not in unique_stacks:
                    unique_stacks[stack_str] = 1
                    package_dict_for_eco.get(stack_type).append(package_list)

        training_data = {
            'ecosystem': eco,
            'package_dict': package_dict_for_eco
        }

        return training_data

    def store_training_data(self, result):
        """Store Training Data for each ecosystem in their respective buckets."""
        model_version = dt.now().strftime('%Y-%m-%d')

        for eco, stack_dict in result.items():
            training_data = self.get_training_data_for_ecosystem(eco, stack_dict)
            obj_key = '{model_version}/data/manifest.json'.format(model_version=model_version)

            # Get the bucket name based on ecosystems to store user-input stacks for retraining
            if eco == 'maven':
                bucket_name = self.maven_model_bucket
                github_repo = self.maven_training_repo
                logger.info('maven bucket name is: {bucket}'.format(bucket=bucket_name))
            elif eco == 'pypi':
                bucket_name = self.pypi_model_bucket
                github_repo = self.pypi_training_repo
                logger.info('pypi bucket name is: {bucket}'.format(bucket=bucket_name))
            elif eco == 'go':
                bucket_name = self.golang_model_bucket
                github_repo = self.golang_training_repo
                logger.info('go bucket name is: {bucket}'.format(bucket=bucket_name))
            elif eco == 'npm':
                bucket_name = self.npm_model_bucket
                github_repo = self.npm_training_repo
                logger.info('npm bucket name is: {bucket}'.format(bucket=bucket_name))
            else:
                continue

            if bucket_name:
                logger.info('Storing user-input stacks for ecosystem {eco} at {dir}'.format(
                    eco=eco, dir=bucket_name + obj_key))
                try:
                    # Store the training content for each ecosystem
                    self.s3.store_json_content(content=training_data, bucket_name=bucket_name,
                                               obj_key=obj_key)
                    # Invoke the EMR API to kickstart retraining process
                    # This EMR invocation happens for all ecosystems almost at the same time.
                    # TODO - find an alternative if there is a need
                    self.invoke_emr_api(bucket_name, eco, model_version, github_repo)
                except Exception as e:
                    logger.error('Unable to invoke EMR API. Reason: %r' % e)

    def get_trending(self, mydict, top_trending_count=3):
        """Generate the top trending items list."""
        return (dict(heapq.nlargest(top_trending_count, mydict.items(), key=itemgetter(1))))

    def get_ecosystem_summary(self, ecosystem, total_stack_requests, all_deps, all_unknown_deps,
                              unique_stacks_with_recurrence_count, unique_stacks_with_deps_count,
                              avg_response_time, unknown_deps_ingestion_report):
        """Generate ecosystem specific stack summary."""
        unique_dep_frequency = self.populate_key_count(self.flatten_list(all_deps[ecosystem]))
        rectify_latest_version(unique_dep_frequency, ecosystem, True)
        return {
            'stack_requests_count': total_stack_requests[ecosystem],
            'unique_dependencies_with_frequency':
            self.populate_key_count(self.flatten_list(all_deps[ecosystem])),
            'unique_unknown_dependencies_with_frequency': unique_dep_frequency,
            'unique_stacks_with_frequency': unique_stacks_with_recurrence_count[ecosystem],
            'unique_stacks_with_deps_count': unique_stacks_with_deps_count[ecosystem],
            'average_response_time': '{} ms'.format(avg_response_time[ecosystem]),
            'trending': {
                'top_stacks':
                    self.get_trending(unique_stacks_with_recurrence_count[ecosystem], 3),
                'top_deps': self.get_trending(
                    self.populate_key_count(self.flatten_list(all_deps[ecosystem])), 5),
            },
            'previously_unknown_dependencies': unknown_deps_ingestion_report[ecosystem]
        }

    def save_result(self, frequency, report_name, template):
        """Save result in S3 bucket."""
        try:
            obj_key = '{freq}/{report_name}.json'.format(
                freq=frequency, report_name=report_name
            )
            self.s3.store_json_content(content=template, obj_key=obj_key,
                                       bucket_name=self.s3.report_bucket_name)
        except Exception as e:
            logger.exception('Unable to store the report on S3. Reason: %r' % e)

    def get_report_name(self, frequency, end_date):
        """Create a report name."""
        if frequency == 'monthly':
            return dt.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m')
        else:
            return dt.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')

    def collate_and_retrain(self, unique_stacks, frequency='weekly'):
        """Append stacks to 'collated-weekly' and re-train models."""
        # Append last week's data to 'collated-weekly'; returns 'BQ+collated' data
        collated_data = self.collate_raw_data(unique_stacks, frequency)
        # Store ecosystem specific manifest.json and re-trains models
        self.store_training_data(collated_data)

    def create_venus_report(self, venus_input):
        """Create venus report."""
        # Retrieve input variables
        frequency = venus_input[0]
        report_name = venus_input[1]
        template = venus_input[2]

        self.save_result(frequency, report_name, template)
        return template

    def normalize_worker_data(self, start_date, end_date, stack_data, worker,
                              frequency='daily', retrain=False):
        """Normalize worker data for reporting."""
        total_stack_requests = {'all': 0, 'npm': 0, 'maven': 0, 'pypi': 0}

        report_name = self.get_report_name(frequency, end_date)

        # Prepare the template
        stack_data = json.loads(stack_data)
        template = {
            'report': {
                'from': start_date,
                'to': end_date,
                'generated_on': dt.now().isoformat('T')
            },
            'stacks_summary': {},
            'stacks_details': []
        }
        all_deps = {'npm': [], 'maven': [], 'pypi': []}
        all_unknown_deps = {'npm': [], 'maven': [], 'pypi': []}
        all_unknown_lic = []
        all_cve_list = []

        # Process the response
        total_response_time = {'all': 0.0, 'npm': 0.0, 'maven': 0.0, 'pypi': 0.0}
        if worker == 'stack_aggregator_v2':
            stacks_list = {'npm': [], 'maven': [], 'pypi': []}
            for data in stack_data:
                stack_info_template = {
                    'ecosystem': '',
                    'stack': [],
                    'unknown_dependencies': [],
                    'license': {
                        'conflict': False,
                        'unknown': []
                    },
                    'security': {
                        'cve_list': [],
                    },
                    'response_time': ''
                }
                try:
                    user_stack_info = data[0]['stack_data'][0]['user_stack_info']
                    if len(user_stack_info['dependencies']) == 0:
                        continue

                    stack_info_template['ecosystem'] = user_stack_info['ecosystem']
                    total_stack_requests['all'] += 1
                    total_stack_requests[stack_info_template['ecosystem']] += 1

                    stack_info_template['stack'] = self.normalize_deps_list(
                        user_stack_info['dependencies'])
                    all_deps[user_stack_info['ecosystem']].append(stack_info_template['stack'])
                    stack_str = ','.join(stack_info_template['stack'])
                    stacks_list[user_stack_info['ecosystem']].append(stack_str)

                    unknown_dependencies = []
                    for dep in user_stack_info['unknown_dependencies']:
                        dep['package'] = dep.pop('name')
                        unknown_dependencies.append(dep)
                    stack_info_template['unknown_dependencies'] = self.normalize_deps_list(
                        unknown_dependencies)
                    all_unknown_deps[user_stack_info['ecosystem']].\
                        append(stack_info_template['unknown_dependencies'])

                    stack_info_template['license']['unknown'] = \
                        user_stack_info['license_analysis']['unknown_licenses']['really_unknown']
                    all_unknown_lic.append(stack_info_template['license']['unknown'])

                    for pkg in user_stack_info['analyzed_dependencies']:
                        for cve in pkg['security']:
                            stack_info_template['security']['cve_list'].append(cve)
                            all_cve_list.append('{cve}:{cvss}'.
                                                format(cve=cve['CVE'], cvss=cve['CVSS']))

                    ended_at, started_at = \
                        data[0]['_audit']['ended_at'], data[0]['_audit']['started_at']

                    response_time = self.datediff_in_millisecs(started_at, ended_at)
                    stack_info_template['response_time'] = '%f ms' % response_time
                    total_response_time['all'] += response_time
                    total_response_time[stack_info_template['ecosystem']] += response_time
                    template['stacks_details'].append(stack_info_template)
                except (IndexError, KeyError, TypeError) as e:
                    logger.exception('Error: %r' % e)
                    continue

            unique_stacks_with_recurrence_count = {
                'npm': self.populate_key_count(stacks_list['npm']),
                'maven': self.populate_key_count(stacks_list['maven']),
                'pypi': self.populate_key_count(stacks_list['pypi'])
            }

            unique_stacks_with_deps_count = \
                self.set_unique_stack_deps_count(unique_stacks_with_recurrence_count)

            avg_response_time = {}
            if total_stack_requests['npm'] > 0:
                avg_response_time['npm'] = total_response_time['npm'] / total_stack_requests['npm']
            else:
                avg_response_time['npm'] = 0

            if total_stack_requests['maven'] > 0:
                avg_response_time['maven'] = \
                    total_response_time['maven'] / total_stack_requests['maven']
            else:
                avg_response_time['maven'] = 0

            if total_stack_requests['pypi'] > 0:
                avg_response_time['pypi'] = \
                    total_response_time['pypi'] / total_stack_requests['pypi']
            else:
                avg_response_time['pypi'] = 0

            # Get a list of unknown licenses
            unknown_licenses = []
            for lic_dict in self.flatten_list(all_unknown_lic):
                if 'license' in lic_dict:
                    unknown_licenses.append(lic_dict['license'])

            unknown_deps_ingestion_report = self.unknown_deps_helper.get_current_ingestion_status()

            # generate aggregated data section
            template['stacks_summary'] = {
                'total_stack_requests_count': total_stack_requests['all'],
                'npm': self.get_ecosystem_summary('npm', total_stack_requests, all_deps,
                                                  all_unknown_deps,
                                                  unique_stacks_with_recurrence_count,
                                                  unique_stacks_with_deps_count,
                                                  avg_response_time,
                                                  unknown_deps_ingestion_report),
                'maven': self.get_ecosystem_summary('maven', total_stack_requests, all_deps,
                                                    all_unknown_deps,
                                                    unique_stacks_with_recurrence_count,
                                                    unique_stacks_with_deps_count,
                                                    avg_response_time,
                                                    unknown_deps_ingestion_report),
                'pypi': self.get_ecosystem_summary('pypi', total_stack_requests, all_deps,
                                                   all_unknown_deps,
                                                   unique_stacks_with_recurrence_count,
                                                   unique_stacks_with_deps_count,
                                                   avg_response_time,
                                                   unknown_deps_ingestion_report),
                'unique_unknown_licenses_with_frequency':
                    self.populate_key_count(unknown_licenses),
                'unique_cves':
                    self.populate_key_count(all_cve_list),
                'total_average_response_time':
                    '{} ms'.format(total_response_time['all'] / len(template['stacks_details'])),
                'cve_report': CVE().generate_cve_report(updated_on=start_date)
            }

            # monthly data collection on the 1st of every month
            if frequency == 'monthly':
                self.collate_raw_data(unique_stacks_with_recurrence_count, 'monthly')

            # return data to re-train models or generate venus report
            if retrain is True:
                return unique_stacks_with_recurrence_count
            else:
                venus_input = [frequency, report_name, template]
                return venus_input
        else:
            # todo: user feedback aggregation based on the recommendation task results
            return None

    def retrieve_worker_results(self, start_date, end_date, id_list=[], worker_list=[],
                                frequency='daily', retrain=False):
        """Retrieve results for selected worker from RDB."""
        result_interim = {}
        # convert the elements of the id_list to sql.Literal
        # so that the SQL query statement contains the IDs within quotes
        id_list = list(map(sql.Literal, id_list))
        ids = sql.SQL(', ').join(id_list).as_string(self.conn)

        for worker in worker_list:
            # Selecting only versions = v1
            query = sql.SQL('SELECT {} FROM {} WHERE {} IN (%s) AND {} = \'%s\' '
                            'AND {}->\'_audit\'->>\'version\' = \'%s\'').format(
                sql.Identifier('task_result'), sql.Identifier('worker_results'),
                sql.Identifier('external_request_id'), sql.Identifier('worker'),
                sql.Identifier('task_result')
            )

            self.cursor.execute(query.as_string(self.conn) % (ids, worker, 'v1'))
            data = json.dumps(self.cursor.fetchall())
            if not self.cursor.rowcount:
                logger.info('No Data has been found for v1 stack analyses.')
                return result_interim

            if retrain is True:
                unique_stacks = self.normalize_worker_data(start_date, end_date,
                                                           data, worker, frequency, retrain)
                return unique_stacks
            else:
                # associate the retrieved data to the worker name
                result_interim[worker] = \
                    self.normalize_worker_data(start_date, end_date, data,
                                               worker, frequency, retrain)
        return result_interim

    def retrieve_ingestion_results(self, start_date, end_date, frequency='daily'):
        """Retrieve results for selected worker from RDB."""
        logger.info('Retrieve ingestion results.')
        result = {}

        # Query to fetch the EPVs that were ingested on a particular day

        query = sql.SQL('SELECT EC.NAME, PK.NAME, VR.IDENTIFIER FROM ANALYSES AN,'
                        ' PACKAGES PK, VERSIONS VR, ECOSYSTEMS EC WHERE'
                        ' AN.STARTED_AT >= \'%s\' AND AN.STARTED_AT < \'%s\''
                        ' AND AN.VERSION_ID = VR.ID AND VR.PACKAGE_ID = PK.ID'
                        ' AND PK.ECOSYSTEM_ID = EC.ID')

        self.cursor.execute(query.as_string(self.conn) % (start_date, end_date))
        data = json.dumps(self.cursor.fetchall())
        result['EPV_DATA'] = data
        return self.normalize_ingestion_data(start_date, end_date, result, frequency)

    def generate_results(self, epvs, template, pkg_output, ver_output):
        """Get package information from graph."""
        template['ingestion_summary']['incorrect_latest_version'] = {}
        template['ingestion_summary']['unknown_deps'] = {}
        count = {}
        latest_epvs = []
        checked_pkgs = []
        for epv in epvs:
            eco = epv['ecosystem']
            pkg = epv['name']
            ver = epv['version']

            # Add parameters to count the different params
            if eco not in count:
                count[eco] = {
                    'incorrect_latest_versions': 0,
                    'correct_latest_versions': 0,
                    'ingested_in_graph': 0,
                    'not_ingested_in_graph': 0
                }
            if eco not in template['ingestion_summary']['incorrect_latest_version']:
                template['ingestion_summary']['incorrect_latest_version'][eco] = []
                template['ingestion_summary']['unknown_deps'][eco] = []
            pkg_data = pkg_output[eco + "@DELIM@" + pkg]
            ver_data = ver_output[eco + "@DELIM@" + pkg + "@DELIM@" + ver]
            actual_latest_ver = pkg_data['actual_latest_version']

            # check if the package is publicly available
            if actual_latest_ver:
                known_latest_ver = pkg_data['known_latest_version']
                if actual_latest_ver != known_latest_ver and (eco + "@DELIM@" + pkg
                                                              not in checked_pkgs):
                    checked_pkgs.append(eco + "@DELIM@" + pkg)
                    tmp = {
                        "package": pkg,
                        "actual_latest_version": actual_latest_ver,
                        "known_latest_version": known_latest_ver
                    }
                    template['ingestion_summary']['incorrect_latest_version'][eco].append(tmp)
                    count[eco]['incorrect_latest_versions'] += 1

                template['ingestion_details'][eco][pkg]['known_latest_version'] \
                    = known_latest_ver
                template['ingestion_details'][eco][pkg]['actual_latest_version'] \
                    = actual_latest_ver
                non_cve_version = pkg_data.get('non_cve_version', '')
                if non_cve_version:
                    template['ingestion_details'][eco][pkg]['non_cve_version'] \
                        = non_cve_version
                latest_json = {
                    "ecosystem": eco,
                    "name": pkg,
                    "version": actual_latest_ver
                }
                latest_epvs.append(latest_json)

                # Count the correct latest version EPVs
                if actual_latest_ver == known_latest_ver:
                    count[eco]['correct_latest_versions'] += 1

                # Add to report if the EPV exist in the graph or not
                template['ingestion_details'][eco][pkg][ver]['synced_to_graph'] = ver_data
                if ver_data == "false":
                    template['ingestion_summary']['unknown_deps'][eco].append(epv)
                    count[eco]['not_ingested_in_graph'] += 1
                else:
                    count[eco]['ingested_in_graph'] += 1
            else:
                # Mark the package as private as the information is not present publicly
                template['ingestion_details'][eco][pkg]['private_pkg'] = "true"

        # For each ecosystem, calculate the %age accuracy
        for eco in count:
            correct = count[eco]['correct_latest_versions']
            incorrect = count[eco]['incorrect_latest_versions']
            # Calculate the %age of latest version accuracy
            if correct != 0 or incorrect != 0:
                count[eco]['latest_version_accuracy'] = round(((correct * 100) /
                                                               (correct + incorrect)), 2)

            correct = count[eco]['ingested_in_graph']
            incorrect = count[eco]['not_ingested_in_graph']
            # Calculate the %age of successful ingestion
            if correct != 0 or incorrect != 0:
                count[eco]['ingestion_accuracy'] = round(((correct * 100) /
                                                          (correct + incorrect)), 2)

            # Rectify the latest versions only if present
            if count[eco]['incorrect_latest_versions'] != 0:
                summary = template['ingestion_summary']
                logger.info("Information related to incorrect latest version --")
                logger.info(summary['incorrect_latest_version'][eco])
                rectify_latest_version(summary['incorrect_latest_version'][eco], eco)
        template['ingestion_summary']['stats'] = count
        return template, latest_epvs

    def check_latest_node(self, latest_epvs, template):
        """Get if latest node is present in graph."""
        graph_output = generate_report_for_unknown_epvs(latest_epvs)
        missing_latest = {}
        for epv in latest_epvs:
            eco = epv['ecosystem']
            pkg = epv['name']
            ver = epv['version']
            output = graph_output[eco + "@DELIM@" + pkg + "@DELIM@" + ver]
            template['ingestion_details'][eco][pkg]['latest_node_in_graph'] = output

            # If the EPV is missing in graph, add it to the summary
            if output == "false":
                if eco not in missing_latest:
                    missing_latest[eco] = []
                tmp = {
                    "package": pkg,
                    "version": ver
                }
                missing_latest[eco].append(tmp)
        template['ingestion_summary']['missing_latest_node'] = missing_latest
        return template, missing_latest

    def populate_default_information(self, epv_data, template):
        """To populate the default information in the template."""
        epvs = []
        ing_details = {}
        for epv in epv_data:
            eco = epv[0]
            pkg = epv[1]
            ver = epv[2]
            epv_template = {
                'ecosystem': eco,
                'name': pkg,
                'version': ver
            }
            epvs.append(epv_template)

            # Add eco key in json if missing
            if eco not in ing_details:
                ing_details[eco] = {}

            # Add pkg key in json if missing
            if pkg not in ing_details[eco]:
                ing_details[eco][pkg] = {}

            # Add version key in json if missing
            if ver not in ing_details[eco][pkg]:
                ing_details[eco][pkg][ver] = {}

        # Add the EPV information to the template
        template['ingestion_details'] = ing_details
        return template, epvs

    def normalize_ingestion_data(self, start_date, end_date, ingestion_data, frequency='daily'):
        """Normalize worker data for reporting."""
        logger.info("Normalize Ingestion Data started")
        report_type = 'ingestion-data'
        if frequency == 'monthly':
            report_name = dt.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m')
        else:
            report_name = dt.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')

        template = {
            'report': {
                'from': start_date,
                'to': end_date,
                'generated_on': dt.now().isoformat('T')
            },
            'ingestion_summary': {},
            'ingestion_details': {}
        }

        epv_data = ingestion_data['EPV_DATA']
        epv_data = json.loads(epv_data)

        # Populate the default template with EPV info
        template, epvs = self.populate_default_information(epv_data, template)

        logger.info("Fetching details of the latest version for the epvs")
        today = dt.today()
        pkg_output = generate_report_for_latest_version(epvs, today)
        logger.info("Fetching details of the unknown packages for the epvs")
        ver_output = generate_report_for_unknown_epvs(epvs)

        # Call the function to add the package information to the template
        template, latest_epvs = self.generate_results(epvs, template, pkg_output, ver_output)

        # Call the function to get the availability of latest node
        logger.info("Checking if latest node exists in graph")
        template, missing_latest_nodes = self.check_latest_node(latest_epvs, template)

        # Saving the final report in the relevant S3 bucket
        try:
            obj_key = '{type}/epv/{report_name}.json'.format(
                type=report_type, report_name=report_name
            )
            self.s3.store_json_content(content=template, obj_key=obj_key,
                                       bucket_name=self.s3.report_bucket_name)
        except Exception as e:
            logger.exception('Unable to store the report on S3. Reason: %r' % e)
        return template, missing_latest_nodes

    def get_report(self, start_date, end_date, frequency='daily', retrain=False):
        """Generate the stacks report."""
        logger.info("Get Report Executed.")
        ids = self.retrieve_stack_analyses_ids(start_date, end_date)
        worker_list = ['stack_aggregator_v2']
        ingestion_results = False
        missing_latest_node = {}

        if frequency == 'daily':
            start = datetime.datetime.now()
            result, missing_latest_node = self.retrieve_ingestion_results(start_date, end_date)
            elapsed_seconds = (datetime.datetime.now() - start).total_seconds()
            logger.info(
                "It took {t} seconds to generate ingestion report.".format(
                    t=elapsed_seconds))
            if result['ingestion_details'] != {}:
                ingestion_results = True
            else:
                ingestion_results = False

            result = self.sentry_helper.retrieve_sentry_logs(start_date, end_date)
            if not result:
                logger.error('No Sentry Error Logs found in last 24 hours')
        if len(ids) > 0:
            logger.info('stack analyses data exists.')
            result_interim = self.retrieve_worker_results(
                start_date, end_date, ids, worker_list, frequency, retrain)

            # generate result for each worker
            worker_result = {}
            if not result_interim:
                logger.error('No v1 Stack Analyses found in last 1 day.')
                return worker_result, ingestion_results, missing_latest_node

            for worker in worker_list:
                if worker == 'stack_aggregator_v2':
                    worker_result[worker] = self.create_venus_report(result_interim[worker])
                # can add results for more workers later

            return worker_result, ingestion_results, missing_latest_node
        else:
            logger.error('No stack analyses found from {s} to {e} to generate an aggregated report'
                         .format(s=start_date, e=end_date))
            return False, ingestion_results, missing_latest_node

    def re_train(self, start_date, end_date, frequency='weekly', retrain=True):
        """Re-trains models for all ecosystems."""
        logger.info('retraining triggered.')
        ids = self.retrieve_stack_analyses_ids(start_date, end_date)
        if len(ids) > 0:
            unique_stacks = self.retrieve_worker_results(
                start_date, end_date, ids, ['stack_aggregator_v2'], frequency, retrain)
            # collate stacks and re-train models for all ecosystems
            self.collate_and_retrain(unique_stacks, frequency)

        else:
            logger.error('No stack analyses found from {s} to {e} to re-train models'
                         .format(s=start_date, e=end_date))
