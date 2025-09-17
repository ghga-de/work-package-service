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

"""Test the tokens module."""

from uuid import UUID, uuid4

import pytest
from ghga_service_commons.utils.jwt_helpers import (
    decode_and_validate_token,
    generate_jwk,
)

from wps.core.models import (
    BaseWorkOrderToken,
    CreateFileWorkOrder,
    DownloadWorkOrder,
    UploadFileWorkOrder,
)
from wps.core.tokens import (
    generate_work_package_access_token,
    hash_token,
    sign_work_order_token,
)

USER_ID = UUID("32a19d10-2d9b-420d-93f8-1206559c6cb2")


def test_generate_work_package_access_token():
    """Test the generation of a work package access token."""
    token = generate_work_package_access_token()
    assert len(token) == 24
    assert token.isascii()
    assert token.isalnum()
    another_token = generate_work_package_access_token()
    assert len(another_token) == len(token)
    assert another_token.isascii()
    assert another_token.isalnum()
    assert another_token != token


def test_hash_token():
    """Test hashing of tokens."""
    token = "abc123" * 4
    hashed_token = hash_token(token)
    assert 16 <= len(hashed_token) <= 64
    assert hashed_token.isascii()
    hashed_again_token = hash_token(token)
    assert hashed_again_token == hashed_token
    another_token = "123abc" * 4
    hashed_another_token = hash_token(another_token)
    assert hashed_another_token != hashed_token


@pytest.mark.parametrize(
    "work_order_token",
    [
        DownloadWorkOrder(
            work_type="download",
            file_id="some-file-id",
            user_public_crypt4gh_key="some-public-key",
        ),
        CreateFileWorkOrder(
            work_type="create",
            box_id=uuid4(),
            alias="file1",
            user_public_crypt4gh_key="some-public-key",
        ),
        UploadFileWorkOrder(
            work_type="upload",
            box_id=uuid4(),
            file_id=uuid4(),
            user_public_crypt4gh_key="some-public-key",
        ),
    ],
)
def test_sign_work_order_token(work_order_token: BaseWorkOrderToken):
    """Test signing of work order tokens."""
    key = generate_jwk()
    token_str = sign_work_order_token(work_order_token=work_order_token, key=key)
    assert isinstance(token_str, str)
    assert len(token_str) > 80
    assert token_str.count(".") == 2
    token_chars = token_str.replace(".", "").replace("-", "").replace("_", "")
    assert token_chars.isalnum()
    assert token_chars.isascii()
    token_dict = decode_and_validate_token(token_str, key)
    assert isinstance(token_dict, dict)
    assert token_dict.pop("exp") - token_dict.pop("iat") == 30
    expected_token_dict = work_order_token.model_dump(mode="json")
    assert token_dict == expected_token_dict
