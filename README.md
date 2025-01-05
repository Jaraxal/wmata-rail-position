# WMATA Rail Position

This project is an example python program that demonstrates how to query the WMATA api and ingest that data to Elasticsearch.

## Configuration

Before running the app you must update the `config/settings.toml` and `config/.secrets.toml` configuration files.

### config/settings.toml

The `settings.toml` configuration file should have the following configuration settings defined, as appropriate, for your
environment.

```toml
# Elastics configuration
INDEX_NAME = "wmata-rail-position"

# APM configuration
APM_SERVICE_VERSION = "2.0"
APM_ENVIRONMENT = "Development"
APM_SERVICE_NAME = "wmata-rail-position"

# WMATA API configuration
WMATA_API_URL = "https://api.wmata.com/gtfs/rail-gtfsrt-vehiclepositions.pb"
SLEEP_DURATION = "90"
```

### config/.secrets.toml

The `.secrets.toml` configuration file should have the following configuration settings defined, as appropriate, for your
environment.

```toml
# Elastic Server Configuration
ES_USERNAME = "YOUR ELASTICSEARCH USERNAME"
ES_PASSWORD = "YOUR ELASTICSEARCH PASSWORD"
ES_URL = "YOUR ELASTICSEARCH SERVER URL - https://localhost:9200"
KB_URL = "YOUR KIBANA SERVER URL - https://localhost:5601"

# APM Configuration
APM_SECRET_TOKEN = "YOUR ELASTIC APM SECRET TOKEN"
APM_SERVER_URL = "YOUR ELASTIC APM SERVER URL - https://localhost:8201"

# WMATA Configuration
WMATA_API_KEY = "acd9c07bf6f54998ae7024547d88c4b1"
```
