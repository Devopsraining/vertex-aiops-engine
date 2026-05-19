from google.cloud import bigquery

client = bigquery.Client()


def get_recent_incidents():

    query = """
    SELECT *
    FROM `YOUR_PROJECT.aiops.incident_history`
    ORDER BY timestamp DESC
    LIMIT 5
    """

    rows = client.query(query).result()

    return [dict(r) for r in rows]