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

"""Outbound HTTP calls """

import httpx
from pydantic import BaseSettings, Field

from wps.ports.outbound.http import AccessCheckPort

__all__ = ["AccessCheckConfig", "AccessCheckAdapter"]

TIMEOUT = 60


class AccessCheckConfig(BaseSettings):
    """Config parameters for checking dataset access."""

    download_access_url: str = Field(
        ...,
        example="http://127.0.0.1/download_access",
        description="URL pointing to the internal download access API.",
    )


class AccessCheckAdapter(AccessCheckPort):
    """An adapter for checking access permissions for datasets."""

    def __init__(self, *, config: AccessCheckConfig):
        """Configure the access adadapter."""
        self._url = config.download_access_url

    async def check_download_access(self, user_id: str, dataset_id: str) -> bool:
        """Check whether the given user has download access for the given dataset."""
        url = f"{self._url}/users/{user_id}/datasets/{dataset_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=TIMEOUT)
        return response.status_code == 200 and response.json() is True

    async def get_datasets_with_download_access(self, user_id: str) -> list[str]:
        """Get all datasets that the given user is allowed to download."""
        url = f"{self._url}/users/{user_id}/datasets"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=TIMEOUT)
        return response.json() if response.status_code == 200 else []
