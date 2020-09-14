"""CVE Module to generate CVE Report."""
import requests
import time
import os
import logging
from datetime import datetime as dt
from datetime import timedelta
from helpers.graph_report_generator import get_session_retry, GREMLIN_SERVER_URL_REST

logger = logging.getLogger(__file__)


class CVE(object):
    """CVE class helper to validate and generate CVE report."""

    def __init__(self):
        """Initialise CVE class."""
        self.repo_name = os.environ.get('GITHUB_CVE_REPO', 'fabric8-analytics')
        self.github_url = 'https://api.github.com/search/issues?q=repo:{}/cvedb'.format(
            self.repo_name
        )
        self.github_rate_limits = 100
        self.github_rate_limit_reset = -1

    def get_cveids_from_cvedb_prs(self, updated_on):
        """Get all the merged CVEDB Pull Requests."""
        cve_ids = set()

        try:
            # Create a query to fetch PRs merged yesterday
            query = '+type:pr+is:merged+updated:{}&sort=updated&order=desc&per_page=100'.format(
                updated_on
            )
            cve_json = self.call_github_api(query=query)
            for cve in cve_json.get('items'):
                # Get the CVE ID from the title of the PR
                title = cve.get('title', '')
                if title:
                    cve_id = title.strip().split(' ')[-1]
                    # Make sure we get the correct CVE ID e.g CVE-YYYY-ABCD
                    if cve_id.startswith('CVE'):
                        cve_ids.add(cve_id)

            logger.info("List of CVE-IDS picked from CVEDB PRs are %r" % cve_ids)
            return list(cve_ids)

        except (ValueError, TypeError) as e:
            raise ValueError('%r' % e)

    def validate_cveids_in_graph(self, cve_ids):
        """Identify CVEs ingested to graph or missed being ingested."""
        ingested = []
        missed = []
        assert isinstance(cve_ids, list)
        # Check whether CVE node is present in graph or not
        try:
            for cve_id in cve_ids:
                gremlin_query = "g.V().has('cve_id', '{}').valueMap();".format(cve_id)
                payload = {'gremlin': gremlin_query}
                try:
                    resp = get_session_retry().post(url=GREMLIN_SERVER_URL_REST, json=payload)
                    if resp.status_code == 200:
                        graph_resp = resp.json()
                        if graph_resp.get('result', {}).get('data', []):
                            ingested.append(cve_id)
                        else:
                            missed.append(cve_id)
                    else:
                        msg = "Error - CVEGraphValidation failed for CVE: {} with error: {}".format(
                                cve_id, resp.status_code)
                        logger.error(msg)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                        requests.exceptions.RequestException) as e:
                    logger.error('Error Connecting to Graph Instance : %r' % e)
                    continue

            return ingested, missed

        except (ValueError, AssertionError) as e:
            raise ValueError('%r' % e)

    def get_fp_cves_count(self, updated_on):
        """Identify total false positive CVEs that were not mapped correctly."""
        try:
            # Create a query to fetch False Positive PRs closed yesterday
            query = '+type:pr+is:closed+updated:{}'.format(updated_on)
            cve_json = self.call_github_api(query=query)
            return cve_json.get('total_count', -1)

        except (ValueError, TypeError) as e:
            raise ValueError('%r' % e)

    def call_github_api(self, query):
        """Return the json output from Github APIs."""
        # Check if we are above github rate limits
        # If yes, wait till the limit is reset
        if self.github_rate_limits <= 1 and self.github_rate_limit_reset > 0:
            wait_time = self.github_rate_limit_reset - int(dt.now().timestamp())
            logger.info("Github Rate Limits Exceeded. Waiting for {} seconds".format(wait_time))
            time.sleep(wait_time)
        try:
            resp = requests.get(url=self.github_url + query,
                                headers={"Accept": "application/vnd.github.symmetra-preview+json"})
            self.github_rate_limits = int(resp.headers.get('X-RateLimit-Remaining', 0))
            self.github_rate_limit_reset = int(resp.headers.get('X-RateLimit-Reset', -1))

            return resp.json() or None

        except (ValueError, requests.exceptions.ConnectionError,
                requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            logger.error("Error fetching via github API for query: {}".format(query))
            raise ValueError('%r' % e)

    def get_open_cves_count(self, updated_on):
        """Get all the open CVE count for the last [2, 7, 30, 365] days."""
        cve_stats = {"github_stats": {"open_count": {}}}
        end_date = (dt.strptime(updated_on, "%Y-%m-%d") - timedelta(days=1)).strftime(
                    "%Y-%m-%d")
        # Create a query to fetch PRs not acted for more than xx days
        for day in [2, 7, 30, 365]:
            open_key = str(day) + " days"
            start_date = (dt.strptime(updated_on, "%Y-%m-%d") - timedelta(days=day)).strftime(
                "%Y-%m-%d")
            query = '+type:pr+is:open+created:{}..{}'.format(start_date, end_date)
            try:
                cve_json = self.call_github_api(query=query)
                if cve_json and isinstance(cve_json, dict):
                    cve_stats['github_stats']['open_count'][open_key] = \
                        cve_json.get('total_count', -1)
            except (ValueError, TypeError) as e:
                logger.error('%r' % e)
                continue
        return cve_stats

    def generate_cve_report(self, updated_on):
        """Generate CVE statistics and CVE ingestion report."""
        try:
            assert dt.strptime(updated_on, "%Y-%m-%d")
            # Add Open Count of CVEs for the last 2 days, week, month and year
            cve_report = self.get_open_cves_count(updated_on)

            # Add false positives PRs from yesterday
            cve_report['github_stats']['false_positives'] = self.get_fp_cves_count(updated_on)

            # Create CVE Ingestion Report
            cves_from_github = self.get_cveids_from_cvedb_prs(updated_on)
            ingested_cves, missed_cves = self.validate_cveids_in_graph(cves_from_github)
            cve_report['ingestion'] = {'ingested': ingested_cves, 'missed': missed_cves}

            return cve_report

        except (ValueError, TypeError, AssertionError) as e:
            logger.error('%r' % e)
            return None
