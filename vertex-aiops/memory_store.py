from google.cloud import bigquery

client = bigquery.Client()


def store_incident(data):

    table_id = (
        "devops-492107.aiops.incident_history"
    )

    errors = client.insert_rows_json(
        table_id,
        [data]
    )

    if errors:

        print(errors)

    else:

        print("Incident stored")