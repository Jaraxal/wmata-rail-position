import hashlib
import json
import logging
import logging.config
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import ecs_logging
import elasticapm
import requests
from config import config as CFG
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError, TransportError
from elasticsearch.helpers import streaming_bulk
from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2


def configure_logging():
    """
    Configures structured logging with ECS (Elastic Common Schema) formatting.

    This function sets up the logging configuration for the application, enabling
    structured log output in ECS format. Logs are output to the console using
    the `ecs_logging.StdlibFormatter`. The configuration includes a root logger
    and an application-specific logger.

    Logging Configuration:
        - **Formatters**: Uses the ECS formatter (`ecs_logging.StdlibFormatter`) for structured logs.
        - **Handlers**: Configures a console handler to output logs to `stdout`.
        - **Root Logger**: Logs messages at the `INFO` level and outputs them to the console.
        - **Application Logger**: Configures a logger named `wmata-rail-position` with the same console handler,
          set to `INFO` level, and prevents propagation to the root logger.

    Dependencies:
        - `ecs_logging`: A library that provides an ECS-compatible formatter for Python logging.
        - `logging.config.dictConfig`: Used to apply the logging configuration.

    Notes:
        - This setup ensures that all logs are consistent with ECS, making them compatible
          with tools like Elastic Observability for centralized monitoring and analysis.
        - The `wmata-rail-position` logger can be used for application-specific logging needs.

    """
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "ecs": {  # ECS formatter for structured logs
                "()": ecs_logging.StdlibFormatter,
            }
        },
        "handlers": {
            "console": {  # Console handler with ECS formatter
                "class": "logging.StreamHandler",
                "formatter": "ecs",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {  # Root logger
            "level": "INFO",
            "handlers": ["console"],
        },
        "loggers": {
            "wmata-rail-position": {  # Application-specific logger
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            }
        },
    }

    logging.config.dictConfig(logging_config)


def validate_config(cfg: dict, required_keys: List[str], category: str) -> None:
    """
    Validates the presence of required keys in a specific configuration category.
    Logs missing keys and exits the program if any are missing.

    :param cfg: The configuration dictionary to validate.
    :param required_keys: A list of required keys to check in the configuration.
    :param category: The category name (e.g., 'SETTINGS' or 'SECRETS').
    """
    missing_keys = [
        key
        for key in required_keys
        if key not in cfg.get(category, {}) or not cfg[category][key]
    ]

    if missing_keys:
        logger.error(
            f"Missing configuration {category.lower()} in app/config/{category.lower()}.toml:"
        )
        for key in missing_keys:
            logger.error(f" - {key}")
        sys.exit(1)


def format_unix_timestamp(timestamp: int) -> str:
    """
    Converts a UNIX timestamp to ISO 8601 format (e.g., '2015-01-01T12:10:30Z').

    Args:
        timestamp (int): UNIX timestamp to be converted.

    Returns:
        str: Formatted date-time string in ISO 8601 format.
    """
    # Convert the timestamp to a datetime object in UTC
    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)

    # Format the datetime object to ISO 8601 format
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# Fetch data from WMATA API
def query_wmata_api(url: str, api_key: str) -> gtfs_realtime_pb2.FeedMessage | None:  # type: ignore
    """
    Fetches data from the WMATA API and parses it into a GTFS-realtime FeedMessage.

    This function sends a GET request to the specified WMATA API endpoint using the provided API key.
    The response is parsed into a `gtfs_realtime_pb2.FeedMessage` object. If an error occurs during
    the request or parsing process, the exception is logged, captured by Elastic APM, and the function
    returns `None`.

    Args:
        url (str): The WMATA API endpoint URL.
        api_key (str): The API key for authenticating with the WMATA API.

    Returns:
        gtfs_realtime_pb2.FeedMessage | None: A `FeedMessage` object if the data is successfully fetched
                                              and parsed, otherwise `None`.

    Raises:
        None: All exceptions are logged and captured without being raised directly.

    Notes:
        - Uses Elastic APM for monitoring execution spans and capturing exceptions.
        - Assumes that the `requests` and `gtfs_realtime_pb2` libraries are correctly configured.
        - Logs errors using the `logger` object.
    """
    logger.info("Fetching data from WMATA API.")
    with elasticapm.capture_span("query_wmata_api"):  # type: ignore
        try:
            feed = gtfs_realtime_pb2.FeedMessage()  # type: ignore
            response = requests.get(url, headers={"api_key": api_key})
            feed.ParseFromString(response.content)
            return feed
        except requests.exceptions.RequestException as e:
            logger.error("Error fetching data from WMATA API.")
            logger.error(e)
            apm_client.capture_exception()
            return None


