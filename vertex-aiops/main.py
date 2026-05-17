import os
import json
import yaml

from github import Github

import functions_framework

import vertexai
from vertexai.generative_models import GenerativeModel


PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME")
HELM_PATH = os.environ.get("HELM_PATH")


vertexai.init(
    project=PROJECT_ID,
    location=REGION
)

model = GenerativeModel("gemini-2.5-pro")


###############################################################
# GITHUB UPDATE FUNCTION
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
        message=f"AIOps: AI remediation scaling to {replica_count}",
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
        # DATADOG ALERT
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
        # SIMULATED LIVE TELEMETRY
        #######################################################

        cluster_context = {

            "service": "ecom-frontend",

            "cpu_history": [
                22,
                35,
                48,
                67,
                81,
                93
            ],

            "memory_history": [
                40,
                41,
                42,
                43,
                44,
                45
            ],

            "latency_history_ms": [
                120,
                140,
                180,
                260,
                420
            ],

            "request_rate_rps": [
                400,
                600,
                1000,
                1800,
                2600
            ],

            "restart_count": 0,

            "node_pressure": False,

            "current_replicas": 2,

            "hpa_min_replicas": 1,

            "hpa_max_replicas": 5,

            "traffic_pattern":
                "CPU spike every 15 minutes lasting 5 minutes",

            "historical_incidents": [

                {
                    "cpu": 91,
                    "latency": 380,
                    "replicas_needed": 8,
                    "resolved": True
                },

                {
                    "cpu": 72,
                    "latency": 150,
                    "replicas_needed": 2,
                    "resolved": True
                }
            ]
        }

        #######################################################
        # AI REASONING PROMPT
        #######################################################

        prompt = f"""
You are an Autonomous AI SRE platform.

Analyze Kubernetes workload telemetry
and determine the safest remediation strategy.

Telemetry:
{json.dumps(cluster_context, indent=2)}

Your job:

1. Determine whether remediation is required
2. Determine whether issue may self-recover
3. Determine whether scaling frontend is needed
4. Determine whether node scaling is safer
5. Assess risk level
6. Generate confidence score
7. Explain reasoning

IMPORTANT:
Do NOT always scale.

Possible decisions:
- no_action
- scale_frontend
- tune_hpa
- recommend_cluster_autoscaler

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
    "Recurring saturation pattern detected",
    "Latency increasing rapidly",
    "Current HPA insufficient"
  ]
}}
"""

        #######################################################
        # GEMINI AI REASONING
        #######################################################

        print("\n==============================")
        print("CALLING GEMINI AI")
        print("==============================")

        response = model.generate_content(
            prompt
        )

        ai_response = response.text

        print("\n==============================")
        print("RAW GEMINI RESPONSE")
        print("==============================")

        print(ai_response)

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

        decision = json.loads(ai_response)

        #######################################################
        # EXTRACT AI DECISION
        #######################################################

        ai_decision = decision.get(
            "decision",
            "no_action"
        )

        #######################################################
        # AI DECISION LOGGING
        #######################################################

        print("\n==============================")
        print("AI DECISION")
        print("==============================")

        print(json.dumps(
            decision,
            indent=2
        ))

        #######################################################
        # EXECUTE AI REMEDIATION
        #######################################################

        if ai_decision == "scale_frontend":

            replicas = decision.get(
                "recommended_replicas",
                5
            )

            min_replicas = decision.get(
                "recommended_min_replicas",
                2
            )

            max_replicas = decision.get(
                "recommended_max_replicas",
                10
            )

            print("\n==============================")
            print("EXECUTING AI REMEDIATION")
            print("==============================")

            print(
                f"Scaling frontend to {replicas}"
            )

            update_helm_values(
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                replica_count=replicas
            )

            return {
                "status": "success",
                "ai_decision": decision
            }

        #######################################################
        # NO ACTION PATH
        #######################################################

        print("\n==============================")
        print("AI DECIDED NO ACTION")
        print("==============================")

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