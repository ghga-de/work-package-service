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

"""Module hosting the dependency injection container."""

from hexkit.inject import ContainerBase, get_configurator, get_constructor
from hexkit.providers.mongodb import MongoDbDaoFactory

from wps.adapters.outbound.dao import WorkPackageDaoConstructor
from wps.config import CONFIG, Config


class Container(ContainerBase):
    """DI Container"""

    config = get_configurator(Config)

    # outbound providers:
    dao_factory = get_constructor(MongoDbDaoFactory, config=config)

    # outbound translators:
    work_package_dao = get_constructor(
        WorkPackageDaoConstructor,
        name=CONFIG.work_packages_collection,
        dao_factory=dao_factory,
    )
