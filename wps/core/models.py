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

"""Defines dataclasses for business-logic data as well as request/reply models for use
in the API."""

from dataclasses import dataclass
from enum import Enum

from ghga_service_commons.utils.utc_dates import DateTimeUTC
from pydantic import BaseModel, EmailStr, Field

__all__ = [
    "WorkType",
    "WorkOrderToken",
    "WorkPackageCreationData",
    "WorkPackageData",
    "WorkPackage",
]


class BaseDto(BaseModel):
    """Base model preconfigured for use as Dto."""

    class Config:  # pylint: disable=missing-class-docstring
        extra = "forbid"
        frozen = True


class WorkType(str, Enum):
    """The type of work that a work package describes."""

    DOWNLOAD = "download"
    UPLOAD = "upload"


@dataclass(frozen=True)
class WorkOrderToken:
    """A class describing the payload of a work order token."""

    type: WorkType
    file_id: str
    user_id: str
    public_key: str
    full_user_name: str
    email: str


class WorkPackageCreationData(BaseDto):
    """
    All data necessary to create a work package.
    """

    user_id: str = Field(default=..., title="ID od the user")
    dataset_id: str = Field(default=..., title="ID of the dataset")
    type: WorkType = Field(default=..., title="Work type")
    file_ids: list[str] = Field(default=..., title="IDs of all included files")
    public_c4gh_user_key: str = Field(
        default=...,
        description="The user's public Crpyt4GH key in base64 encoding",
    )


class WorkPackageData(WorkPackageCreationData):
    """
    All data that describes a work package.
    """

    full_user_name: str = Field(
        default=...,
        title="Full name of the user",
        description="The user's full name including academic title",
    )
    email: EmailStr = Field(default=..., title="E-Mail of the user")
    token_hash: str = Field(
        default=...,
        title="Hash of thhe token",
        description="Hash of the workpackage access token",
    )
    file_extensions: dict[str, str] = Field(
        default=...,
        title="File extensions",
        description="Mapping from file ids to file extensions",
    )
    created: DateTimeUTC = Field(default=None, title="Date of creation")
    expires: DateTimeUTC = Field(default=None, title="Date of expiry")


class WorkPackage(WorkPackageData):
    """
    A work package including a unique identifier.
    """

    id: str = Field(default=..., title="ID of the work package")
