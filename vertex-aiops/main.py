import os
import json
import yaml
import time

from datetime import datetime

import functions_framework

from github import Github

import vertexai
from vertexai.generative_models import GenerativeModel

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client import Configuration

from google.cloud import bigquery


###############################################################
# ENV VARIABLES
###############################################################

PROJECT_ID = os.environ.get("PROJECT_ID")

REGION = os.environ.get("REGION")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

REPO_NAME = os.environ.get("REPO_NAME")

HELM_PATH = os.environ.get("HELM_PATH")

DD_API_KEY = os.environ.get("DD_API_KEY")

DD_APP_KEY = os.environ.get("DD_APP_KEY")


###############################################################
# VERTEX AI INIT
###############################################################

vertexai.init(
    project=PROJECT_ID,
    location=REGION
)

model = GenerativeModel(
    "gemini-2.5-pro"
)


###############################################################
# BIGQUERY CLIENT
###############################################################

bq_client = bigquery.Client()


###############################################################
# DATADOG CONFIG
###############################################################

dd_configuration = Configuration()

dd_configuration.api_key = {
    "apiKeyAuth": DD_API_KEY,
    "appKeyAuth": DD_APP_KEY
}


###############################################################
# DATADOG METRIC QUERY
###############################################################

def query_metric(query):

    try:

        now = int(time.time())

        start = now - 300

        with ApiClient(dd_configuration) as api_client:

            api = MetricsApi(api_client)

            response = api.query_metrics(
                _from=start,
                to=now,
                query=query
            )

            if not response.series:
                return 0

            points = response.series[0].pointlist

            values = [
                p[1]
                for p in points
                if p[1] is not None
            ]

            if not values:
                return 0

            return round(max(values), 2)

    except Exception as e:

        print(f"Metric query failed: {str(e)}")

        return 0


###############################################################
# BUILD LIVE TELEMETRY
###############################################################

def build_live_context():

    cpu = query_metric(
        "max:kubernetes.cpu.usage.total{kube_namespace:ecommerce,pod_name:dev-ecom-frontend*}"
    )

    memory = query_metric(
        "max:kubernetes.memory.usage{kube_namespace:ecommerce,pod_name:dev-ecom-frontend*}"
    )

    latency = query_metric(
        "avg:trace.http.request.duration{service:ecom-frontend}"
    )

    request_rate = query_metric(
        "sum:trace.http.request.hits{service:ecom-frontend}"
    )

    error_rate = query_metric(
        "sum:trace.http.request.errors{service:ecom-frontend}"
    )

    return {

        "service": "ecom-frontend",

        "cpu_percent": cpu,

        "memory_usage": memory,

        "latency_ms": latency,

        "request_rate": request_rate,

        "error_rate": error_rate
    }


###############################################################
# FETCH INCIDENT MEMORY
###############################################################

def get_recent_incidents():

    try:

        query = f"""
        SELECT
            timestamp,
            service,
            cpu,
            memory,
            latency,
            request_rate,
            error_rate,
            ai_decision,
            replicas_before,
            replicas_after,
            outcome
        FROM `{PROJECT_ID}.aiops.incident_history`
        ORDER BY timestamp DESC
        LIMIT 5
        """

        rows = bq_client.query(query).result()

        incidents = []

        for row in rows:

            incidents.append({

                "timestamp": str(row.timestamp),

                "service": row.service,

                "cpu": row.cpu,

                "memory": row.memory,

                "latency": row.latency,

                "request_rate": row.request_rate,

                "error_rate": row.error_rate,

                "ai_decision": row.ai_decision,

                "replicas_before": row.replicas_before,

                "replicas_after": row.replicas_after,

                "outcome": row.outcome
            })

        return incidents

    except Exception as e:

        print(f"Incident fetch failed: {str(e)}")

        return []


###############################################################
# STORE INCIDENT MEMORY
###############################################################

def store_incident(data):

    try:

        table_id = f"{PROJECT_ID}.aiops.incident_history"

        errors = bq_client.insert_rows_json(
            table_id,
            [data]
        )

        if errors:

            print(errors)

    except Exception as e:

        print(f"BigQuery insert failed: {str(e)}")