def format_data(records: gtfs_realtime_pb2.FeedMessage) -> List[Dict[str, Any]]:  # type: ignore
    with elasticapm.capture_span("format_data"):  # type: ignore
        record_list = []

        for entity in records.entity:  # type: ignore
            # Convert protobuf messages to dictionary
            record = MessageToDict(entity)

            # Create a sha256 hash of the json record as a unique id for Elasticearch
            record_string = json.dumps(record, sort_keys=True)
            record_hash = hashlib.sha256(record_string.encode("utf-8")).hexdigest()
            record["hash"] = record_hash

            # Extract location data if available
            if (
                record["vehicle"]["position"]["longitude"]
                and record["vehicle"]["position"]["latitude"]
            ):
                record["location"] = {
                    "lon": record["vehicle"]["position"]["longitude"],
                    "lat": record["vehicle"]["position"]["latitude"],
                }

            record["@timestamp"] = format_unix_timestamp(record["vehicle"]["timestamp"])

            record_list.append(record)
        return record_list


def send_to_elasticsearch(
    es_client: Elasticsearch, records: List[Dict[str, Any]], index_name: str
) -> None:
    """
    Send data to Elasticsearch for indexing.

    Args:
        es_client (Elasticsearch): Elasticsearch client instance.
        records (List[Dict[str, Any]]): Data records to index.
        index_name (str): Elasticsearch index name.
    """
    with elasticapm.capture_span(name="send_to_elasticsearch"):  # type: ignore
        logger.info(
            f"Sending {len(records)} records to Elasticsearch index {index_name}."
        )
        try:
            for ok, action in streaming_bulk(
                client=es_client,
                actions=document_generator(records, index_name),
                raise_on_error=False,
            ):
                if not ok:
                    logger.error(f"Failed to index document: {action}")
        except (ConnectionError, TransportError, RequestError) as e:
            logger.error(f"Error during Elasticsearch indexing: {e}")


def document_generator(
    records: List[Dict[str, Any]], index_name: str
) -> Generator[Dict[str, Any], None, None]:
    """
    Generate documents for bulk Elasticsearch indexing.

    Args:
        records (List[Dict[str, Any]]): Data records to index.
        index_name (str): Elasticsearch index name.

    Yields:
        Dict[str, Any]: Document for Elasticsearch indexing.
    """
    for record in records:
        yield {
            "_op_type": "create",
            "_index": index_name,
            "_id": record["hash"],
            "_source": record,
        }


def main():

    # Define required settings and secrets
    required_settings = [
        "INDEX_NAME",
        "APM_SERVICE_NAME",
        "APM_SERVICE_VERSION",
        "APM_ENVIRONMENT",
        "WMATA_API_URL",
        "SLEEP_DURATION",
    ]

    required_secrets = [
        "ES_USERNAME",
        "ES_PASSWORD",
        "ES_URL",
        "KB_URL",
        "APM_SECRET_TOKEN",
        "APM_SERVER_URL",
        "WMATA_API_KEY",
    ]

    # Validate configurations
    validate_config(CFG, required_settings, "SETTINGS")
    validate_config(CFG, required_secrets, "SECRETS")

    # Initialize Elasticsearch client
    es_client = Elasticsearch(
        CFG["SECRETS"]["ES_URL"],
        basic_auth=(CFG["SECRETS"]["ES_USERNAME"], CFG["SECRETS"]["ES_PASSWORD"]),
    )

    # Validate the Elasticsearch connection
    try:
        if not es_client.ping():
            logger.error(
                "Failed to connect to Elasticsearch. Please check the configuration."
            )
            sys.exit(1)
        else:
            logger.info("Successfully connected to Elasticsearch.")
    except ConnectionError as e:
        logger.error(f"Elasticsearch connection error: {e}")
        sys.exit(1)

    # Create Elastic APM client
    apm_client = elasticapm.Client(
        {
            "SERVER_URL": CFG["SECRETS"]["APM_SERVER_URL"],
            "SERVICE_NAME": CFG["SETTINGS"]["APM_SERVICE_NAME"],
            "SECRET_TOKEN": CFG["SECRETS"]["APM_SECRET_TOKEN"],
            "ENVIRONMENT": CFG["SETTINGS"]["APM_ENVIRONMENT"],
            "SERVICE_VERSION": CFG["SETTINGS"]["APM_SERVICE_VERSION"],
        }
    )

    elasticapm.instrument()  # type: ignore

    while True:
        apm_client.begin_transaction(transaction_type="script")

        raw_data = query_wmata_api(
            url=CFG["SECRETS"]["WMATA_API_URL"],
            api_key=CFG["SECRETS"]["WMATA_API_KEY"],
        )

        if raw_data:
            formatted_data = format_data(raw_data)
            send_to_elasticsearch(
                es_client, formatted_data, CFG["SETTINGS"]["INDEX_NAME"]
            )
            apm_client.end_transaction(__name__, result="success")

        else:
            apm_client.end_transaction(__name__, result="failure")

        # Sleep to avoid being throttled by the WMATA API
        logger.info(f"Sleeping for {CFG['SETTINGS']['SLEEP_DURATION']} seconds.")
        time.sleep(int(CFG["SETTINGS"]["SLEEP_DURATION"]))


# Configure logging at module level so it's accessible globally
configure_logging()

# Create the logger for the application
logger = logging.getLogger("wmata-rail-position")
logger.info("Logging configured successfully!")

if __name__ == "__main__":
    main()
