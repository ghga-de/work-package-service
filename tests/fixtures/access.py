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

from wps.ports.outbound.http import AccessCheckPort

USERS_WITH_DOWNLOAD_ACCESS = ["john-doe@ghga.de"]
DATASETS_WITH_DOWNLOAD_ACCESS = ["some-dataset-id"]

__all__ = ["AccessCheckMock"]


class AccessCheckMock(AccessCheckPort):
    """Mock checking dataset access pemisions."""

    async def check_download_access(self, user_id: str, dataset_id: str) -> bool:
        return (
            user_id in USERS_WITH_DOWNLOAD_ACCESS
            and dataset_id in DATASETS_WITH_DOWNLOAD_ACCESS
        )

    async def get_datasets_with_download_access(self, user_id: str) -> list[str]:
        return (
            list(DATASETS_WITH_DOWNLOAD_ACCESS)
            if user_id in USERS_WITH_DOWNLOAD_ACCESS
            else []
        )
