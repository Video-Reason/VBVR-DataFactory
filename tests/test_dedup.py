"""Unit tests for DedupChecker (DynamoDB conditional put logic)."""

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from vbvrdatafactory.core.dedup import DedupChecker

TABLE_NAME = "vbvr-param-hash"
REGION = "us-east-2"


@pytest.fixture
def ddb_table():
    """Create a mocked DynamoDB table and return the DedupChecker."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "generator_name", "KeyType": "HASH"},
                {"AttributeName": "param_hash", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "generator_name", "AttributeType": "S"},
                {"AttributeName": "param_hash", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        checker = DedupChecker(TABLE_NAME, REGION)
        yield checker, dynamodb.Table(TABLE_NAME)


class TestCheckAndRegister:
    """Tests for DedupChecker.check_and_register."""

    def test_unique_hash_returns_true(self, ddb_table):
        checker, table = ddb_table
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000") is True

    def test_unique_hash_is_persisted(self, ddb_table):
        checker, table = ddb_table
        checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000")

        resp = table.get_item(Key={"generator_name": "gen-1", "param_hash": "abcd1234abcd1234"})
        item = resp["Item"]
        assert item["sample_id"] == "sample_0000"

    def test_duplicate_hash_different_sample_returns_false(self, ddb_table):
        checker, table = ddb_table
        # First registration
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000") is True
        # Same hash, different sample → duplicate
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0001") is False

    def test_same_hash_same_sample_returns_true(self, ddb_table):
        """Lambda retry scenario: same sample_id re-registers → should return True."""
        checker, table = ddb_table
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000") is True
        # Lambda retry: same sample_id
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000") is True

    def test_same_hash_different_generator_is_independent(self, ddb_table):
        checker, table = ddb_table
        assert checker.check_and_register("gen-1", "abcd1234abcd1234", "sample_0000") is True
        # Different generator, same hash → should be independent
        assert checker.check_and_register("gen-2", "abcd1234abcd1234", "sample_0000") is True

    def test_multiple_hashes_same_generator(self, ddb_table):
        checker, table = ddb_table
        assert checker.check_and_register("gen-1", "aaaa1111aaaa1111", "sample_0000") is True
        assert checker.check_and_register("gen-1", "bbbb2222bbbb2222", "sample_0001") is True
        assert checker.check_and_register("gen-1", "aaaa1111aaaa1111", "sample_0002") is False
        assert checker.check_and_register("gen-1", "bbbb2222bbbb2222", "sample_0003") is False


class TestIsOwnedBy:
    """Tests for _is_owned_by (Lambda retry detection)."""

    def test_owned_by_same_sample(self, ddb_table):
        checker, table = ddb_table
        table.put_item(Item={
            "generator_name": "gen-1",
            "param_hash": "hash1",
            "sample_id": "sample_0000",
        })
        assert checker._is_owned_by("gen-1", "hash1", "sample_0000") is True

    def test_owned_by_different_sample(self, ddb_table):
        checker, table = ddb_table
        table.put_item(Item={
            "generator_name": "gen-1",
            "param_hash": "hash1",
            "sample_id": "sample_0000",
        })
        assert checker._is_owned_by("gen-1", "hash1", "sample_0001") is False

    def test_item_not_found(self, ddb_table):
        """If item was deleted between conditional put and get_item."""
        checker, table = ddb_table
        assert checker._is_owned_by("gen-1", "nonexistent", "sample_0000") is False
