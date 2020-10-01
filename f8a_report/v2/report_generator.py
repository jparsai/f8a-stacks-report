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
"""Daily/Monthly Report Generator for Stack Analyses v2 API."""

import logging
import json
from helpers.cve_helper import CVE
from datetime import datetime as dt
from helpers.db_gateway import ReportQueries
from helpers.unknown_deps_report_helper import UnknownDepsReportHelperV2
from helpers.s3_helper import S3Helper

logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


class StackReportBuilder():
    """Namespace for Report Builder v2.

    Build and Save Report for Stack Analyses API v2.
    """

    def __init__(self, ReportHelper):
        """Build Report for v2."""
        self.report_helper = ReportHelper()
        self.total_stack_requests = {'all': 0, 'npm': 0, 'maven': 0, 'pypi': 0}
        self.all_deps = {'npm': [], 'maven': [], 'pypi': []}
        self.all_unknown_deps = {'npm': [], 'maven': [], 'pypi': []}
        self.unique_stacks_with_deps_count = 0
        self.unique_stacks_with_recurrence_count = 0
        self.avg_response_time = {'npm': {}, 'maven': {}, 'pypi': {}}
        self.unknown_licenses = []
        self.all_cve_list = []
        self.total_response_time = {'all': 0.0, 'npm': 0.0, 'maven': 0.0, 'pypi': 0.0}
        self.start_date = 'YYYY-MM-DD'
        self.end_date = 'YYYY-MM-DD'
        self.stacks_list = {'npm': [], 'maven': [], 'pypi': []}
        self.all_unknown_lic = []
        self.avg_response_time = {}

    @staticmethod
    def normalize_deps_list(dependencies) -> list:
        """Flatten the dependencies dict into a list.

        :param dependencies: dependencies from each stack
        :return: Normalised Dependencies in a list.
        """
        normalized_list = []
        for dependency in dependencies:
            normalized_list.append(f'{dependency.get("name")} {dependency.get("version")}')
        return sorted(normalized_list)

    @staticmethod
    def get_report_template(start_date, end_date) -> dict:
        """Build Venus Report Template.

        :param start_date: Start date of data collection
        :param end_date: End date of data collection
        :return: Template
        """
        template = {
            'report': {
                'from': start_date,
                'to': end_date,
                'generated_on': dt.now().isoformat('T'),
                'report_version': 'v2',
            },
            'stacks_summary': {},
            'stacks_details': []
        }
        return template

    @staticmethod
    def get_stack_info_template() -> dict:
        """Build Stack Template."""
        stack_info_template = {
            'ecosystem': '',
            'stack': [],
            'unknown_dependencies': [],
            'license': {
                'conflict': False,
                'unknown': []
            },
            'public_vulnerabilities': {
                'cve_list': [],
            },
            'private_vulnerabilities': {
                'cve_list': [],
            },
            'response_time': ''
        }
        return stack_info_template

    @staticmethod
    def get_unknown_licenses(stack) -> list:
        """Fetch unknown_licenses from Stack.

        :param stack: stack data from DB
        :return: List of Unknown licenses.
        """
        return stack.get('license_analysis', {}).get('unknown_licenses', {}).get('unknown', [])

    @staticmethod
    def get_audit_timelines(data) -> tuple:
        """Fetch Start date and end_date from audit key.

        :param data: Stack data
        :returns: started_at, ended_at
        """
        started_at = data.get('_audit', {}).get('started_at')
        ended_at = data.get('_audit', {}).get('ended_at')
        return started_at, ended_at

    def analyse_stack(self, stacks_data, report_template) -> dict:
        """Analyse each stack and Build reporting parameters.

        :param
            :stacks_data: Stacks Data from DB
            :report_template: Report Template
        :return: None
        """
        logger.info("Analysing Stack data")
        for stack in stacks_data:
            stack = stack[0]
            stack_info_template = self.get_stack_info_template()
            ecosystem = stack.get('ecosystem')
            analysed_dependencies = stack.get('analyzed_dependencies', [])
            unknown_dependencies = stack.get('unknown_dependencies', [])
            normalised_unknown_dependencies = self.normalize_deps_list(unknown_dependencies)
            unknown_licenses = self.get_unknown_licenses(stack)
            try:
                if len(analysed_dependencies) == 0:
                    continue
                stack_info_template['ecosystem'] = ecosystem
                self.total_stack_requests['all'] += 1
                self.total_stack_requests[ecosystem] += 1

                stack_info_template['stack'] = self.normalize_deps_list(
                    analysed_dependencies)

                self.all_deps[ecosystem].append(stack_info_template['stack'])
                stack_str = ','.join(stack_info_template['stack'])
                self.stacks_list[ecosystem].append(stack_str)

                stack_info_template['unknown_dependencies'] = normalised_unknown_dependencies
                self.all_unknown_deps[ecosystem].append(normalised_unknown_dependencies)

                stack_info_template['license']['unknown'] = unknown_licenses
                self.all_unknown_lic.append(stack_info_template['license']['unknown'])

                # Accumulating security information.
                for package in analysed_dependencies:
                    stack_info_template = self.collate_vulnerabilites(stack_info_template, package)

                ended_at, started_at = self.get_audit_timelines(stack)
                response_time = self.report_helper.datediff_in_millisecs(started_at, ended_at)
                stack_info_template['response_time'] = '%f ms' % response_time
                self.total_response_time['all'] += response_time
                self.total_response_time[stack_info_template['ecosystem']] += response_time
                report_template['stacks_details'].append(stack_info_template)
            except (IndexError, KeyError, TypeError) as e:
                logger.exception('Error: %r' % e)
                continue
        logger.info("Stacks Analyse Completed.")
        return report_template

    def collate_vulnerabilites(self, stack_info_template, package) -> dict:
        """Collate Vulnerability list of Private and Public Vulnerabilities.

        :param
            :stack_info_template: Template
            :package: Vulnerable package
        :return: Stack Data template filled with data
        """
        for vul_type in ('private_vulnerabilities', "public_vulnerabilities"):
            for cve_info in package.get(vul_type):
                stack_info_template[vul_type]['cve_list'].append(cve_info)
                cve_id = cve_info.get('cve_ids')
                cvss = cve_info.get('cvss')
                self.all_cve_list.append(f'{cve_id}:{cvss}')
        return stack_info_template

    def build_report_summary(self, unknown_deps_ingestion_report, report_content) -> dict:
        """Build Final Report Summary."""
        logger.info("Building Report summary.")

        summary = {
            'total_stack_requests_count': self.total_stack_requests['all'],
            'unique_unknown_licenses_with_frequency':
                self.report_helper.populate_key_count(self.unknown_licenses),
            'unique_cves':
                self.report_helper.populate_key_count(self.all_cve_list),
            'total_average_response_time': '{} ms'.format(
                self.total_response_time['all'] / len(report_content['stacks_details'])),
            'cve_report': CVE().generate_cve_report(updated_on=self.start_date)
        }
        ecosystem_summary = {ecosystem: self.report_helper.get_ecosystem_summary(
            ecosystem, self.total_stack_requests,
            self.all_deps, self.all_unknown_deps,
            self.unique_stacks_with_recurrence_count,
            self.unique_stacks_with_deps_count,
            self.avg_response_time,
            unknown_deps_ingestion_report)
            for ecosystem in ('npm', 'maven', 'pypi')}
        summary.update(ecosystem_summary)
        return summary

    def set_average_response_time(self) -> None:
        """Set Average Response time in self."""
        logger.info("Calculating Average response time.")
        for ecosytem in ('npm', 'maven', 'pypi'):
            if self.total_stack_requests[ecosytem] > 0:
                self.avg_response_time[ecosytem] = \
                    self.total_response_time[ecosytem] / self.total_stack_requests[ecosytem]
                continue
            self.avg_response_time[ecosytem] = 0

    def normalize_worker_data(self, stacks_data, retrain, frequency='daily'):
        """Parser for worker data for Stack Analyses v2.

        :arg:
            stacks_data: Stacks Collected from DB within time-frame.
            frequency: Frequency of Report ( daily/monthly )
        :return: Final Venus Report Generated.
        """
        logger.info("Normalising v2 Stack Data.")
        stacks_data = json.loads(stacks_data)
        report_name = self.report_helper.get_report_name(frequency, self.end_date)
        report_template = self.get_report_template(self.start_date, self.end_date)

        report_content = self.analyse_stack(stacks_data, report_template)

        self.unique_stacks_with_recurrence_count = {
            'npm': self.report_helper.populate_key_count(self.stacks_list['npm']),
            'maven': self.report_helper.populate_key_count(self.stacks_list['maven']),
            'pypi': self.report_helper.populate_key_count(self.stacks_list['pypi'])
        }
        self.unique_stacks_with_deps_count = \
            self.report_helper.set_unique_stack_deps_count(self.unique_stacks_with_recurrence_count)
        self.set_average_response_time()

        # Get a list of unknown licenses
        for lic_dict in self.report_helper.flatten_list(self.all_unknown_lic):
            if 'license' in lic_dict:
                self.unknown_licenses.append(lic_dict['license'])

        unknown_deps_ingestion_report = UnknownDepsReportHelperV2().get_current_ingestion_status()

        report_content['stacks_summary'] = self.build_report_summary(
            unknown_deps_ingestion_report, report_content)

        if frequency == 'monthly':
            # monthly data collection on the 1st of every month
            self.report_helper.collate_raw_data(self.unique_stacks_with_recurrence_count, frequency)

        if retrain:
            return self.unique_stacks_with_recurrence_count

        venus_input = [frequency, report_name, report_content]
        logger.info("Venus Report Successfully Generated.")
        return venus_input

    def get_report(self, start_date, end_date, frequency='daily', retrain=False):
        """Generate the stacks report: Worker Report and Ingestion Report.

        :param start_date: Date from where to start collecting stacks.
        :param end_date: Date upto which to collect stacks.
        :param frequency: Frequency of Reporting (daily/ monthly)
        :param retrain: Boolean to retrain Model.
        :returns: Worker Results and Ingestion Results
        """
        logger.info(f"Venus Report Triggered for freq. {frequency}")
        self.start_date = start_date
        self.end_date = end_date
        rds_obj = ReportQueries()
        ids = rds_obj.retrieve_stack_analyses_ids(start_date, end_date)
        worker = 'stack_aggregator_v2'

        # Ingestion Reporting is in v1
        ingestion_results = False

        if not len(ids):
            logger.info(f'No stack analyses found from {start_date} to {end_date} '
                        f'to generate an aggregated report')
            return False, ingestion_results

        query_data = rds_obj.get_worker_results_v2(worker=worker, stack_ids=ids)

        generated_report = self.normalize_worker_data(query_data, retrain, frequency)

        worker_result = {}
        if not generated_report:
            logger.error(f'No v2 Stack Analyses found from {start_date} to {end_date}.')
            return worker_result, ingestion_results

        worker_result[worker] = self.create_venus_report(generated_report)

        return worker_result, ingestion_results

    def create_venus_report(self, venus_input):
        """Create venus report."""
        # Retrieve input variables
        frequency = venus_input[0]
        report_name = venus_input[1]
        report_content = venus_input[2]

        self.save_worker_result_to_s3(frequency, report_name, report_content)
        return report_content

    @staticmethod
    def save_worker_result_to_s3(frequency, report_name, content) -> bool:
        """Save worker result in S3 bucket.

        :param frequency: Frequency of Reporting ( daily/ monthly)
        :param report_name: Name of File/ Report.
        :param content: File Content to be saved in S3
        :return: True: Save Success, False: Saved Fail
        """
        logger.info("Trying to save report file")
        try:
            s3 = S3Helper()
            obj_key = f'v2/{frequency}/{report_name}.json'
            s3.store_json_content(content=content, obj_key=obj_key,
                                  bucket_name=s3.report_bucket_name)
            logger.info(f"Successfully saved report in {obj_key}.")
            return True
        except Exception as e:
            logger.exception(f'Unable to store the report on S3. Reason: {e}')
            return False
