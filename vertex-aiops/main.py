import os
import json
import yaml

import vertexai

from github import Github

from vertexai.generative_models import GenerativeModel

PROJECT_ID = os.environ["PROJECT_ID"]

REGION = os.environ["REGION"]

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

REPO_NAME = os.environ["REPO_NAME"]

VALUES_FILE = "fraud-helm/ecommerce-frontend/values.yaml"

vertexai.init(
    project=PROJECT_ID,
    location=REGION
)

model = GenerativeModel("gemini-1.5-flash")


def aiops(request):

    body = request.get_json()

    cpu = body.get("cpu", 0)

    deployment = body.get(
        "deployment",
        "ecom-frontend"
    )

    replicas = body.get(
        "replicas",
        3
    )

    prompt = f"""
You are an enterprise AI Ops engine.

Current Kubernetes state:

Deployment: {deployment}

CPU Usage: {cpu}%

Current replicas: {replicas}

Historical pattern:
- CPU spikes every 15 mins
- Spike duration = 5 mins

Rules:
- Scale UP if CPU > 80
- Scale DOWN if CPU < 35 for long time
- Max replicas = 4
- Min replicas = 2

Return ONLY JSON.

Examples:

{{
  "action":"scale_up",
  "replicas":4
}}

OR

{{
  "action":"scale_down",
  "replicas":2
}}
"""

    response = model.generate_content(prompt)

    text = response.text.strip()

    text = text.replace("```json", "")
    text = text.replace("```", "")

    decision = json.loads(text)

    target_replicas = decision["replicas"]

    g = Github(GITHUB_TOKEN)

    repo = g.get_repo(REPO_NAME)

    contents = repo.get_contents(
        VALUES_FILE
    )

    values = yaml.safe_load(
        contents.decoded_content.decode()
    )

    values["replicaCount"] = target_replicas

    updated_yaml = yaml.dump(
        values,
        sort_keys=False
    )

    repo.update_file(
        path=VALUES_FILE,
        message=f"Vertex AI Ops scaling to {target_replicas}",
        content=updated_yaml,
        sha=contents.sha,
        branch="main"
    )

    return {
        "status":"success",
        "decision":decision
    }