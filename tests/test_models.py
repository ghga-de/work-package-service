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

"""Test the creation of dataclasses and DTOs"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from wps.core.models import (
    DownloadWorkOrder,
    WorkPackage,
    WorkPackageCreationData,
    WorkPackageType,
    WOTWorkType,
)

from .fixtures.crypt import user_public_crypt4gh_key


def test_work_order_token():
    """Test instantiating a work order token model."""
    token = DownloadWorkOrder(
        work_type=WOTWorkType.DOWNLOAD,
        file_id="some-file-id",
        user_public_crypt4gh_key="some-public-key",
    )
    assert token.file_id == "some-file-id"

    with pytest.raises(ValueError):
        token = DownloadWorkOrder(
            work_type="upload",  # type: ignore
            file_id="some_file_id",
            user_public_crypt4gh_key="some-public-key",
        )


def test_good_creation_data():
    """Test instantiating valid work package creation DTO."""
    data = WorkPackageCreationData(
        dataset_id="some-dataset-id",
        type=WorkPackageType.DOWNLOAD,
        file_ids=["some-file-id", "another-file-id"],
        user_public_crypt4gh_key=user_public_crypt4gh_key,
    )
    assert data.dataset_id == "some-dataset-id"
    assert data.type == WorkPackageType.DOWNLOAD
    assert data.file_ids == ["some-file-id", "another-file-id"]
    assert data.user_public_crypt4gh_key == user_public_crypt4gh_key

    wrapped_key = (
        "\n\n-----BEGIN CRYPT4GH PUBLIC KEY-----\n"
        + user_public_crypt4gh_key
        + "\n-----END CRYPT4GH PUBLIC KEY-----\n\n"
    )
    data = WorkPackageCreationData(
        dataset_id="123-foo-456",
        type=WorkPackageType.UPLOAD,
        file_ids=None,
        user_public_crypt4gh_key=wrapped_key,
    )
    assert data.dataset_id == "123-foo-456"
    assert data.type == WorkPackageType.UPLOAD
    assert data.file_ids is None
    assert data.user_public_crypt4gh_key == user_public_crypt4gh_key


def test_bad_creation_data():
    """Test instantiating invalid work package creation DTO."""
    with pytest.raises(ValidationError, match="dataset_id"):
        WorkPackageCreationData(
            dataset_id=["foo", "bar"],  # type: ignore
            type=WorkPackageType.DOWNLOAD,
            file_ids=["some-file-id", "another-file-id"],
            user_public_crypt4gh_key=user_public_crypt4gh_key,
        )
    with pytest.raises(ValidationError, match="type"):
        WorkPackageCreationData(
            dataset_id="some-dataset-id",
            type="UNKNOWN_TYPE",  # type: ignore
            file_ids=["some-file-id", "another-file-id"],
            user_public_crypt4gh_key=user_public_crypt4gh_key,
        )
    with pytest.raises(ValidationError, match="file_ids"):
        WorkPackageCreationData(
            dataset_id="some-dataset-id",
            type=WorkPackageType.DOWNLOAD,
            file_ids="some-file-id",  # type: ignore
            user_public_crypt4gh_key=user_public_crypt4gh_key,
        )
    with pytest.raises(ValidationError, match="user_public_crypt4gh_key"):
        WorkPackageCreationData(
            dataset_id="some-dataset-id",
            type=WorkPackageType.DOWNLOAD,
            file_ids=["some-file-id", "another-file-id"],
            user_public_crypt4gh_key="foo",
        )


TEST_ID = UUID("edd537d0-0b94-4305-bfe0-99863aa63998")


def test_work_package():
    """Test instantiating a work package DTO."""
    package = WorkPackage(
        id=TEST_ID,
        user_id=uuid4(),
        dataset_id="some-dataset-id",
        type=WorkPackageType.DOWNLOAD,
        files={"some-file-id": ".sam", "another-file-id": ".bam"},
        user_public_crypt4gh_key=user_public_crypt4gh_key,
        full_user_name="Dr. John Doe",
        email="john@home.org",
        token_hash="308eda9daf26b7446b284449a5895ab9a04ff30c129d4454e471cfb81bf5557d",
        created=datetime(2022, 2, 2, 2, tzinfo=UTC),  # pyright: ignore
        expires=datetime(2022, 2, 2, 3, tzinfo=UTC),  # pyright: ignore
    )
    assert package.id == TEST_ID
    assert package.full_user_name == "Dr. John Doe"
    assert package.files["another-file-id"] == ".bam"
    assert (package.expires - package.created).seconds == 60 * 60
