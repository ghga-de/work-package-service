[![tests](https://github.com/ghga-de/work-package-service/actions/workflows/tests.yaml/badge.svg)](https://github.com/ghga-de/work-package-service/actions/workflows/tests.yaml)
[![Coverage Status](https://coveralls.io/repos/github/ghga-de/work-package-service/badge.svg?branch=main)](https://coveralls.io/github/ghga-de/work-package-service?branch=main)

# Work Package Service

Work Package Service

## Description

The work package service allows creating work packages for downloading or
uploading dataset files and provides an authorization mechanism for these tasks
by issuing access and work order tokens.

### API endpoints:

#### `POST /work-packages`

Creates a work package.

- auth header: internal access token
- request body:
  - `dataset_id`: string (the ID of a dataset)
  - `type`: enum (download/upload)
  - `file_ids`: array of strings  (null = all files of the dataset)
  - `user_public_crypt4gh_key`: string (the user's public Crypt4GH key)
- response body:
  - `id`: string (the ID of the created work package)
  - `token`: string (encrypted work and base64 encoded package access token)

####  `GET /work-packages/{work_package_id}`

Gets details on the specified work package.

- auth header: work package access token

#### `POST /work-packages/{work_package_id}/files/{file_id}/work-order-tokens`

 Creates an encrypted work order token for the specified work package and file.

- auth header: work package access token

#### `GET /users/{user_id}/datasets`

Gets a list of all dataset IDs that can be downloaded by the user.

- auth header: internal access token with the user context


## Installation

We recommend using the provided Docker container.

A pre-built version is available on [Docker Hub](https://hub.docker.com/repository/docker/ghga/work-package-service):
```bash
docker pull ghga/work-package-service:7.0.2
```

Or you can build the container yourself from the [`./Dockerfile`](./Dockerfile):
```bash
# Execute in the repo's root dir:
docker build -t ghga/work-package-service:7.0.2 .
```

For production-ready deployment, we recommend using Kubernetes.
However for simple use cases, you could execute the service using docker
on a single server:
```bash
# The entrypoint is pre-configured:
docker run -p 8080:8080 ghga/work-package-service:7.0.2 --help
```

If you prefer not to use containers, you may install the service from source:
```bash
# Execute in the repo's root dir:
pip install .

# To run the service:
wps --help
```

## Configuration

### Parameters

The service requires the following configuration parameters:
- <a id="properties/enable_opentelemetry"></a>**`enable_opentelemetry`** *(boolean)*: If set to true, this will run necessary setup code.If set to false, environment variables are set that should also effectively disable autoinstrumentation. Default: `false`.
- <a id="properties/otel_trace_sampling_rate"></a>**`otel_trace_sampling_rate`** *(number)*: Determines which proportion of spans should be sampled. A value of 1.0 means all and is equivalent to the previous behaviour. Setting this to 0 will result in no spans being sampled, but this does not automatically set `enable_opentelemetry` to False. Minimum: `0`. Maximum: `1`. Default: `1.0`.
- <a id="properties/log_level"></a>**`log_level`** *(string)*: The minimum log level to capture. Must be one of: "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", or "TRACE". Default: `"INFO"`.
- <a id="properties/service_name"></a>**`service_name`** *(string)*: Default: `"wps"`.
- <a id="properties/service_instance_id"></a>**`service_instance_id`** *(string, required)*: A string that uniquely identifies this instance across all instances of this service. A globally unique Kafka client ID will be created by concatenating the service_name and the service_instance_id.

  Examples:
  ```json
  "germany-bw-instance-001"
  ```

- <a id="properties/log_format"></a>**`log_format`**: If set, will replace JSON formatting with the specified string format. If not set, has no effect. In addition to the standard attributes, the following can also be specified: timestamp, service, instance, level, correlation_id, and details. Default: `null`.
  - **Any of**
    - <a id="properties/log_format/anyOf/0"></a>*string*
    - <a id="properties/log_format/anyOf/1"></a>*null*

  Examples:
  ```json
  "%(timestamp)s - %(service)s - %(level)s - %(message)s"
  ```

  ```json
  "%(asctime)s - Severity: %(levelno)s - %(msg)s"
  ```

- <a id="properties/log_traceback"></a>**`log_traceback`** *(boolean)*: Whether to include exception tracebacks in log messages. Default: `true`.
- <a id="properties/datasets_collection"></a>**`datasets_collection`** *(string)*: The name of the database collection for datasets. Default: `"datasets"`.
- <a id="properties/upload_boxes_collection"></a>**`upload_boxes_collection`** *(string)*: The name of the database collection for upload boxes. Default: `"uploadBoxes"`.
- <a id="properties/work_packages_collection"></a>**`work_packages_collection`** *(string)*: The name of the database collection for work packages. Default: `"workPackages"`.
- <a id="properties/work_package_valid_days"></a>**`work_package_valid_days`** *(integer)*: How many days a work package (and its access token) stays valid. Default: `30`.
- <a id="properties/work_package_signing_key"></a>**`work_package_signing_key`** *(string, format: password, required and write-only)*: The private key for signing work order tokens.

  Examples:
  ```json
  "{\"crv\": \"P-256\", \"kty\": \"EC\", \"x\": \"...\", \"y\": \"...\"}"
  ```

- <a id="properties/mongo_dsn"></a>**`mongo_dsn`** *(string, format: multi-host-uri, required)*: MongoDB connection string. Might include credentials. For more information see: https://naiveskill.com/mongodb-connection-string/. Length must be at least 1.

  Examples:
  ```json
  "mongodb://localhost:27017"
  ```

- <a id="properties/db_name"></a>**`db_name`** *(string)*: Default: `"work-packages"`.
- <a id="properties/mongo_timeout"></a>**`mongo_timeout`**: Timeout in seconds for API calls to MongoDB. The timeout applies to all steps needed to complete the operation, including server selection, connection checkout, serialization, and server-side execution. When the timeout expires, PyMongo raises a timeout exception. If set to None, the operation will not time out (default MongoDB behavior). Default: `null`.
  - **Any of**
    - <a id="properties/mongo_timeout/anyOf/0"></a>*integer*: Exclusive minimum: `0`.
    - <a id="properties/mongo_timeout/anyOf/1"></a>*null*

  Examples:
  ```json
  300
  ```

  ```json
  600
  ```

  ```json
  null
  ```

- <a id="properties/db_version_collection"></a>**`db_version_collection`** *(string, required)*: The name of the collection containing DB version information for this service.

  Examples:
  ```json
  "ifrsDbVersions"
  ```

- <a id="properties/migration_wait_sec"></a>**`migration_wait_sec`** *(integer, required)*: The number of seconds to wait before checking the DB version again.

  Examples:
  ```json
  5
  ```

  ```json
  30
  ```

  ```json
  180
  ```

- <a id="properties/migration_max_wait_sec"></a>**`migration_max_wait_sec`**: The maximum number of seconds to wait for migrations to complete before raising an error. Default: `null`.
  - **Any of**
    - <a id="properties/migration_max_wait_sec/anyOf/0"></a>*integer*
    - <a id="properties/migration_max_wait_sec/anyOf/1"></a>*null*

  Examples:
  ```json
  null
  ```

  ```json
  300
  ```

  ```json
  600
  ```

  ```json
  3600
  ```

- <a id="properties/kafka_servers"></a>**`kafka_servers`** *(array, required)*: A list of connection strings to connect to Kafka bootstrap servers.
  - <a id="properties/kafka_servers/items"></a>**Items** *(string)*

  Examples:
  ```json
  [
      "localhost:9092"
  ]
  ```

- <a id="properties/kafka_security_protocol"></a>**`kafka_security_protocol`** *(string)*: Protocol used to communicate with brokers. Valid values are: PLAINTEXT, SSL. Must be one of: "PLAINTEXT" or "SSL". Default: `"PLAINTEXT"`.
- <a id="properties/kafka_ssl_cafile"></a>**`kafka_ssl_cafile`** *(string)*: Certificate Authority file path containing certificates used to sign broker certificates. If a CA is not specified, the default system CA will be used if found by OpenSSL. Default: `""`.
- <a id="properties/kafka_ssl_certfile"></a>**`kafka_ssl_certfile`** *(string)*: Optional filename of client certificate, as well as any CA certificates needed to establish the certificate's authenticity. Default: `""`.
- <a id="properties/kafka_ssl_keyfile"></a>**`kafka_ssl_keyfile`** *(string)*: Optional filename containing the client private key. Default: `""`.
- <a id="properties/kafka_ssl_password"></a>**`kafka_ssl_password`** *(string, format: password, write-only)*: Optional password to be used for the client private key. Default: `""`.
- <a id="properties/generate_correlation_id"></a>**`generate_correlation_id`** *(boolean)*: A flag, which, if False, will result in an error when inbound requests don't possess a correlation ID. If True, requests without a correlation ID will be assigned a newly generated ID in the correlation ID middleware function. Default: `true`.

  Examples:
  ```json
  true
  ```

  ```json
  false
  ```

- <a id="properties/kafka_max_message_size"></a>**`kafka_max_message_size`** *(integer)*: The largest message size that can be transmitted, in bytes, before compression. Only services that have a need to send/receive larger messages should set this. When used alongside compression, this value can be set to something greater than the broker's `message.max.bytes` field, which effectively concerns the compressed message size. Exclusive minimum: `0`. Default: `1048576`.

  Examples:
  ```json
  1048576
  ```

  ```json
  16777216
  ```

- <a id="properties/kafka_compression_type"></a>**`kafka_compression_type`**: The compression type used for messages. Valid values are: None, gzip, snappy, lz4, and zstd. If None, no compression is applied. This setting is only relevant for the producer and has no effect on the consumer. If set to a value, the producer will compress messages before sending them to the Kafka broker. If unsure, zstd provides a good balance between speed and compression ratio. Default: `null`.
  - **Any of**
    - <a id="properties/kafka_compression_type/anyOf/0"></a>*string*: Must be one of: "gzip", "snappy", "lz4", or "zstd".
    - <a id="properties/kafka_compression_type/anyOf/1"></a>*null*

  Examples:
  ```json
  null
  ```

  ```json
  "gzip"
  ```

  ```json
  "snappy"
  ```

  ```json
  "lz4"
  ```

  ```json
  "zstd"
  ```

- <a id="properties/kafka_max_retries"></a>**`kafka_max_retries`** *(integer)*: The maximum number of times to immediately retry consuming an event upon failure. Works independently of the dead letter queue. Minimum: `0`. Default: `0`.

  Examples:
  ```json
  0
  ```

  ```json
  1
  ```

  ```json
  2
  ```

  ```json
  3
  ```

  ```json
  5
  ```

- <a id="properties/kafka_enable_dlq"></a>**`kafka_enable_dlq`** *(boolean)*: A flag to toggle the dead letter queue. If set to False, the service will crash upon exhausting retries instead of publishing events to the DLQ. If set to True, the service will publish events to the DLQ topic after exhausting all retries. Default: `false`.

  Examples:
  ```json
  true
  ```

  ```json
  false
  ```

- <a id="properties/kafka_dlq_topic"></a>**`kafka_dlq_topic`** *(string)*: The name of the topic used to resolve error-causing events. Default: `"dlq"`.

  Examples:
  ```json
  "dlq"
  ```

- <a id="properties/kafka_retry_backoff"></a>**`kafka_retry_backoff`** *(integer)*: The number of seconds to wait before retrying a failed event. The backoff time is doubled for each retry attempt. Minimum: `0`. Default: `0`.

  Examples:
  ```json
  0
  ```

  ```json
  1
  ```

  ```json
  2
  ```

  ```json
  3
  ```

  ```json
  5
  ```

- <a id="properties/upload_box_topic"></a>**`upload_box_topic`** *(string, required)*: Name of the event topic containing upload box events.

  Examples:
  ```json
  "upload-boxes"
  ```

- <a id="properties/dataset_change_topic"></a>**`dataset_change_topic`** *(string, required)*: Name of the topic announcing, among other things, the list of files included in a new dataset.

  Examples:
  ```json
  "metadata_datasets"
  ```

- <a id="properties/dataset_deletion_type"></a>**`dataset_deletion_type`** *(string, required)*: Event type used for communicating dataset deletions.

  Examples:
  ```json
  "dataset_deleted"
  ```

- <a id="properties/dataset_upsertion_type"></a>**`dataset_upsertion_type`** *(string, required)*: Event type used for communicating dataset upsertions.

  Examples:
  ```json
  "dataset_upserted"
  ```

- <a id="properties/access_url"></a>**`access_url`** *(string, format: uri, required)*: Base URL of the internal access API for download and upload. Length must be between 1 and 2083 (inclusive).

  Examples:
  ```json
  "http://127.0.0.1/"
  ```

- <a id="properties/auth_key"></a>**`auth_key`** *(string, required)*: The GHGA internal public key for validating the token signature.

  Examples:
  ```json
  "{\"crv\": \"P-256\", \"kty\": \"EC\", \"x\": \"...\", \"y\": \"...\"}"
  ```

- <a id="properties/auth_algs"></a>**`auth_algs`** *(array)*: A list of all algorithms used for signing GHGA internal tokens. Default: `["ES256"]`.
  - <a id="properties/auth_algs/items"></a>**Items** *(string)*
- <a id="properties/auth_check_claims"></a>**`auth_check_claims`** *(object)*: A dict of all GHGA internal claims that shall be verified. Can contain additional properties. Default: `{"id": null, "name": null, "email": null, "iat": null, "exp": null}`.
- <a id="properties/auth_map_claims"></a>**`auth_map_claims`** *(object)*: A mapping of claims to attributes in the GHGA auth context. Can contain additional properties. Default: `{}`.
  - <a id="properties/auth_map_claims/additionalProperties"></a>**Additional properties** *(string)*
- <a id="properties/host"></a>**`host`** *(string)*: IP of the host. Default: `"127.0.0.1"`.
- <a id="properties/port"></a>**`port`** *(integer)*: Port to expose the server on the specified host. Default: `8080`.
- <a id="properties/auto_reload"></a>**`auto_reload`** *(boolean)*: A development feature. Set to `True` to automatically reload the server upon code changes. Default: `false`.
- <a id="properties/workers"></a>**`workers`** *(integer)*: Number of workers processes to run. Default: `1`.
- <a id="properties/api_root_path"></a>**`api_root_path`** *(string)*: Root path at which the API is reachable. This is relative to the specified host and port. Default: `""`.
- <a id="properties/openapi_url"></a>**`openapi_url`** *(string)*: Path to get the openapi specification in JSON format. This is relative to the specified host and port. Default: `"/openapi.json"`.
- <a id="properties/docs_url"></a>**`docs_url`** *(string)*: Path to host the swagger documentation. This is relative to the specified host and port. Default: `"/docs"`.
- <a id="properties/cors_allowed_origins"></a>**`cors_allowed_origins`**: A list of origins that should be permitted to make cross-origin requests. By default, cross-origin requests are not allowed. You can use ['*'] to allow any origin. Default: `null`.
  - **Any of**
    - <a id="properties/cors_allowed_origins/anyOf/0"></a>*array*
      - <a id="properties/cors_allowed_origins/anyOf/0/items"></a>**Items** *(string)*
    - <a id="properties/cors_allowed_origins/anyOf/1"></a>*null*

  Examples:
  ```json
  [
      "https://example.org",
      "https://www.example.org"
  ]
  ```

- <a id="properties/cors_allow_credentials"></a>**`cors_allow_credentials`**: Indicate that cookies should be supported for cross-origin requests. Defaults to False. Also, cors_allowed_origins cannot be set to ['*'] for credentials to be allowed. The origins must be explicitly specified. Default: `null`.
  - **Any of**
    - <a id="properties/cors_allow_credentials/anyOf/0"></a>*boolean*
    - <a id="properties/cors_allow_credentials/anyOf/1"></a>*null*

  Examples:
  ```json
  [
      "https://example.org",
      "https://www.example.org"
  ]
  ```

- <a id="properties/cors_allowed_methods"></a>**`cors_allowed_methods`**: A list of HTTP methods that should be allowed for cross-origin requests. Defaults to ['GET']. You can use ['*'] to allow all standard methods. Default: `null`.
  - **Any of**
    - <a id="properties/cors_allowed_methods/anyOf/0"></a>*array*
      - <a id="properties/cors_allowed_methods/anyOf/0/items"></a>**Items** *(string)*
    - <a id="properties/cors_allowed_methods/anyOf/1"></a>*null*

  Examples:
  ```json
  [
      "*"
  ]
  ```

- <a id="properties/cors_allowed_headers"></a>**`cors_allowed_headers`**: A list of HTTP request headers that should be supported for cross-origin requests. Defaults to []. You can use ['*'] to allow all request headers. The Accept, Accept-Language, Content-Language, Content-Type and some are always allowed for CORS requests. Default: `null`.
  - **Any of**
    - <a id="properties/cors_allowed_headers/anyOf/0"></a>*array*
      - <a id="properties/cors_allowed_headers/anyOf/0/items"></a>**Items** *(string)*
    - <a id="properties/cors_allowed_headers/anyOf/1"></a>*null*

  Examples:
  ```json
  []
  ```

- <a id="properties/cors_exposed_headers"></a>**`cors_exposed_headers`**: A list of HTTP response headers that should be exposed for cross-origin responses. Defaults to []. Note that you can NOT use ['*'] to expose all response headers. The Cache-Control, Content-Language, Content-Length, Content-Type, Expires, Last-Modified and Pragma headers are always exposed for CORS responses. Default: `null`.
  - **Any of**
    - <a id="properties/cors_exposed_headers/anyOf/0"></a>*array*
      - <a id="properties/cors_exposed_headers/anyOf/0/items"></a>**Items** *(string)*
    - <a id="properties/cors_exposed_headers/anyOf/1"></a>*null*

  Examples:
  ```json
  []
  ```

### Usage:

A template YAML file for configuring the service can be found at
[`./example_config.yaml`](./example_config.yaml).
Please adapt it, rename it to `.wps.yaml`, and place it in one of the following locations:
- in the current working directory where you execute the service (on Linux: `./.wps.yaml`)
- in your home directory (on Linux: `~/.wps.yaml`)

The config YAML file will be automatically parsed by the service.

**Important: If you are using containers, the locations refer to paths within the container.**

All parameters mentioned in the [`./example_config.yaml`](./example_config.yaml)
can also be set using environment variables or file secrets.

For naming the environment variables, just prefix the parameter name with `wps_`,
e.g. for the `host` set an environment variable named `wps_host`
(you may use both upper or lower cases, however, it is standard to define all env
variables in upper cases).

To use file secrets, please refer to the
[corresponding section](https://pydantic-docs.helpmanual.io/usage/settings/#secret-support)
of the pydantic documentation.

## HTTP API
An OpenAPI specification for this service can be found [here](./openapi.yaml).

## Architecture and Design:
This is a Python-based service following the Triple Hexagonal Architecture pattern.
It uses protocol/provider pairs and dependency injection mechanisms provided by the
[hexkit](https://github.com/ghga-de/hexkit) library.


## Development

For setting up the development environment, we rely on the
[devcontainer feature](https://code.visualstudio.com/docs/remote/containers) of VS Code
in combination with Docker Compose.

To use it, you have to have Docker Compose as well as VS Code with its "Remote - Containers"
extension (`ms-vscode-remote.remote-containers`) installed.
Then open this repository in VS Code and run the command
`Remote-Containers: Reopen in Container` from the VS Code "Command Palette".

This will give you a full-fledged, pre-configured development environment including:
- infrastructural dependencies of the service (databases, etc.)
- all relevant VS Code extensions pre-installed
- pre-configured linting and auto-formatting
- a pre-configured debugger
- automatic license-header insertion

Inside the devcontainer, a command `dev_install` is available for convenience.
It installs the service with all development dependencies, and it installs pre-commit.

The installation is performed automatically when you build the devcontainer. However,
if you update dependencies in the [`./pyproject.toml`](./pyproject.toml) or the
[`lock/requirements-dev.txt`](./lock/requirements-dev.txt), run it again.

## License

This repository is free to use and modify according to the
[Apache 2.0 License](./LICENSE).

## README Generation

This README file is auto-generated, please see [.readme_generation/README.md](./.readme_generation/README.md)
for details.
