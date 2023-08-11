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

"""Test that the work package service consumes and processes events properly."""

import asyncio

from hexkit.base import InboundProviderBase
from hexkit.providers.akafka.testutils import KafkaFixture
from pytest import mark, raises

from wps.config import Config
from wps.container import Container
from wps.core.repository import WorkPackageRepository

from .fixtures import fixture_container  # noqa: F401 # pylint: disable=unused-import
from .fixtures.datasets import DATASET, DATASET_DELETION_EVENT, DATASET_UPSERTION_EVENT

TIMEOUT = 5
RETRY_INTERVAL = 0.05
RETRIES = round(TIMEOUT / RETRY_INTERVAL)


@mark.asyncio
async def test_dataset_registration(container: Container):
    """Test the registration of a dataset announced as an event."""

    repository = await container.work_package_repository()
    dataset = await repository.get_dataset("some-dataset-id")

    assert dataset == DATASET

    with raises(repository.DatasetNotFoundError):
        await repository.get_dataset("another-dataset-id")


@mark.asyncio
async def test_dataset_insert_update_delete(
    container: Container, kafka_fixture: KafkaFixture
):
    """Test the whole lifecycle of a dataset announced as an event."""

    config: Config = container.config()
    repository: WorkPackageRepository = await container.work_package_repository()
    event_subscriber: InboundProviderBase = await container.event_subscriber()

    accession = "another-dataset-id"
    with raises(repository.DatasetNotFoundError):
        await repository.get_dataset(accession)

    # insert a dataset

    inserted_dataset = DATASET_UPSERTION_EVENT
    inserted_dataset = inserted_dataset.copy(update={"accession": accession})
    await kafka_fixture.publish_event(
        payload=inserted_dataset.dict(),
        topic=config.dataset_change_event_topic,
        type_=config.dataset_upsertion_event_type,
        key="test-key-1",
    )
    await asyncio.wait_for(event_subscriber.run(forever=False), timeout=TIMEOUT)

    # wait until dataset is stored
    dataset = None
    for _ in range(RETRIES):
        await asyncio.sleep(RETRY_INTERVAL)
        try:
            dataset = await repository.get_dataset(accession)
        except repository.DatasetNotFoundError:
            pass
        else:
            assert dataset.title == "Test dataset 1"
            break
    else:
        assert False, "dataset not created"

    # update the dataset

    updated_dataset = DATASET_UPSERTION_EVENT
    updated_dataset = inserted_dataset.copy(
        update={"accession": accession, "title": "Changed dataset 1"}
    )
    await kafka_fixture.publish_event(
        payload=updated_dataset.dict(),
        topic=config.dataset_change_event_topic,
        type_=config.dataset_upsertion_event_type,
        key="test-key-2",
    )
    await asyncio.wait_for(event_subscriber.run(forever=False), timeout=TIMEOUT)
    # wait until dataset is updated
    dataset = None
    for _ in range(RETRIES):
        await asyncio.sleep(RETRY_INTERVAL)
        dataset = await repository.get_dataset(accession)
        if dataset.title == "Changed dataset 1":
            break
    else:
        assert False, "dataset title not changed"

    # delete the dataset again

    deleted_dataset = DATASET_DELETION_EVENT
    deleted_dataset = deleted_dataset.copy(update={"accession": accession})
    await kafka_fixture.publish_event(
        payload=deleted_dataset.dict(),
        topic=config.dataset_change_event_topic,
        type_=config.dataset_deletion_event_type,
        key="test_key-3",
    )
    await asyncio.wait_for(event_subscriber.run(forever=False), timeout=TIMEOUT)

    # wait until dataset is deleted
    for _ in range(RETRIES):
        await asyncio.sleep(RETRY_INTERVAL)
        try:
            await repository.get_dataset(accession)
        except repository.DatasetNotFoundError:
            break
    else:
        assert False, "dataset not deleted"
