# Copyright 2021 - 2024 Universität Tübingen, DKFZ, EMBL, and Universität zu Köln
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

"""Shared fixtures"""

import asyncio

import pytest
from hexkit.providers.akafka.testutils import KafkaFixture, get_kafka_fixture
from hexkit.providers.mongodb.testutils import MongoDbFixture, get_mongodb_fixture

from tests.fixtures.datasets import DATASET_UPSERTION_EVENT
from wps.config import Config
from wps.inject import Consumer

kafka_fixture = get_kafka_fixture("session")
mongodb_fixture = get_mongodb_fixture("session")


@pytest.fixture(autouse=True, scope="function")
def reset_db(mongodb_fixture: MongoDbFixture):
    """Clear the database before tests."""
    mongodb_fixture.empty_collections()


async def publish_and_process_dataset_upsertion_event(
    config: Config, kafka_fixture: KafkaFixture, consumer: Consumer
):
    """Publish and process a dataset upsertion event"""
    await kafka_fixture.publish_event(
        payload=DATASET_UPSERTION_EVENT.model_dump(),
        topic=config.dataset_change_event_topic,
        type_=config.dataset_upsertion_event_type,
        key="test-key-fixture",
    )
    await asyncio.wait_for(consumer.event_subscriber.run(forever=False), timeout=10)
    await asyncio.sleep(0.125)


@pytest.fixture(scope="function")
def populate_db(
    reset_db, config: Config, kafka_fixture: KafkaFixture, consumer: Consumer
):
    """Populate the database

    Required for tests using the consumer or client fixtures.
    """
    asyncio.get_event_loop().run_until_complete(
        publish_and_process_dataset_upsertion_event(
            config=config, kafka_fixture=kafka_fixture, consumer=consumer
        )
    )
