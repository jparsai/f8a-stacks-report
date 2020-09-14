"""Tests for classes from s3_helper module."""

from f8a_report.helpers.s3_helper import S3Helper
from moto import mock_s3
import boto3
import os

BUCKET = os.environ.get('MANIFESTS_BUCKET')
AWS_KEY = os.environ.get('AWS_S3_ACCESS_KEY_ID')
AWS_SECRET = os.environ.get('AWS_S3_SECRET_ACCESS_KEY')


def test_s3_helper():
    """Test to validate the s3_helper constructor function."""
    assert S3Helper()


def test_s3_client():
    """Test to validate the s3 client method."""
    S3 = S3Helper(aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    s3 = S3.s3_client(BUCKET)
    assert s3


@mock_s3
def test_store_json_content():
    """Test to validate store_json method."""
    s3 = boto3.resource('s3')
    s3.create_bucket(Bucket=BUCKET)
    S3 = S3Helper(aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    S3.store_json_content({"keyA": "valueB"}, BUCKET, 'dummy.json')


@mock_s3
def test_read_json_object():
    """Test to validate read_json method."""
    s3 = boto3.resource('s3')
    s3.create_bucket(Bucket=BUCKET)
    S3 = S3Helper(aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    s3.meta.client.upload_file('tests/data/data.json', BUCKET, 'data.json')
    data = S3.read_json_object(BUCKET, 'data.json')
    assert data.get("key1") == "value1"
    data = S3.read_json_object('dummy', 'data.json')
    assert data is None


@mock_s3
def test_list_objects():
    """Test to validate list_object method."""
    s3 = boto3.resource('s3')
    s3.create_bucket(Bucket=BUCKET)
    S3 = S3Helper(aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    s3.meta.client.upload_file('tests/data/dev/weekly/data.json', BUCKET, 'dev/weekly/data.json')
    obj = S3.list_objects(BUCKET, 'weekly')
    assert len(obj['objects']) > 0
    data = S3.list_objects('dummy', 'weekly')
    assert len(data['objects']) == 0


@mock_s3
def test_store_file_object():
    """Test to validate list_object method."""
    s3 = boto3.client('s3')
    s3.create_bucket(Bucket=BUCKET)
    S3 = S3Helper(aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    S3.store_file_object('tests/data/dev/weekly/data.json', BUCKET, 'dev/weekly/data.json')
    obj = S3.list_objects(BUCKET, 'weekly')
    assert len(obj['objects']) > 0
