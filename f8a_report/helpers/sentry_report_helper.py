"""Various functions related to sentry reporting."""

import os
import logging
import requests as requests
from helpers.s3_helper import S3Helper
from datetime import datetime as dt

logger = logging.getLogger(__file__)


class SentryReportHelper:
    """Various functions related to sentry reporting."""

    def __init__(self):
        """Init method for SentryReportHelper."""
        self.s3 = S3Helper()
        self.sentry_url = os.getenv('SENTRY_URL', 'https://sentry.devshift.net')
        self.sentry_api_issues = self.sentry_url + os.getenv(
            'SENTRY_API_ISSUES', '/api/0/projects/sentry/fabric8-analytics-production/issues/')
        self.sentry_api_tags = self.sentry_url + os.getenv('SENTRY_API_TAGS', '/api/0/issues/')
        self.sentry_token = os.getenv('SENTRY_AUTH_TOKEN', '')

    def retrieve_sentry_logs(self, start_date, end_date):
        """Retrieve results for selected worker from RDB."""
        result = {}
        try:
            # Invoke Sentry API to run the error collection
            auth = 'Bearer {token}'.format(token=self.sentry_token)
            resp = requests.get(url=self.sentry_api_issues + '?statsPeriod=24h',
                                headers={"Authorization": auth})
            # Checking for status code
            # If status is not success, log it as an error
            if resp.status_code == 200:
                logger.info('Successfully invoked Sentry API')
                # associate the retrieved data to result
                result = self.normalize_sentry_data(start_date, end_date, resp.json())
            else:
                logger.error('Error received from Sentry API \n {resp}'.format(resp=resp.json()))
        except requests.exceptions.RequestException as e:
            logger.error('Unable to invoke Sentry API. Reason: %r' % e)
        except requests.exceptions.Timeout as e:
            logger.error('Timeout occured while invoking Sentry API. Reason: %r' % e)
        return result

    def normalize_sentry_data(self, start_date, end_date, errorlogs):
        """Retrieve results for selected worker from RDB."""
        report_type = 'sentry-error-data'
        report_name = dt.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        result = {
            "error_report": {}
        }
        # Iterating all the error logs
        try:
            for item in errorlogs:
                errors = {}
                events = self.retrieve_events(item['id'])
                errors['id'] = item['id']
                errors['last_seen'] = item['lastSeen']
                errors[events['pods_impacted']] = item['metadata']['type'] + ": " + \
                    item['metadata']['value'] if item['metadata'].get('type')\
                    else item['metadata']['title']
                errors['stacktrace'] = events['stacktrace']
                # Detecting the endpoint services
                server_name = "-".join(events['pods_impacted'].split("-")[:-2])
                result['error_report'][server_name] = result['error_report'][server_name] \
                    if result['error_report'].get(server_name) else {}
                # Calculating total errors
                result['error_report'][server_name]['total_errors'] = \
                    result.get('error_report').get(server_name).get('total_errors', 0) + 1
                if not result['error_report'][server_name].get('errors'):
                    result['error_report'][server_name]['errors'] = []
                result['error_report'][server_name]['errors'].append(errors)
        except KeyError as e:
            logger.error('Key not found while parsing. Reason: %r' % e)
            # Saving the final report in the relevant S3 bucket

        try:
            obj_key = '{type}/{report_name}.json'.format(
                type=report_type, report_name=report_name
            )
            self.s3.store_json_content(content=result, obj_key=obj_key,
                                       bucket_name=self.s3.report_bucket_name)
        except Exception as e:
            logger.exception('Unable to store the report on S3. Reason: %r' % e)

        return result

    def retrieve_events(self, issue_id):
        """Retrieve results for issue events."""
        events = {'stacktrace': ''}
        output = {}

        try:
            # Invoke Sentry API to run the event collection
            auth = 'Bearer {token}'.format(token=self.sentry_token)
            resp = requests.get(url=self.sentry_api_tags + issue_id + '/events/latest/',
                                headers={"Authorization": auth})
            # Check for status code
            # If status is not success, log it as an error
            if resp.status_code == 200:
                logger.info('Successfully invoked Sentry API \n {resp}'.format(resp=resp.json()))
                output = resp.json()
            else:
                logger.error('Error received from Sentry API \n {resp}'.format(resp=resp.json()))
        except requests.exceptions.RequestException as e:
            logger.error('Unable to invoke Sentry API3. Reason: %r' % e)
        except requests.exceptions.Timeout as e:
            logger.error('Timeout occured while invoking Sentry API. Reason: %r' % e)

        try:
            # retrieving server name info
            for item in output['tags']:
                if item['key'] == 'server_name':
                    events['pods_impacted'] = item['value']
                    break
            # Collecting stacktrace for each frames
            if output['entries'][1]['type'] == 'exception':
                for frames in output['entries'][1]['data']['values'][0]['stacktrace']['frames']:
                    stacktrace = 'File ' + frames['filename'] + ', Line ' + \
                                 str(frames['lineNo']) + ', Function ' + \
                                 frames['function']
                    # Collecting stacktrace for each line Nos
                    for context in frames['context']:
                        if frames['lineNo'] in context:
                            stacktrace = stacktrace + ', Statement ' + \
                                         context[1] + ' || '
                            break
                    else:
                        stacktrace = stacktrace + ' || '
                    events['stacktrace'] = events['stacktrace'] + stacktrace
            else:
                events['stacktrace'] = 'Not Available'
        except KeyError as e:
            logger.error('Key not found while parsing. Reason: %r' % e)
        except IndexError as e:
            logger.error('Index not found while parsing. Reason: %r' % e)
        except NameError as e:
            logger.error('Name not found while parsing. Reason: %r' % e)
        return events
