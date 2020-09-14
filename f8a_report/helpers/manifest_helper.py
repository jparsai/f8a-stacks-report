"""Dynamic Generation of Manifest files."""

import random
import json
from helpers.s3_helper import S3Helper
import logging
import os
import re
from json import JSONDecodeError

logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


class GetReport:
    """This creates a manifest file for all ecosystem and save to s3."""

    def __init__(self):
        """Init method for the Report helper class."""
        self.s3 = S3Helper()
        self.curr_dir = os.path.join(
            '/tmp', "dynamic_manifests")
        if not os.path.exists(self.curr_dir):
            os.makedirs(self.curr_dir)

    def generate_manifest_for_pypi(self, stack_report):
        """Generate manifest file for pypi."""
        logger.info('Generating Manifest for Pypi executed')
        file_name = "pylist.json"
        file_path = os.path.join(self.curr_dir, file_name)
        with open(file_path, 'w') as manifest:
            json.dump(stack_report, manifest)
        return self.save_manifest_to_s3(file_path=file_path, file_name=file_name)

    def generate_manifest_for_npm(self, stack_report):
        """Generate manifest file for npm."""
        logger.info('Generating manifest for NPM executed')
        file_name = "npmlist.json"
        file_path = os.path.join(self.curr_dir, file_name)
        with open(file_path, 'w') as manifest:
            json.dump(stack_report, manifest)
        return self.save_manifest_to_s3(file_path=file_path, file_name=file_name)

    def generate_manifest_for_maven(self, stack_report):
        """Generate manifest file for maven."""
        logger.info('Generate Manifest for Maven executed')
        file_name = "dependencies.json"
        file_path = os.path.join(self.curr_dir, file_name)
        new_stack = [{'content': e.pop('content')} for e in stack_report]
        with open(file_path, 'w') as manifest:
            json.dump(new_stack, manifest)
        return self.save_manifest_to_s3(file_path=file_path, file_name=file_name)

    def save_manifest_to_s3(self, file_path, file_name):
        """Save Generated manifest file to S3."""
        manifest_file_key = f'dynamic_manifests/{file_name}'
        self.s3.store_file_object(file_path=file_path,
                                  bucket_name=self.s3.manifests_bucket,
                                  file_name=manifest_file_key)


class FilterStacks:
    """This filters a Manifest file from collated stack report."""

    def filter_stacks_on_ecosystem(self, stack_report, stack_size):
        """Filter Stack Report on ecosystem."""
        logger.info('Filtering Stacks on ecosystem executed')
        npm_stack_data = []
        pypi_stack_data = []
        maven_stack_data = []
        get_report = GetReport()
        for stack in stack_report:
            data = stack[0]['manifest'][0]
            if data['ecosystem'] == 'npm':
                npm_stack_data.append(data)
                continue
            if data['ecosystem'] == 'pypi':
                pypi_stack_data.append(data)
                continue
            if data['ecosystem'] == 'maven':
                maven_stack_data.append(data)
                continue
        if npm_stack_data:
            npm_stack_data = self.filter_stacks_on_size(npm_stack_data, stack_size)
            npm_stack_data = self.clean_stacks(npm_stack_data)
            get_report.generate_manifest_for_npm(npm_stack_data)
        if maven_stack_data:
            maven_stack_data = self.filter_stacks_on_size(maven_stack_data, stack_size)
            get_report.generate_manifest_for_maven(maven_stack_data)
        if pypi_stack_data:
            pypi_stack_data = self.filter_stacks_on_size(pypi_stack_data, stack_size)
            pypi_stack_data = self.clean_stacks(pypi_stack_data)
            get_report.generate_manifest_for_pypi(pypi_stack_data)

    @staticmethod
    def filter_stacks_on_size(stack_report, stack_size):
        """Filter Stack Report on size and convert into dict."""
        logger.info('Filtering Stacks on size Executed')
        return random.sample(stack_report, min(len(stack_report), stack_size))

    @staticmethod
    def clean_stacks(sampled_stack_reports):
        """Remove Spaces and Tabs from Json Data."""
        try:
            return [json.loads(re.sub(r'\s+', ' ', stack_report['content']))
                    for stack_report in sampled_stack_reports]
        except JSONDecodeError:
            return [re.sub(r'\s+', ' ', stack_report['content'])
                    for stack_report in sampled_stack_reports]


def manifest_interface(stack_report, stack_size=3):
    """Initialize function, executed first."""
    return FilterStacks().filter_stacks_on_ecosystem(
        stack_report=stack_report, stack_size=stack_size)
