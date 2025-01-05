#!/bin/sh

# Path to the environment file
ENV_FILE="../config/.env"

# Check if the file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: File '$ENV_FILE' does not exist."
    exit 1
fi

# Load environment variables from the file
export $(grep -v '^#' "$ENV_FILE" | xargs)

echo "Environment variables loaded successfully."

echo "Creating WMATA rail position Elasticseach setttings ..."

echo "Uploading component template: mappings"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_component_template/wmata-rail-position-mappings?pretty" -H 'Content-Type: application/json' -d @wmata_rail_position_index_mappings.json

echo "Uploading component template: setttings"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_component_template/wmata-rail-position-settings?pretty" -H 'Content-Type: application/json' -d @wmata_rail_position_index_settings.json

echo "Uploading index template"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_index_template/wmata-rail-position?pretty" -H 'Content-Type: application/json' -d @wmata_rail_position_index_template.json

echo "Uploading ILM policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_ilm/policy/wmata-rail-position?pretty" -H 'Content-Type: application/json' -d @wmata_rail_position_lifecycle_policy.json

echo "Uploading routes enrich policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-routes-policy?pretty" -H 'Content-Type: application/json' -d @wmata_rail_routes_policy.json

echo "Uploading stops enrich policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-stops-policy?pretty" -H 'Content-Type: application/json' -d @wmata_rail_stops_policy.json

echo "Uploading trips enrich policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-trips-policy?pretty" -H 'Content-Type: application/json' -d @wmata_rail_trips_policy.json

echo "Executing routes lookup policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-routes-policy/_execute?pretty"

echo "Executing stops lookup policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-stops-policy/_execute?pretty"

echo "Executing trips lookup policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_enrich/policy/wmata-rail-trips-policy/_execute?pretty"

echo "Uploading lookup policy"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_ingest/pipeline/wmata-rail-lookup?pretty" -H 'Content-Type: application/json' -d @wmata_rail_position_lookup_policy.json

echo "Creating data stream"
curl -X PUT --user ${ES_USERNAME}:${ES_PASSWORD} "${ES_URL}/_data_stream/wmata-rail-position?pretty"


