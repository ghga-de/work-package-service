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

"""A repository for work packages."""

import logging
from datetime import timedelta
from uuid import UUID

from ghga_service_commons.auth.ghga import AuthContext
from ghga_service_commons.utils.crypt import encrypt
from ghga_service_commons.utils.utc_dates import UTCDatetime
from hexkit.utils import now_utc_ms_prec
from jwcrypto import jwk
from pydantic import UUID4, Field, SecretStr
from pydantic_settings import BaseSettings

from wps.core.models import (
    CreateFileWorkOrder,
    Dataset,
    DatasetWithExpiration,
    DownloadWorkOrder,
    ResearchDataUploadBox,
    UploadFileWorkOrder,
    WorkPackage,
    WorkPackageCreationData,
    WorkPackageCreationResponse,
    WorkPackageType,
    WorkType,
)
from wps.core.tokens import (
    generate_work_package_access_token,
    hash_token,
    sign_work_order_token,
)
from wps.ports.inbound.repository import WorkPackageRepositoryPort
from wps.ports.outbound.access import AccessCheckPort
from wps.ports.outbound.dao import (
    DatasetDaoPort,
    ResourceNotFoundError,
    UploadBoxDaoPort,
    WorkPackageDaoPort,
)

log = logging.getLogger(__name__)


class WorkPackageConfig(BaseSettings):
    """Config parameters needed for the WorkPackageRepository."""

    datasets_collection: str = Field(
        "datasets",
        description="The name of the database collection for datasets",
    )
    work_packages_collection: str = Field(
        "workPackages",
        description="The name of the database collection for work packages",
    )
    upload_boxes_collection: str = Field(
        "uploadBoxes",
        description="The name of the database collection for upload boxes",
    )
    work_package_valid_days: int = Field(
        30,
        description="How many days a work package (and its access token) stays valid",
    )
    work_package_signing_key: SecretStr = Field(
        ...,
        description="The private key for signing work order tokens",
        examples=['{"crv": "P-256", "kty": "EC", "x": "...", "y": "..."}'],
    )


