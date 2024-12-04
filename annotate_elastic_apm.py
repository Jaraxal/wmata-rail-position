# -*- coding: utf-8 -*-
"""
File: annotate-elastic-apm.py
Author: Michael Young
Date: 2024-09-16
Version: 1.0
License: BSD License

Description:
This Python script uses Kibana's API to annotate an APM service with versioning and messages.
It validates configuration settings and secrets before making requests to the Kibana API.

Usage:
    python annotate-elastic-apm.py --message "Deploy update" --version 1.2.0

Arguments:
    -m, --message : Optional message to include in the APM annotation.
    -v, --version : Optional version number of the service to be annotated.

Dependencies:
    - argparse
    - json
    - sys
    - requests
    - datetime
    - app.config (for configuration settings)

Example:
    python annotate-elastic-apm.py --message "Release 1.2.0" --version 1.2.0

"""

import argparse
import json
import sys
from datetime import datetime, timezone

import requests
from app.config import config as CFG


def main():
    """
    Main function to perform APM service annotation using Kibana's API.

    It performs the following actions:
    1. Validates the required secrets and settings in the configuration file.
    2. Constructs a request payload with the service version and message.
    3. Sends the annotation request to the Kibana API.

    The function exits with code 1 if any required configuration is missing.

    Returns:
        None
    """
    # Validate the configuration
    missing_config = False

    # Check required secrets
    for secrets in ("ES_USERNAME", "ES_PASSWORD"):
        if secrets not in CFG["SECRETS"].keys() and not CFG["SECRETS"][secrets]:
            print(f"{secrets} is not set in app/config/.secrets.toml!")
            missing_config = True

    # Check required settings
    for settings in (
        "KB_URL",
        "APM_SERVICE_NAME",
        "APM_SERVICE_VERSION",
        "APM_ENVIRONMENT",
    ):
        if settings not in CFG["SETTINGS"].keys() and not CFG["SETTINGS"][settings]:
            print(f"{settings} is not set in app/config/settings.toml!")
            missing_config = True

    if missing_config:
        sys.exit(1)

    # Prepare request URL and headers
    url = f"{CFG['SETTINGS']['KB_URL']}/api/apm/services/{CFG['SETTINGS']['APM_SERVICE_NAME']}/annotation"

    header = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
    }

    # Set the version and message for the annotation
    if args.version:
        version = args.version
    else:
        version = f"{CFG['SETTINGS']['APM_SERVICE_VERSION']}"

    if args.message:
        message = f"{version} - {args.message}"
    else:
        message = f"{version}"

    # Prepare the data payload for the request
    data = {
        "@timestamp": formatted_date,
        "service": {
            "version": version,
            "environment": CFG["SETTINGS"]["APM_ENVIRONMENT"],
        },
        "message": message,
    }

    # Annotate the APM service with the given data
    response = requests.post(
        url,
        headers=header,
        data=json.dumps(data),
        auth=(CFG["SECRETS"]["ES_USERNAME"], CFG["SECRETS"]["ES_PASSWORD"]),
    )

    # Print the response from the API
    print(response.json())


if __name__ == "__main__":
    """
    Entry point of the script.

    This section initializes the argument parser, parses the command-line
    arguments, and sets up the required date formatting. It then calls
    the `main` function to execute the APM annotation.

    Command-line arguments:
        -m, --message: Optional message to be included in the APM annotation.
        -v, --version: Optional version number of the service to be annotated.
    
    Returns:
        None
    """
    # Initialize argument parser
    parser = argparse.ArgumentParser(
        description="Script to annotate an APM service in Kibana using the APM annotation API."
    )

    # Adding optional argument for custom message
    parser.add_argument(
        "-m", "--message", help="Short message to be displayed for APM annotation"
    )

    # Adding optional argument for service version
    parser.add_argument(
        "-v", "--version", help="Service version number for APM annotation"
    )

    # Read arguments from command line
    args = parser.parse_args()

    # Get the current date and time in UTC
    now = datetime.now(timezone.utc)

    # Format the date and time as desired for the APM annotation
    formatted_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Execute the main function
    main()
