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

"""Generate signing keys for testing"""

from ghga_service_commons.utils.jwt_helpers import generate_jwk


def print_key_env() -> None:
    """Print environment setting for the auth key."""
    auth_key = generate_jwk().export(private_key=False)
    print(f"WPS_AUTH_KEY={auth_key!r}")
    wps_key = generate_jwk().export(private_key=True)
    print(f"WPS_WORK_PACKAGE_SIGNING_KEY={wps_key!r}")


if __name__ == "__main__":
    print_key_env()
