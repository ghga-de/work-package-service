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

"""Entrypoints to prepare and run the application."""

from ghga_service_commons.api import run_server
from hexkit.log import configure_logging
from hexkit.opentelemetry_setup import configure_opentelemetry

from wps.config import Config
from wps.prepare import prepare_consumer, prepare_rest_app


async def run_rest_app() -> None:
    """Run the HTTP REST API."""
    config = Config()  # type: ignore
    configure_logging(config=config)
    configure_opentelemetry(service_name=config.service_name, config=config)

    async with prepare_rest_app(config=config) as app:
        await run_server(app=app, config=config)


async def consume_events(run_forever: bool = True) -> None:
    """Run an event consumer listening to the configured topic."""
    config = Config()  # type: ignore
    configure_logging(config=config)
    configure_opentelemetry(service_name=config.service_name, config=config)

    async with prepare_consumer(config=config) as consumer:
        await consumer.event_subscriber.run(forever=run_forever)