class WorkPackageRepository(WorkPackageRepositoryPort):
    """A repository for work packages."""

    def __init__(
        self,
        *,
        config: WorkPackageConfig,
        access_check: AccessCheckPort,
        dataset_dao: DatasetDaoPort,
        upload_box_dao: UploadBoxDaoPort,
        work_package_dao: WorkPackageDaoPort,
    ):
        """Initialize with specific configuration and outbound adapter."""
        self._valid_timedelta = timedelta(config.work_package_valid_days)
        self._signing_key = jwk.JWK.from_json(
            config.work_package_signing_key.get_secret_value()
        )
        if not self._signing_key.has_private:
            key_error = KeyError("No private work order signing key found.")
            log.error(key_error)
            raise key_error
        self._access = access_check
        self._dataset_dao = dataset_dao
        self._upload_box_dao = upload_box_dao
        self._dao = work_package_dao

    async def create(
        self, *, creation_data: WorkPackageCreationData, auth_context: AuthContext
    ) -> WorkPackageCreationResponse:
        """Create a work package and store it in the repository.

        In the following cases, a WorkPackageAccessError is raised:
        - no internal user specified via auth_context
        - no access permission to the specified dataset
        - the specified work type is not supported
        - the files in th dataset cannot be determined
        - no existing files in the dataset have been specified
        """
        try:
            user_id = UUID(auth_context.id)
        except ValueError as error:
            access_error = self.WorkPackageAccessError("Malformed user ID supplied")
            log.error(access_error)
            raise access_error from error

        if user_id is None:
            access_error = self.WorkPackageAccessError("No internal user specified")
            log.error(access_error)
            raise access_error

        dataset_id = creation_data.dataset_id
        box_id = creation_data.box_id
        work_type = creation_data.type

        if work_type == WorkPackageType.DOWNLOAD:
            if not dataset_id:
                access_error = self.WorkPackageAccessError(
                    "dataset_id required for download work packages"
                )
                log.error(access_error)
                raise access_error
            return await self._create_download_work_package(
                creation_data, auth_context, user_id, dataset_id
            )
        elif work_type == WorkPackageType.UPLOAD:
            if not box_id:
                access_error = self.WorkPackageAccessError(
                    "box_id required for upload work packages"
                )
                log.error(access_error)
                raise access_error
            return await self._create_upload_work_package(
                creation_data, auth_context, user_id, box_id
            )
        else:
            access_error = self.WorkPackageAccessError("Unsupported work type")
            log.error(access_error, extra={"work_type": work_type})
            raise access_error

    async def _create_download_work_package(
        self,
        creation_data: WorkPackageCreationData,
        auth_context: AuthContext,
        user_id: UUID,
        dataset_id: str,
    ) -> WorkPackageCreationResponse:
        """Create a download work package."""
        extra = {  # only used for logging
            "user_id": user_id,
            "dataset_id": dataset_id,
            "work_type": WorkPackageType.DOWNLOAD,
        }

        expires = await self._access.check_download_access(user_id, dataset_id)
        if not expires:
            access_error = self.WorkPackageAccessError(
                "Missing dataset access permission"
            )
            log.error(access_error, extra=extra)
            raise access_error

        try:
            dataset = await self.get_dataset(dataset_id)
        except self.DatasetNotFoundError as error:
            access_error = self.WorkPackageAccessError("Cannot determine dataset files")
            log.error(access_error, extra=extra)
            raise access_error from error

        file_ids = [file.id for file in dataset.files]
        if creation_data.file_ids is not None:
            # if file_ids is not passed as None, restrict the file set
            file_id_set = set(creation_data.file_ids)
            file_ids = [file_id for file_id in file_ids if file_id in file_id_set]
        if not file_ids:
            access_error = self.WorkPackageAccessError(
                "No existing files have been specified"
            )
            log.error(access_error, extra=extra)
            raise access_error

        file_id_set = set(file_ids)
        files = {
            file.id: file.extension for file in dataset.files if file.id in file_id_set
        }

        return await self._create_work_package_record(
            creation_data, auth_context, user_id, expires, files, dataset_id=dataset_id
        )

    async def _create_upload_work_package(
        self,
        creation_data: WorkPackageCreationData,
        auth_context: AuthContext,
        user_id: UUID,
        box_id: UUID,
    ) -> WorkPackageCreationResponse:
        """Create an upload work package."""
        extra = {  # only used for logging
            "user_id": user_id,
            "box_id": box_id,
            "work_type": WorkPackageType.UPLOAD,
        }

        expires = await self._access.check_upload_access(user_id, box_id)
        if not expires:
            access_error = self.WorkPackageAccessError(
                "Missing upload box access permission"
            )
            log.error(access_error, extra=extra)
            raise access_error

        # For upload work packages, files will be created dynamically
        # so we start with an empty files dict
        files: dict[str, str] = {}

        return await self._create_work_package_record(
            creation_data, auth_context, user_id, expires, files, box_id=box_id
        )

    async def _create_work_package_record(  # noqa: PLR0913
        self,
        creation_data: WorkPackageCreationData,
        auth_context: AuthContext,
        user_id: UUID,
        expires: UTCDatetime,
        files: dict[str, str],
        *,
        dataset_id: str | None = None,
        box_id: UUID4 | None = None,
    ) -> WorkPackageCreationResponse:
        """Create the work package database record."""
        full_user_name = auth_context.name
        if auth_context.title:
            full_user_name = auth_context.title + " " + full_user_name

        created = now_utc_ms_prec()
        expires = min(created + self._valid_timedelta, expires)

        token = generate_work_package_access_token()
        user_public_crypt4gh_key = creation_data.user_public_crypt4gh_key

        work_package = WorkPackage(
            dataset_id=dataset_id,
            box_id=box_id,
            type=creation_data.type,
            files=files,
            user_id=user_id,
            full_user_name=full_user_name,
            email=auth_context.email,
            user_public_crypt4gh_key=creation_data.user_public_crypt4gh_key,
            token_hash=hash_token(token),
            created=created,
            expires=expires,
        )
        await self._dao.insert(work_package)
        encrypted_token = encrypt(token, user_public_crypt4gh_key)

        return WorkPackageCreationResponse(
            id=str(work_package.id), token=encrypted_token, expires=expires
        )

    def _validate_work_package(self, work_package: WorkPackage):
        """Validate certain work package details.

        Raises a WorkPackageAccessError in the following cases:
        - the work package has expired
        - the work package is for download and the dataset ID is missing
        - the work package is for upload and the box ID is missing
        """
        extra = {"work_package_id": work_package.id}  # only used for logging
        if not work_package.created <= now_utc_ms_prec() < work_package.expires:
            access_error = self.WorkPackageAccessError("Work package has expired")
            log.error(access_error, extra=extra)
            raise access_error

        dataset_id = work_package.dataset_id
        if work_package.type == WorkPackageType.DOWNLOAD and not dataset_id:
            access_error = self.WorkPackageAccessError(
                "Invalid download work package: missing dataset_id"
            )
            log.error(access_error, extra=extra)
            raise access_error
        elif work_package.type == WorkPackageType.UPLOAD and not work_package.box_id:
            access_error = self.WorkPackageAccessError(
                "Invalid upload work package: missing box_id"
            )
            log.error(access_error, extra=extra)
            raise access_error

        if work_package.type not in (WorkPackageType.DOWNLOAD, WorkPackageType.UPLOAD):
            access_error = self.WorkPackageAccessError("Unsupported work type")
            log.error(access_error, extra=extra)
            raise access_error

    async def get(
        self,
        work_package_id: UUID,
        *,
        check_valid: bool = True,
        work_package_access_token: str | None = None,
    ) -> WorkPackage:
        """Get a work package with the given ID from the repository.

        In the following cases, a WorkPackageAccessError is raised:
        - if a work package with the given work_package_id does not exist
        - if check_valid is set and the work package has expired or the box/dataset
          ID is missing
        - if a work_package_access_token is specified and it does not match
          the token hash that is stored in the work package
        """
        extra = {"work_package_id": work_package_id}  # only used for logging

        try:
            work_package = await self._dao.get_by_id(work_package_id)
        except ResourceNotFoundError as error:
            access_error = self.WorkPackageAccessError("Work package not found")
            log.error(access_error, extra=extra)
            raise access_error from error

        if work_package_access_token and work_package.token_hash != hash_token(
            work_package_access_token
        ):
            access_error = self.WorkPackageAccessError(
                "Invalid work package access token"
            )
            log.error(access_error, extra=extra)
            raise access_error

        if check_valid:
            self._validate_work_package(work_package)

            # Check access based on work package type
            if work_package.type == WorkPackageType.DOWNLOAD:
                has_access = await self._access.check_download_access(
                    work_package.user_id,
                    work_package.dataset_id,  # type: ignore
                )
            elif work_package.type == WorkPackageType.UPLOAD:
                has_access = await self._access.check_upload_access(
                    work_package.user_id,
                    work_package.box_id,  # type: ignore
                )

            if not has_access:
                access_error = self.WorkPackageAccessError(
                    f"{work_package.type.value.title()} access has been revoked"
                )
                log.error(access_error, extra=extra)
                raise access_error
        return work_package

    async def get_download_wot(
        self,
        *,
        work_package_id: UUID4,
        file_id: str,
        check_valid: bool = True,
        work_package_access_token: str | None = None,
    ) -> str:
        """Create a work order token for a given work package and file.

        In the following cases, a WorkPackageAccessError is raised:
        - if a work package with the given work_package_id does not exist
        - if check_valid is set and the work package has expired
        - if the work package type is not DOWNLOAD
        - if a work_package_access_token is specified and it does not match
          the token hash that is stored in the work package
        """
        extra = {  # only used for logging
            "work_package_id": work_package_id,
            "file_id": file_id,
            "check_valid": check_valid,
        }

        work_package = await self.get(
            work_package_id,
            check_valid=check_valid,
            work_package_access_token=work_package_access_token,
        )

        extra["work_package_type"] = work_package.type
        user_public_crypt4gh_key = work_package.user_public_crypt4gh_key

        if work_package.type != WorkPackageType.DOWNLOAD:
            access_error = self.WorkPackageAccessError(
                "Work package type must be DOWNLOAD to obtain a download access WOT"
            )
            log.error(access_error, extra=extra)
            raise access_error

        # For Download-type work packages, the file ID must be in the list of files
        if file_id not in work_package.files:
            access_error = self.WorkPackageAccessError(
                "File is not contained in work package"
            )
            log.error(access_error, extra=extra)
            raise access_error

        wot = DownloadWorkOrder(
            work_type=WorkType.DOWNLOAD,
            file_id=file_id,
            user_public_crypt4gh_key=user_public_crypt4gh_key,
        )
        signed_wot = sign_work_order_token(wot, self._signing_key)
        return encrypt(signed_wot, user_public_crypt4gh_key)

    async def get_upload_wot(  # noqa: PLR0913
        self,
        *,
        work_package_id: UUID4,
        work_type: WorkType,
        box_id: UUID4,
        alias: str | None = None,
        file_id: UUID4 | None = None,
        check_valid: bool = True,
        work_package_access_token: str | None = None,
    ) -> str:
        """Create a work order token for a given work package and file.

        The box ID populated in upload WOTs is the file_upload_box ID, not the main
        ResearchDataUploadBox ID.

        In the following cases, a WorkPackageAccessError is raised:
        - if a work package with the given work_package_id does not exist
        - if the work type is not valid, i.e. one of create, upload, close, or delete
        - if the work_type requires parameters that are not provided (alias or file ID)
        - if check_valid is set and the work package has expired
        - if a work_package_access_token is specified and it does not match
          the token hash that is stored in the work package
        """
        extra = {  # only used for logging
            "work_package_id": work_package_id,
            "file_id": file_id,
            "alias": alias,
            "work_token_type": work_type,
            "check_valid": check_valid,
        }

        work_package = await self.get(
            work_package_id,
            check_valid=check_valid,
            work_package_access_token=work_package_access_token,
        )

        extra["work_package_type"] = work_package.type
        user_public_crypt4gh_key = work_package.user_public_crypt4gh_key

        # Retrieve the ResearchDataUploadBox in order to get its FileUploadBox ID
        # TODO: Error handling here
        research_data_upload_box = await self._upload_box_dao.get_by_id(box_id)
        file_upload_box_id = research_data_upload_box.file_upload_box_id

        if work_type == WorkType.CREATE:
            if not alias:
                access_error = self.WorkPackageAccessError(
                    "Alias must be provided for file creation WOTs"
                )
                log.error(access_error, extra=extra)
                raise access_error
            create_file_wot = CreateFileWorkOrder(
                work_type=work_type,
                alias=alias,
                box_id=file_upload_box_id,
                user_public_crypt4gh_key=user_public_crypt4gh_key,
            )
            signed_wot = sign_work_order_token(create_file_wot, self._signing_key)
        elif work_type in [WorkType.UPLOAD, WorkType.CLOSE, WorkType.DELETE]:
            if not file_id:
                access_error = self.WorkPackageAccessError(
                    "File ID must be provided for file upload WOTs"
                )
                log.error(access_error, extra=extra)
                raise access_error
            upload_file_wot = UploadFileWorkOrder(
                work_type=work_type,
                box_id=file_upload_box_id,
                file_id=file_id,
                user_public_crypt4gh_key=user_public_crypt4gh_key,
            )
            signed_wot = sign_work_order_token(upload_file_wot, self._signing_key)
        else:
            access_error = self.WorkPackageAccessError(
                f"Unsupported Work Order Token type: {work_type.value}"
            )
            log.error(access_error, extra=extra)
            raise access_error
        return encrypt(signed_wot, user_public_crypt4gh_key)

    async def register_dataset(self, dataset: Dataset) -> None:
        """Register a dataset with all of its files."""
        await self._dataset_dao.upsert(dataset)

    async def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset with all of its files.

        If the dataset does not exist, a DatasetNotFoundError will be raised.
        """
        try:
            await self._dataset_dao.delete(id_=dataset_id)
        except ResourceNotFoundError as error:
            dataset_not_found_error = self.DatasetNotFoundError("Dataset not found")
            log.error(dataset_not_found_error, extra={"dataset_id": dataset_id})
            raise dataset_not_found_error from error

    async def get_dataset(self, dataset_id: str) -> Dataset:
        """Get a registered dataset using the given ID.

        If the dataset does not exist, a DatasetNotFoundError will be raised.
        """
        try:
            return await self._dataset_dao.get_by_id(dataset_id)
        except ResourceNotFoundError as error:
            dataset_not_found_error = self.DatasetNotFoundError("Dataset not found")
            log.error(dataset_not_found_error, extra={"dataset_id": dataset_id})
            raise dataset_not_found_error from error

    async def get_datasets(
        self, *, auth_context: AuthContext
    ) -> list[DatasetWithExpiration]:
        """Get the list of all datasets accessible to the authenticated user.

        The returned datasets also have an expiration date until when access is granted.
        """
        try:
            user_id = UUID(auth_context.id)
        except ValueError as error:
            access_error = self.WorkPackageAccessError("Malformed user ID supplied")
            log.error(access_error)
            raise access_error from error

        if user_id is None:
            access_error = self.WorkPackageAccessError("No internal user specified")
            log.error(access_error)
            raise access_error

        dataset_id_to_expiration = (
            await self._access.get_accessible_datasets_with_expiration(user_id)
        )
        datasets_with_expiration: list[DatasetWithExpiration] = []
        for dataset_id in dataset_id_to_expiration:
            try:
                dataset = await self.get_dataset(dataset_id)
            except self.DatasetNotFoundError:
                log.debug("Dataset '%s' not found, continuing...", dataset_id)
                continue
            dataset_with_expiration = DatasetWithExpiration(
                **dataset.model_dump(), expires=dataset_id_to_expiration[dataset_id]
            )
            datasets_with_expiration.append(dataset_with_expiration)
        return datasets_with_expiration

    async def register_upload_box(self, upload_box: ResearchDataUploadBox) -> None:
        """Register an upload box."""
        await self._upload_box_dao.upsert(upload_box)
        log.info("Upserted UploadBox with ID %s", str(upload_box.id))

    async def delete_upload_box(self, box_id: UUID4) -> None:
        """Delete an upload box with the given ID."""
        try:
            await self._upload_box_dao.delete(id_=box_id)
            log.info("Deleted UploadBox with ID %s", str(box_id))
        except ResourceNotFoundError:
            log.info(
                "UploadBox with ID %s not found, presumed already deleted.", str(box_id)
            )

    async def get_upload_box(self, box_id: UUID4) -> ResearchDataUploadBox:
        """Get a registered upload box using the given ID.

        Raises an `UploadBoxNotFoundError` if no doc with the box_id exists.
        """
        try:
            return await self._upload_box_dao.get_by_id(box_id)
        except ResourceNotFoundError as err:
            error = self.UploadBoxNotFoundError("UploadBox not found")
            log.error(error, extra={"box_id": box_id})
            raise error from err

    async def get_upload_boxes(self, *, user_id: UUID4) -> list[ResearchDataUploadBox]:
        """Get the list of all upload boxes accessible to the authenticated user."""
        # Get accessible upload boxes from access service
        box_id_to_expiration = await self._access.get_accessible_boxes_with_expiration(
            user_id
        )
        log.debug(
            "Retrieved %i upload boxes for user %s",
            len(box_id_to_expiration),
            str(user_id),
        )

        upload_boxes: list[ResearchDataUploadBox] = []
        now = now_utc_ms_prec()
        for box_id, expiration in box_id_to_expiration.items():
            if expiration <= now:
                continue
            try:
                upload_box = await self.get_upload_box(box_id)
                upload_boxes.append(upload_box)
            except self.UploadBoxNotFoundError:
                log.debug("Upload box '%s' not found, continuing...", box_id)
                continue

        return upload_boxes
