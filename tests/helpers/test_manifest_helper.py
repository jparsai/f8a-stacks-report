"""Tests for classes from Manifests helper module."""

from moto import mock_s3
import boto3
from f8a_report.helpers.manifest_helper import GetReport, FilterStacks, manifest_interface
from unittest import mock
import json
import os

BUCKET = os.environ.get('MANIFESTS_BUCKET')
AWS_KEY = os.environ.get('AWS_S3_ACCESS_KEY_ID')
AWS_SECRET = os.environ.get('AWS_S3_SECRET_ACCESS_KEY')
get_report = GetReport()

with open("tests/data/manifests.json") as myfile:
    stack_report = json.load(myfile)


def test_manifests_helper():
    """Test to validate the manifest_helper constructor function."""
    assert get_report


@mock.patch('f8a_report.helpers.manifest_helper.GetReport.save_manifest_to_s3')
def test_generate_manifest_for_pypi(_mock1):
    """Test to validate the generate_manifest_for_pypi method."""
    data = [stack_report[2][0]['manifest']]
    pypi_obj = get_report.generate_manifest_for_pypi(data)
    assert pypi_obj


@mock.patch('f8a_report.helpers.manifest_helper.GetReport.save_manifest_to_s3')
def test_generate_manifest_for_npm(_mock1):
    """Test to validate the generate_manifest_for npm method."""
    data = [json.loads(stack_report[0][0]['manifest'][0]['content'])]
    npm_obj = get_report.generate_manifest_for_npm(data)
    assert npm_obj


@mock.patch('f8a_report.helpers.manifest_helper.GetReport.save_manifest_to_s3')
def test_generate_manifest_for_maven(_mock1):
    """Test to validate the generate_manifest_for_maven method."""
    data = stack_report[-2][0]['manifest']
    maven_obj = get_report.generate_manifest_for_maven(data)
    assert maven_obj


@mock_s3
@mock.patch('f8a_report.helpers.s3_helper.S3Helper.store_file_object')
def test_save_manifest_to_s3(_mock1):
    """Test to validate the save manifests to s3 method."""
    s3 = boto3.resource('s3')
    s3.create_bucket(Bucket=BUCKET)
    get_report.s3.manifests_bucket = BUCKET
    save_obj = get_report.save_manifest_to_s3(
        file_name='data.json', file_path='tests/data/dev/weekly/data.json')
    assert save_obj is None


def test_clean_stacks():
    """Test to validate the clean_stacks method."""
    fs = FilterStacks()
    data = stack_report[0][0]['manifest']
    f_obj = fs.clean_stacks(data)
    assert f_obj


def test_filter_stack_on_size():
    """Test to validate the filter_on_size method."""
    fs = FilterStacks()
    f_obj = fs.filter_stacks_on_size(stack_report, 1)
    assert f_obj


@mock.patch('f8a_report.helpers.manifest_helper.FilterStacks.filter_stacks_on_ecosystem')
def test_manifests_interface(_mock1):
    """Test to validate the manifests interface method."""
    mi = manifest_interface(stack_report, 1)
    assert mi


@mock.patch('f8a_report.helpers.manifest_helper.FilterStacks.filter_stacks_on_size')
@mock.patch('f8a_report.helpers.manifest_helper.FilterStacks.clean_stacks')
@mock.patch('f8a_report.helpers.manifest_helper.GetReport.generate_manifest_for_npm')
@mock.patch('f8a_report.helpers.manifest_helper.GetReport.generate_manifest_for_maven')
@mock.patch('f8a_report.helpers.manifest_helper.GetReport.generate_manifest_for_pypi')
def test_filter_stacks_on_ecosystem(_mock1, _mock2, _mock3, _mock4, _mock5):
    """Test to validate the filter stacks on ecosystem method."""
    fs = FilterStacks()
    f_obj = fs.filter_stacks_on_ecosystem(stack_report, 1)
    assert f_obj is None
