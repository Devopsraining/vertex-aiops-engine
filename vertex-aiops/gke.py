import os

from google.cloud import container_v1

from kubernetes import client
from kubernetes.client import Configuration

import google.auth
from google.auth.transport.requests import Request


PROJECT_ID = os.environ.get("PROJECT_ID")

GKE_CLUSTER_NAME = os.environ.get(
    "GKE_CLUSTER_NAME"
)

GKE_CLUSTER_REGION = os.environ.get(
    "GKE_CLUSTER_REGION"
)


def load_gke_config():

    try:

        print("\n==============================")
        print("LOADING GKE CONFIG")
        print("==============================")

        cluster_client = (
            container_v1.ClusterManagerClient()
        )

        cluster_path = (
            f"projects/{PROJECT_ID}/locations/"
            f"{GKE_CLUSTER_REGION}/clusters/"
            f"{GKE_CLUSTER_NAME}"
        )

        cluster = cluster_client.get_cluster(
            name=cluster_path
        )

        credentials, _ = google.auth.default()

        credentials.refresh(Request())

        configuration = Configuration()

        configuration.host = (
            f"https://{cluster.endpoint}"
        )

        configuration.verify_ssl = False

        configuration.api_key = {
            "authorization":
            "Bearer " + credentials.token
        }

        client.Configuration.set_default(
            configuration
        )

        print("Connected to GKE cluster")

    except Exception as e:

        print(f"GKE config failed: {str(e)}")