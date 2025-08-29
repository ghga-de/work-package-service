# Copyright 2021 - 2025 Universität Tübingen, DKFZ, EMBL, and Universität zu Köln
# for the German Human Genome-Phenome Archive (GHGA)
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
#

"""Test the API of the work package service."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import status
from ghga_service_commons.api.testing import AsyncTestClient
from ghga_service_commons.utils.jwt_helpers import decode_and_validate_token
from ghga_service_commons.utils.utc_dates import now_as_utc
from hexkit.providers.mongodb.testutils import MongoDbFixture
from pytest_httpx import HTTPXMock

from wps.config import Config
from wps.constants import WORK_ORDER_TOKEN_VALID_SECONDS
from wps.core.models import DatasetWithExpiration

from .fixtures import (  # noqa: F401
    SIGNING_KEY_PAIR,
    fixture_auth_headers,
    fixture_bad_auth_headers,
    fixture_client,
    fixture_config,
    fixture_repository,
    headers_for_token,
    non_mocked_hosts,
)
from .fixtures.crypt import decrypt, user_public_crypt4gh_key
from .fixtures.datasets import DATASET

pytestmark = pytest.mark.asyncio()


CREATION_DATA = {
    "dataset_id": "some-dataset-id",
    "type": "download",
    "file_ids": ["file-id-1", "file-id-3", "file-id-5"],
    "user_public_crypt4gh_key": user_public_crypt4gh_key,
}

TIMEOUT = 5


async def test_health_check(client: AsyncTestClient):
    """Test that the health check endpoint works."""
    response = await client.get("/health", timeout=TIMEOUT)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "OK"}


async def test_create_work_package_unauthorized(
    client: AsyncTestClient, bad_auth_headers: dict[str, str]
):
    """Test that creating a work package needs authorization."""
    response = await client.post("/work-packages", json=CREATION_DATA)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = await client.post(
        "/work-packages", json=CREATION_DATA, headers=bad_auth_headers
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_get_work_package_unauthorized(client: AsyncTestClient):
    """Test that getting a work package needs authorization."""
    response = await client.get("/work-packages/some-work-package-id")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
async def test_create_work_order_token(
    client: AsyncTestClient,
    auth_headers: dict[str, str],
    httpx_mock: HTTPXMock,
    mongodb_populated: MongoDbFixture,
    config: Config,
):
    """Test that work order tokens can be properly created."""
    # mock the access check for the test dataset to grant access

    valid_until = (now_as_utc() + timedelta(days=365)).isoformat()
    httpx_mock.add_response(
        method="GET",
        url="http://access/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets/some-dataset-id",
        json=valid_until,
    )

    # create a work package

    response = await client.post(
        "/work-packages", json=CREATION_DATA, headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert isinstance(response_data, dict)
    assert sorted(response_data) == ["expires", "id", "token"]

    valid_timedelta = datetime.fromisoformat(response_data["expires"]) - now_as_utc()
    valid_days = round((valid_timedelta).total_seconds() / (24 * 60 * 60))

    assert valid_days == config.work_package_valid_days
    work_package_id = response_data["id"]
    assert (
        work_package_id
        and isinstance(work_package_id, str)
        and work_package_id.isascii()
    )

    token = response_data["token"]
    assert token and isinstance(token, str) and token.isascii()
    token = decrypt(token)
    assert token.isalnum() and len(token) == 24

    # try to get the work package without authorization

    response = await client.get(f"/work-packages/{work_package_id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # try to get a non-existing work package with authorization and malformed ID

    response = await client.get(
        "/work-packages/some-work-package-id", headers=headers_for_token(token)
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # try to get a non-existing work package with authorization
    response = await client.get(
        f"/work-packages/{uuid4()}", headers=headers_for_token(token)
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # get the proper work package with authorization

    response = await client.get(
        f"/work-packages/{work_package_id}", headers=headers_for_token(token)
    )
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert isinstance(response_data, dict)
    assert sorted(response_data) == [
        "created",
        "expires",
        "files",
        "type",
    ]

    assert response_data.pop("created") < response_data.pop("expires")
    assert response_data == {
        "type": "download",
        "files": {"file-id-1": ".json", "file-id-3": ".bam"},
    }

    # try to get a work order token without authorization

    response = await client.post(
        f"/work-packages/{work_package_id}/files/file-id-1/work-order-tokens"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # try to get a work order token for a non-existing work package with authorization

    response = await client.post(
        f"/work-packages/{uuid4()}/files/file-id-1/work-order-tokens",
        headers=headers_for_token(token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # try to get a work order token for a non-requested file with authorization

    response = await client.post(
        f"/work-packages/{work_package_id}/files/file-id-2/work-order-tokens",
        headers=headers_for_token(token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # try to get a work order token for a non-existing file with authorization

    response = await client.post(
        f"/work-packages/{work_package_id}/files/file-id-5/work-order-tokens",
        headers=headers_for_token(token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # get a work order token for an existing file with authorization

    response = await client.post(
        f"/work-packages/{work_package_id}/files/file-id-3/work-order-tokens",
        headers=headers_for_token(token),
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert "Cache-Control" in response.headers
    cache_control = response.headers["Cache-Control"]
    assert cache_control == f"max-age={WORK_ORDER_TOKEN_VALID_SECONDS}, private"

    wot = response.json()
    assert isinstance(wot, str)

    # decrypt the work order token

    assert wot and isinstance(wot, str) and wot.isascii()
    wot = decrypt(wot)

    # validate the work order token

    assert isinstance(wot, str)
    assert len(wot) > 80
    assert wot.count(".") == 2
    wot_chars = wot.replace(".", "").replace("-", "").replace("_", "")
    assert wot_chars.isalnum()
    assert wot_chars.isascii()
    wot_dict = decode_and_validate_token(wot, SIGNING_KEY_PAIR.public())

    # check the content of the work order token

    assert isinstance(wot_dict, dict)
    assert wot_dict.pop("exp") - wot_dict.pop("iat") == 30
    assert wot_dict == {
        "work_type": "download",
        "file_id": "file-id-3",
        "user_id": "a86f8281-e18a-429e-88a9-a5c8ea0cf754",
        "user_public_crypt4gh_key": user_public_crypt4gh_key,
        "full_user_name": "Dr. John Doe",
        "email": "john@home.org",
    }

    # mock the access check for the test dataset to revoke access
    httpx_mock.add_response(
        method="GET",
        url="http://access/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets/some-dataset-id",
        text="false",
    )

    # try to fetch a work order token again

    response = await client.post(
        f"/work-packages/{work_package_id}/files/file-id-3/work-order-tokens",
        headers=headers_for_token(token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Download access has been revoked" in response.json()["detail"]


async def test_get_datasets_unauthenticated(client: AsyncTestClient):
    """Test that the list of accessible datasets cannot be fetched unauthenticated."""
    response = await client.get("/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_datasets_for_another_user(
    client: AsyncTestClient, auth_headers: dict[str, str]
):
    """Test that the list of accessible datasets for another user cannot be fetched."""
    response = await client.get(
        "/users/78b1c9a5-eb59-4e49-9330-9ffdd2b161ef/datasets", headers=auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_datasets_when_none_authorized(
    client: AsyncTestClient,
    auth_headers: dict[str, str],
    httpx_mock: HTTPXMock,
    mongodb_populated: MongoDbFixture,
):
    """Test that no datasets are fetched when none are accessible."""
    # mock the access check for the test dataset

    expires = (now_as_utc() + timedelta(days=365)).isoformat()
    httpx_mock.add_response(
        method="GET",
        url="http://access/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets",
        json={"some-other-dataset-id": expires},
    )

    # get the list of datasets

    response = await client.get(
        "/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert isinstance(response_data, list)
    assert response_data == []


async def test_get_datasets(
    client: AsyncTestClient,
    auth_headers: dict[str, str],
    httpx_mock: HTTPXMock,
    mongodb_populated: MongoDbFixture,
):
    """Test that the list of accessible datasets can be fetched."""
    # mock the access check for the test dataset

    expires = (now_as_utc() + timedelta(days=365)).isoformat()
    httpx_mock.add_response(
        method="GET",
        url="http://access/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets",
        json={
            "some-dataset-id": expires,
            "some-non-existing-dataset-id": expires,
        },
    )

    # get the list of datasets

    response = await client.get(
        "/users/a86f8281-e18a-429e-88a9-a5c8ea0cf754/datasets", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1
    returned = response_data[0]
    expected = {**DATASET.model_dump(), "expires": expires}
    assert DatasetWithExpiration(**returned) == DatasetWithExpiration(**expected)