###############################################################
# UPDATE HELM VALUES
###############################################################

def update_helm_values(
    min_replicas,
    max_replicas,
    replica_count
):

    g = Github(GITHUB_TOKEN)

    repo = g.get_repo(REPO_NAME)

    file_path = f"{HELM_PATH}/values.yaml"

    contents = repo.get_contents(file_path)

    values = yaml.safe_load(
        contents.decoded_content
    )

    values["autoscaling"]["enabled"] = True

    values["autoscaling"]["minReplicas"] = min_replicas

    values["autoscaling"]["maxReplicas"] = max_replicas

    values["replicaCount"] = replica_count

    updated_yaml = yaml.dump(
        values,
        default_flow_style=False
    )

    repo.update_file(
        path=file_path,
        message=f"AIOps remediation scaling to {replica_count}",
        content=updated_yaml,
        sha=contents.sha,
        branch="main"
    )


###############################################################
# MAIN CLOUD FUNCTION
###############################################################

@functions_framework.http
def aiops(request):

    try:

        #######################################################
        # DATADOG EVENT
        #######################################################

        request_json = request.get_json(
            silent=True
        ) or {}

        print("\n==============================")
        print("DATADOG EVENT")
        print("==============================")

        print(json.dumps(
            request_json,
            indent=2
        ))

        #######################################################
        # LIVE TELEMETRY
        #######################################################

        cluster_context = build_live_context()

        #######################################################
        # HISTORICAL INCIDENTS
        #######################################################

        historical_incidents = get_recent_incidents()

        #######################################################
        # BUILD AI PROMPT
        #######################################################

        prompt = f"""
You are an enterprise Autonomous AI SRE platform.

Analyze Kubernetes telemetry and determine
the safest remediation strategy.

##################################################
CURRENT TELEMETRY
##################################################

{json.dumps(cluster_context, indent=2)}

##################################################
HISTORICAL INCIDENT MEMORY
##################################################

{json.dumps(historical_incidents, indent=2)}

##################################################
YOUR RESPONSIBILITIES
##################################################

1. Analyze workload saturation
2. Detect recurring incident patterns
3. Determine whether remediation is required
4. Decide whether scaling frontend is required
5. Decide whether scale-down is safe
6. Avoid unnecessary scaling
7. Assess operational risk
8. Generate confidence score
9. Learn from historical outcomes

##################################################
IMPORTANT RULES
##################################################

- Do NOT always scale
- Prefer minimal safe remediation
- Use historical incidents heavily
- Avoid repeating failed remediations
- Prevent scaling oscillation

##################################################
POSSIBLE DECISIONS
##################################################

- no_action
- scale_frontend
- scale_down_frontend
- tune_hpa
- recommend_cluster_autoscaler

##################################################
RETURN FORMAT
##################################################

Return ONLY valid JSON.

Example:

{{
  "decision": "scale_frontend",
  "recommended_replicas": 8,
  "recommended_min_replicas": 2,
  "recommended_max_replicas": 10,
  "risk_level": "high",
  "confidence": "93%",
  "reasoning": [
    "CPU saturation sustained",
    "Latency increasing rapidly",
    "Historical incidents required scaling to 8 replicas"
  ]
}}
"""

        #######################################################
        # GEMINI AI ANALYSIS
        #######################################################

        print("\n==============================")
        print("CALLING GEMINI")
        print("==============================")

        response = model.generate_content(
            prompt
        )

        ai_response = response.text

        #######################################################
        # CLEAN RESPONSE
        #######################################################

        ai_response = ai_response.replace(
            "```json",
            ""
        )

        ai_response = ai_response.replace(
            "```",
            ""
        )

        ai_response = ai_response.strip()

        #######################################################
        # PARSE RESPONSE
        #######################################################

        decision = json.loads(ai_response)

        print("\n==============================")
        print("AI DECISION")
        print("==============================")

        print(json.dumps(
            decision,
            indent=2
        ))

        #######################################################
        # EXTRACT DECISION
        #######################################################

        ai_decision = decision.get(
            "decision",
            "no_action"
        )

        replicas = decision.get(
            "recommended_replicas",
            2
        )

        min_replicas = decision.get(
            "recommended_min_replicas",
            1
        )

        max_replicas = decision.get(
            "recommended_max_replicas",
            5
        )

        #######################################################
        # SCALE FRONTEND
        #######################################################

        if ai_decision == "scale_frontend":

            print("\n==============================")
            print("SCALING FRONTEND UP")
            print("==============================")

            ###################################################
            # STORE OLD TELEMETRY
            ###################################################

            old_latency = cluster_context["latency_ms"]

            old_cpu = cluster_context["cpu_percent"]

            old_error_rate = cluster_context["error_rate"]

            ###################################################
            # EXECUTE HELM REMEDIATION
            ###################################################

            update_helm_values(
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                replica_count=replicas
            )

            ###################################################
            # WAIT FOR STABILIZATION
            ###################################################

            print("\nWaiting for ArgoCD stabilization...")

            time.sleep(120)

            ###################################################
            # FETCH NEW TELEMETRY
            ###################################################

            new_context = build_live_context()

            new_latency = new_context["latency_ms"]

            new_cpu = new_context["cpu_percent"]

            new_error_rate = new_context["error_rate"]

            ###################################################
            # VERIFY REMEDIATION
            ###################################################

            if (

                new_latency < old_latency

                and new_cpu < old_cpu

                and new_error_rate <= old_error_rate

            ):

                outcome = "resolved"

            else:

                outcome = "failed"

            ###################################################
            # STORE MEMORY
            ###################################################

            store_incident({

                "timestamp": datetime.utcnow().isoformat(),

                "service": cluster_context["service"],

                "cpu": new_cpu,

                "memory": new_context["memory_usage"],

                "latency": new_latency,

                "request_rate": new_context["request_rate"],

                "error_rate": new_error_rate,

                "ai_decision": ai_decision,

                "replicas_before": 2,

                "replicas_after": replicas,

                "outcome": outcome
            })

            ###################################################
            # RETURN SUCCESS
            ###################################################

            return {

                "status": "success",

                "outcome": outcome,

                "before": {

                    "cpu": old_cpu,

                    "latency": old_latency,

                    "error_rate": old_error_rate
                },

                "after": {

                    "cpu": new_cpu,

                    "latency": new_latency,

                    "error_rate": new_error_rate
                },

                "ai_decision": decision
            }

        #######################################################
        # SCALE DOWN
        #######################################################

        elif ai_decision == "scale_down_frontend":

            print("\n==============================")
            print("SCALING FRONTEND DOWN")
            print("==============================")

            update_helm_values(
                min_replicas=1,
                max_replicas=3,
                replica_count=2
            )

            store_incident({

                "timestamp": datetime.utcnow().isoformat(),

                "service": cluster_context["service"],

                "cpu": cluster_context["cpu_percent"],

                "memory": cluster_context["memory_usage"],

                "latency": cluster_context["latency_ms"],

                "request_rate": cluster_context["request_rate"],

                "error_rate": cluster_context["error_rate"],

                "ai_decision": ai_decision,

                "replicas_before": replicas,

                "replicas_after": 2,

                "outcome": "resolved"
            })

            return {

                "status": "scaled_down",

                "ai_decision": decision
            }

        #######################################################
        # NO ACTION
        #######################################################

        else:

            print("\n==============================")
            print("NO ACTION REQUIRED")
            print("==============================")

            store_incident({

                "timestamp": datetime.utcnow().isoformat(),

                "service": cluster_context["service"],

                "cpu": cluster_context["cpu_percent"],

                "memory": cluster_context["memory_usage"],

                "latency": cluster_context["latency_ms"],

                "request_rate": cluster_context["request_rate"],

                "error_rate": cluster_context["error_rate"],

                "ai_decision": ai_decision,

                "replicas_before": 2,

                "replicas_after": 2,

                "outcome": "no_action"
            })

            return {

                "status": "no_action",

                "ai_decision": decision
            }

    except Exception as e:

        print(str(e))

        return {

            "status": "error",

            "message": str(e)

        }, 500