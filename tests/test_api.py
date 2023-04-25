# Copyright 2021 - 2023 Universität Tübingen, DKFZ, EMBL, and Universität zu Köln
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

from fastapi import status
from ghga_service_commons.utils.jwt_helpers import decode_and_validate_token
from hexkit.providers.akafka.testutils import (  # noqa: F401 # pylint: disable=unused-import
    kafka_fixture,
)
from hexkit.providers.mongodb.testutils import (  # noqa: F401 # pylint: disable=unused-import
    mongodb_fixture,
)
from httpx import AsyncClient
from pytest import mark
from pytest_httpx import HTTPXMock

from .fixtures import (  # noqa: F401 # pylint: disable=unused-import
    SIGNING_KEY_PAIR,
    fixture_auth_headers,
    fixture_bad_auth_headers,
    fixture_client,
    fixture_container,
    headers_for_token,
    non_mocked_hosts,
)
from .fixtures.crypt import decrypt, user_public_crypt4gh_key
from .fixtures.datasets import DATASET

CREATION_DATA = {
    "dataset_id": "some-dataset-id",
    "type": "download",
    "file_ids": ["file-id-1", "file-id-3", "file-id-5"],
    "user_public_crypt4gh_key": user_public_crypt4gh_key,
}


@mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test that the health check endpoint works."""

    response = await client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "OK"}


@mark.asyncio
async def test_create_work_package_unauthorized(
    client: AsyncClient, bad_auth_headers: dict[str, str]
):
    """Test that creating a work package needs authorization."""

    response = await client.post("/work-packages", json=CREATION_DATA)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = await client.post(
        "/work-packages", json=CREATION_DATA, headers=bad_auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@mark.asyncio
async def test_get_work_package_unauthorized(client: AsyncClient):
    """Test that getting a work package needs authorization."""

    response = await client.get("/work-packages/some-work-package-id")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@mark.asyncio
async def test_create_work_order_token(
    client: AsyncClient, auth_headers: dict[str, str], httpx_mock: HTTPXMock
):
    """Test that work order tokens can be properly created."""

    # mock the access check for the test dataset

    httpx_mock.add_response(
        method="GET",
        url="http://access/users/john-doe@ghga.de/datasets/some-dataset-id",
        text="true",
    )

    # create a work package

    response = await client.post(
        "/work-packages", json=CREATION_DATA, headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert isinstance(response_data, dict)
    assert sorted(response_data) == ["id", "token"]

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

    # try to get a non-existing work package with authorization

    response = await client.get(
        "/work-packages/some-work-package-id", headers=headers_for_token(token)
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
        "/work-packages/some-bad-id/files/file-id-1/work-order-tokens",
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

    token = response.json()
    assert isinstance(token, str)

    # decrypt the work order token

    assert token and isinstance(token, str) and token.isascii()
    token = decrypt(token)

    # validate the work order token

    assert isinstance(token, str)
    assert len(token) > 80
    assert token.count(".") == 2
    token_chars = token.replace(".", "").replace("-", "").replace("_", "")
    assert token_chars.isalnum()
    assert token_chars.isascii()
    token_dict = decode_and_validate_token(token, SIGNING_KEY_PAIR.public())

    # check the content of the work order token

    assert isinstance(token_dict, dict)
    assert token_dict.pop("exp") - token_dict.pop("iat") == 30
    assert token_dict == {
        "type": "download",
        "file_id": "file-id-3",
        "file_ext": ".bam",
        "user_id": "john-doe@ghga.de",
        "user_public_crypt4gh_key": user_public_crypt4gh_key,
        "full_user_name": "Dr. John Doe",
        "email": "john@home.org",
    }


@mark.asyncio
async def test_get_datasets_unauthenticated(client: AsyncClient):
    """Test that the list of accessible datasets can be fetched unauthenticated."""

    response = await client.get("/datasets")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@mark.asyncio
async def test_get_datasets_when_none_authorized(
    client: AsyncClient, auth_headers: dict[str, str], httpx_mock: HTTPXMock
):
    """Test that no datasets are fetched when none are accessible."""

    # mock the access check for the test dataset

    httpx_mock.add_response(
        method="GET",
        url="http://access/users/john-doe@ghga.de/datasets",
        json=["some-other-dataset-id"],
    )

    # get the list of datasets

    response = await client.get("/datasets", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert isinstance(response_data, list)
    assert response_data == []


@mark.asyncio
async def test_get_datasets(
    client: AsyncClient, auth_headers: dict[str, str], httpx_mock: HTTPXMock
):
    """Test that the list of accessible datasets can be fetched."""

    # mock the access check for the test dataset

    httpx_mock.add_response(
        method="GET",
        url="http://access/users/john-doe@ghga.de/datasets",
        json=["some-dataset-id", "some-non-existing-dataset-id"],
    )

    # get the list of datasets

    response = await client.get("/datasets", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert isinstance(response_data, list)
    assert response_data == [DATASET]
