import os
import time

from datadog_api_client import ApiClient
from datadog_api_client import Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi


###############################################################
# DATADOG CONFIG
###############################################################

DD_API_KEY = os.environ["DD_API_KEY"]
DD_APP_KEY = os.environ["DD_APP_KEY"]

configuration = Configuration()

configuration.api_key["apiKeyAuth"] = DD_API_KEY
configuration.api_key["appKeyAuth"] = DD_APP_KEY

configuration.server_variables["site"] = (
    "us5.datadoghq.com"
)


###############################################################
# DATADOG METRIC
###############################################################

def get_metric(query):

    try:

        print("\n==============================")
        print(f"QUERY => {query}")
        print("==============================")

        #######################################################
        # TIME RANGE
        #######################################################

        now = int(time.time())

        start = now - 900

        #######################################################
        # DATADOG QUERY
        #######################################################

        with ApiClient(configuration) as api_client:

            api = MetricsApi(api_client)

            response = api.query_metrics(
                _from=start,
                to=now,
                query=query
            )

        #######################################################
        # CONVERT TO PURE PYTHON DICT
        #######################################################

        response_dict = response.to_dict()

        #######################################################
        # DEBUG RESPONSE
        #######################################################

        print(response_dict)

        #######################################################
        # NO SERIES
        #######################################################

        if not response_dict.get("series"):

            print("Series empty")

            return 0

        #######################################################
        # VALUES
        #######################################################

        values = []

        #######################################################
        # LOOP SERIES
        #######################################################

        for series in response_dict["series"]:

            print("\nSERIES FOUND:")
            print(series)

            ###################################################
            # POINTLIST
            ###################################################

            pointlist = series.get(
                "pointlist",
                []
            )

            if not pointlist:

                print("Pointlist empty")

                continue

            ###################################################
            # LOOP POINTS
            ###################################################

            for point in pointlist:

                try:

                    print(f"POINT => {point}")

                    #################################################
                    # EXPECT:
                    # [timestamp, value]
                    #################################################

                    if not isinstance(point, list):

                        continue

                    if len(point) < 2:

                        continue

                    value = point[1]

                    #################################################
                    # NULL
                    #################################################

                    if value is None:

                        continue

                    #################################################
                    # FLOAT
                    #################################################

                    value = float(value)

                    #################################################
                    # NEGATIVE
                    #################################################

                    if value < 0:

                        continue

                    #################################################
                    # STORE
                    #################################################

                    values.append(value)

                except Exception as e:

                    print(
                        f"Point parse failed => {str(e)}"
                    )

        #######################################################
        # VALUES COUNT
        #######################################################

        print(f"VALUES COUNT => {len(values)}")

        #######################################################
        # EMPTY VALUES
        #######################################################

        if not values:

            print(
                f"No parsed values for query: {query}"
            )

            return 0

        #######################################################
        # MAX VALUE
        #######################################################

        metric = round(max(values), 2)

        print(f"SUCCESS => {metric}")

        return metric

    except Exception as e:

        print(f"Metric error => {str(e)}")

        return 0