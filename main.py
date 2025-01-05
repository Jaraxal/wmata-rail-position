import hashlib
import json
import logging
import logging.config
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List

import elasticapm
import requests
from elasticsearch.exceptions import ConnectionError, RequestError, TransportError
from elasticsearch.helpers import streaming_bulk
from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2
import config
from elasticsearch import Elasticsearch
from logger import configure_logging


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
            if "position" in record["vehicle"]:
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

    ES_URL = loader.get("ES_URL", "secrets")
    ES_USERNAME = loader.get("ES_USERNAME", "secrets")
    ES_PASSWORD = loader.get("ES_PASSWORD", "secrets")

    # Initialize Elasticsearch client
    es_client = Elasticsearch(
        ES_URL,
        basic_auth=(ES_USERNAME, ES_PASSWORD),
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

    APM_SERVER_URL = loader.get("APM_SERVER_URL", "secrets")
    APM_SERVICE_NAME = loader.get("APM_SERVICE_NAME")
    APM_SECRET_TOKEN = loader.get("APM_SECRET_TOKEN", "secrets")
    APM_ENVIRONMENT = loader.get("APM_ENVIRONMENT")
    APM_SERVICE_VERSION = loader.get("APM_SERVICE_VERSION")

    # Create Elastic APM client
    apm_client = elasticapm.Client(
        {
            "SERVER_URL": APM_SERVER_URL,
            "SERVICE_NAME": APM_SERVICE_NAME,
            "SECRET_TOKEN": APM_SECRET_TOKEN,
            "ENVIRONMENT": APM_ENVIRONMENT,
            "SERVICE_VERSION": APM_SERVICE_VERSION
        }
    )

    elasticapm.instrument()  # type: ignore

    WMATA_API = loader.get("WMATA_API_URL")
    WMATA_API_KEY = loader.get("WMATA_API_KEY", "secrets")
    SLEEP_DURATION = int(loader.get("SLEEP_DURATION"))
    INDEX_NAME = loader.get("INDEX_NAME")

    while True:
        apm_client.begin_transaction(transaction_type="script")

        raw_data = query_wmata_api(
            url=WMATA_API,
            api_key=WMATA_API_KEY
        )

        if raw_data:
            formatted_data = format_data(raw_data)
            send_to_elasticsearch(
                es_client, formatted_data, INDEX_NAME
            )
            apm_client.end_transaction(__name__, result="success")

        else:
            apm_client.end_transaction(__name__, result="failure")

        # Sleep to avoid being throttled by the WMATA API
        logger.info(f"Sleeping for {SLEEP_DURATION} seconds.")
        time.sleep(SLEEP_DURATION)


# Configure logging at module level
configure_logging()
logger = logging.getLogger()


loader = config.ConfigLoader()
loader.load_config()

# Define required settings and secrets
REQUIRED_SETTINGS = [
    "INDEX_NAME",
    "APM_SERVICE_NAME",
    "APM_SERVICE_VERSION",
    "APM_ENVIRONMENT",
    "WMATA_API_URL",
    "SLEEP_DURATION",
]

REQUIRED_SECRETS = [
    "ES_USERNAME",
    "ES_PASSWORD",
    "ES_URL",
    "KB_URL",
    "APM_SECRET_TOKEN",
    "APM_SERVER_URL",
    "WMATA_API_KEY",
]

# Validate required keys
loader.validate_config(REQUIRED_SETTINGS, REQUIRED_SECRETS)

if __name__ == "__main__":
    main()
