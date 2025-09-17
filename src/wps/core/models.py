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

"""Defines dataclasses for business-logic data as well as request/reply models for use
in the API.
"""

from enum import StrEnum

from ghga_service_commons.utils.utc_dates import UTCDatetime
from hexkit.protocols.dao import UUID4Field
from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from wps.core.crypt import validate_public_key

__all__ = [
    "BaseWorkOrderToken",
    "CreateFileWorkOrder",
    "ResearchDataUploadBox",
    "UploadFileWorkOrder",
    "WorkOrderTokenRequest",
    "WorkOrderTokenResponse",
    "WorkPackage",
    "WorkPackageCreationData",
    "WorkPackageCreationResponse",
    "WorkPackageType",
    "WorkType",
]


class BaseDto(BaseModel):
    """Base model pre-configured for use as Dto."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkPackageType(StrEnum):
    """The type of work that a work package describes."""

    DOWNLOAD = "download"
    UPLOAD = "upload"


class DatasetFile(BaseDto):
    """A file as that is part of a dataset."""

    id: str = Field(..., description="The file ID.")
    extension: str = Field(..., description="The file extension with a leading dot.")


class Dataset(BaseDto):
    """A model describing a dataset."""

    id: str = Field(default=..., description="ID of the dataset")
    stage: WorkPackageType = Field(
        default=..., description="Current stage of this dataset."
    )
    title: str = Field(default=..., description="The title of the dataset.")
    description: str | None = Field(..., description="The description of the dataset.")
    files: list[DatasetFile] = Field(..., description="Files contained in the dataset.")


class DatasetWithExpiration(Dataset):
    """A model describing a dataset with an expiration date."""

    expires: UTCDatetime = Field(
        default=..., description="The expiration date of access to the dataset."
    )


class WorkType(StrEnum):
    """The type of work that a work order token authorizes."""

    CREATE = "create"
    UPLOAD = "upload"
    CLOSE = "close"
    DELETE = "delete"
    DOWNLOAD = "download"


class BaseWorkOrderToken(BaseModel):
    """Base model for work order tokens."""

    work_type: WorkType
    user_public_crypt4gh_key: str

    model_config = ConfigDict(frozen=True)


class DownloadWorkOrder(BaseWorkOrderToken):
    """WOT schema authorizing a user to download a file from a dataset"""

    file_id: str  # should be the file accession, as opposed to UUID4 used for uploads

    @field_validator("work_type")
    @classmethod
    def enforce_work_type(cls, work_type: str):
        """Make sure work type matches expectation"""
        if work_type != WorkType.DOWNLOAD:
            raise ValueError("Work type must be 'download'.")
        return work_type


class CreateFileWorkOrder(BaseWorkOrderToken):
    """WOT schema authorizing a user to create a new FileUpload"""

    alias: str
    box_id: UUID4

    @field_validator("work_type")
    @classmethod
    def enforce_work_type(cls, work_type):
        """Make sure work type matches expectation"""
        if work_type != WorkType.CREATE:
            raise ValueError("Work type must be 'create'.")
        return work_type


class UploadFileWorkOrder(BaseWorkOrderToken):
    """WOT schema authorizing a user to work with existing FileUploads"""

    file_id: UUID4
    box_id: UUID4

    @field_validator("work_type")
    @classmethod
    def enforce_work_type(cls, work_type):
        """Make sure work type matches expectation"""
        if work_type not in [WorkType.UPLOAD, WorkType.CLOSE, WorkType.DELETE]:
            raise ValueError("Work type must be 'upload', 'close', or 'delete'.")
        return work_type


# TODO: reference the event schema once this is moved there. for now, mark with '_'
class _ResearchDataUploadBoxState(StrEnum):
    """The allowed states for an ResearchDataUploadBox instance"""

    OPEN = "open"
    LOCKED = "locked"
    CLOSED = "closed"


class _ResearchDataUploadBox(BaseModel):
    """A class representing a ResearchDataUploadBox.

    Contains all fields from the FileUploadBox and shares IDs.
    """

    id: UUID4  # unique identifier for the instance
    file_upload_box_id: UUID4  # ID of the FileUploadBox in the UCS
    locked: bool = False  # Whether or not changes to the files in the box are allowed
    file_count: int = 0  # The number of files in the box
    size: int = 0  # The total size of all files in the box
    storage_alias: str  # Storage alias assigned to the FileUploadBox
    state: _ResearchDataUploadBoxState  # one of OPEN, LOCKED, CLOSED
    title: str  # short meaningful name for the box
    description: str  # describes the upload box in more detail
    last_changed: UTCDatetime
    changed_by: UUID4  # ID of the user who performed the latest change


class ResearchDataUploadBox(BaseDto):
    """A model describing an upload box that groups file uploads."""

    id: UUID4 = Field(
        ...,
        description="The ID of the full research data upload box."
        + " This is the ID tied to upload claims.",
    )
    file_upload_box_id: UUID4 = Field(
        ...,
        description="The ID of the file upload box. This is the ID referenced by the Connector.",
    )
    title: str = Field(..., description="The title of the upload box.")
    description: str | None = Field(
        None, description="The description of the upload box."
    )


class WorkPackageCreationData(BaseDto):
    """All data necessary to create a work package."""

    dataset_id: str | None = Field(
        default=None, description="ID of the dataset (for download work packages)"
    )
    box_id: UUID4 | None = Field(
        default=None, description="ID of the upload box (for upload work packages)"
    )
    type: WorkPackageType
    file_ids: list[str] | None = Field(
        default=None,
        description="IDs of all included files."
        " If None, all files of the dataset are assumed as target.",
    )
    user_public_crypt4gh_key: str = Field(
        default=...,
        description="The user's public Crypt4GH key in base64 encoding",
    )

    @field_validator("user_public_crypt4gh_key")
    @classmethod
    def user_public_crypt4gh_key_valid(cls, key: str):
        """Validate the user's public Crypt4GH key."""
        return validate_public_key(key)

    @model_validator(mode="after")
    def validate_ids(self):
        """Ensure exactly one of dataset_id or box_id is provided based on work type."""
        errors: list[str] = []
        if self.type == WorkPackageType.DOWNLOAD:
            if not self.dataset_id:
                errors.append("dataset_id is required for download work packages")
            if self.box_id:
                errors.append("box_id shouldn't be provided for download work packages")
        elif self.type == WorkPackageType.UPLOAD:
            if not self.box_id:
                errors.append("box_id is required for upload work packages")
            if self.dataset_id:
                errors.append(
                    "dataset_id shouldn't be provided for upload work packages"
                )
        if errors:
            raise ValueError("; ".join(errors))

        return self


