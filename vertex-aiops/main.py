import json
import os

import functions_framework
import vertexai

from datetime import datetime

from vertexai.generative_models import (
    GenerativeModel
)

from context_builder import build_live_context
from incident_history import get_recent_incidents
from memory_store import store_incident
from github_ops import update_helm_values

from gke import load_gke_config


PROJECT_ID = os.environ["PROJECT_ID"]

REGION = os.environ["REGION"]


vertexai.init(
    project=PROJECT_ID,
    location=REGION
)

model = GenerativeModel(
    "gemini-2.5-pro"
)


###############################################################
# MAIN
###############################################################

@functions_framework.http
def aiops(request):

    try:

        load_gke_config()

        event = request.get_json(
            silent=True
        ) or {}

        print(json.dumps(event))

        #######################################################
        # ONLY TRIGGERED ALERTS
        #######################################################

        if (
            event.get("alert_transition")
            != "Triggered"
        ):

            return {
                "status": "ignored_recovery"
            }

        #######################################################
        # TELEMETRY
        #######################################################

        telemetry = build_live_context()

        #######################################################
        # HARD SAFETY GUARD
        #######################################################

        if (

            telemetry["cpu_mcores"] == 0

            and

            telemetry["memory_mb"] == 0

            and

            telemetry["network_rx_bytes"] == 0
        ):

            return {
                "status": "invalid_telemetry"
            }

        #######################################################
        # INCIDENTS
        #######################################################

        incidents = get_recent_incidents()

        #######################################################
        # PROMPT
        #######################################################

        prompt = f"""
You are an autonomous SRE AI.

Analyze telemetry and recommend scaling.

CURRENT TELEMETRY:
{json.dumps(telemetry, indent=2)}

INCIDENT HISTORY:
{json.dumps(incidents, indent=2, default=str)}

RULES:

- Never scale below 2
- Prevent oscillation
- Scale only if truly needed
- If ready replicas < current replicas,
  scale up
- If CPU > 200 mcores,
  scale up
- If memory > 700 MB,
  scale up

Return ONLY JSON.

Example:

{{
  "decision":"scale_up",
  "recommended_replicas":4,
  "recommended_min_replicas":2,
  "recommended_max_replicas":5,
  "reason":"CPU spike"
}}
"""

        #######################################################
        # GEMINI
        #######################################################

        response = model.generate_content(
            prompt
        )

        decision = (
            response.text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        decision = json.loads(decision)

        print(json.dumps(decision))

        #######################################################
        # DECISION
        #######################################################

        action = decision.get(
            "decision",
            "no_action"
        )

        replicas = decision.get(
            "recommended_replicas",
            telemetry["current_replicas"]
        )

        min_replicas = decision.get(
            "recommended_min_replicas",
            2
        )

        max_replicas = decision.get(
            "recommended_max_replicas",
            5
        )

        #######################################################
        # SCALE
        #######################################################

        if action == "scale_up":

            update_helm_values(
                min_replicas,
                max_replicas,
                replicas
            )

        #######################################################
        # STORE MEMORY
        #######################################################

        store_incident({

            "timestamp":
            datetime.utcnow().isoformat(),

            "service":
            telemetry["service"],

            "cpu_mcores":
            telemetry["cpu_mcores"],

            "memory_mb":
            telemetry["memory_mb"],

            "decision":
            action,

            "replicas":
            replicas
        })

        return {

            "status": "success",

            "decision": decision,

            "telemetry": telemetry
        }

    except Exception as e:

        print(str(e))

        return {
            "status": "error",
            "message": str(e)
        }, 500