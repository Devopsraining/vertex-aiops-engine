import time

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.model.query_metrics_optional_parameters import QueryMetricsOptionalParameters

import os


DD_API_KEY = os.environ["DD_API_KEY"]
DD_APP_KEY = os.environ["DD_APP_KEY"]


configuration = {
    "apiKeyAuth": DD_API_KEY,
    "appKeyAuth": DD_APP_KEY
}


def get_metric(query):

    now = int(time.time())

    start = now - 300

    body = {
        "from": start,
        "to": now,
        "query": query
    }

    with ApiClient(configuration) as api_client:

        api_instance = MetricsApi(api_client)

        response = api_instance.query_metrics(
            start,
            now,
            query
        )

        if not response.series:
            return 0

        points = response.series[0].pointlist

        values = [
            p[1] for p in points
            if p[1] is not None
        ]

        if not values:
            return 0

        return round(max(values), 2)