class WorkPackageCreationResponse(BaseModel):
    """Response when a work package has been created."""

    id: str = Field(default=..., description="ID of the work package")
    token: str = Field(
        default=...,
        description="The work package access token,"
        " encrypted with the user's public Crypt4GH key",
    )
    expires: UTCDatetime = Field(
        default=..., description="The expiration date of the work package access token"
    )


class WorkPackageDetails(BaseModel):
    """Details about the work package that can be requested."""

    type: WorkPackageType
    files: dict[str, str] = Field(
        default=...,
        description="IDs of all included files mapped to their file extensions",
        examples=[{"file-id-1": ".json", "file-id-2": ".csv"}],
    )
    created: UTCDatetime = Field(
        default=..., description="Creation date of the work package"
    )
    expires: UTCDatetime = Field(
        default=..., title="Expiration date of the work package"
    )


class WorkPackage(WorkPackageDetails):
    """All data that describes a work package."""

    id: UUID4 = UUID4Field(description="ID of the work package")
    dataset_id: str | None = Field(
        default=None, description="ID of the dataset (for download work packages)"
    )
    box_id: UUID4 | None = Field(
        default=None, description="ID of the upload box (for upload work packages)"
    )
    user_id: UUID4
    full_user_name: str = Field(
        default=...,
        description="The user's full name including academic title",
    )
    email: EmailStr = Field(default=..., description="E-Mail address of the user")
    user_public_crypt4gh_key: str = Field(
        default=...,
        description="The user's public Crypt4GH key in base64 encoding",
    )
    token_hash: str = Field(
        default=...,
        description="Hash of the work package access token",
    )


class WorkOrderTokenRequest(BaseModel):
    """Request model for creating work order tokens."""

    work_type: WorkType = Field(
        ..., description="The type of work order token to create"
    )
    alias: str | None = Field(
        None, description="File alias (required for CREATE work type)"
    )
    file_id: UUID4 | None = Field(
        None, description="File ID (required for UPLOAD, CLOSE, DELETE work types)"
    )


class WorkOrderTokenResponse(BaseModel):
    """Response model for work order token creation."""

    token: str = Field(..., description="The encrypted work order token")
