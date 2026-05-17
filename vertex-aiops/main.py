import os
import json

from github import Github

import vertexai

from vertexai.generative_models import GenerativeModel


PROJECT_ID = os.environ.get("PROJECT_ID")

REGION = os.environ.get("REGION")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

REPO_NAME = os.environ.get("REPO_NAME")

HELM_PATH = os.environ.get("HELM_PATH")


def update_helm_values(max_replicas, min_replicas=1):

    g = Github(GITHUB_TOKEN)

    repo = g.get_repo(REPO_NAME)

    file_path = f"{HELM_PATH}/values.yaml"

    file = repo.get_contents(file_path)

    content = file.decoded_content.decode()

    updated_lines = []

    inside_autoscaling = False

    for line in content.splitlines():

        stripped = line.strip()

        if stripped.startswith("autoscaling:"):

            inside_autoscaling = True

            updated_lines.append(line)

            continue

        if inside_autoscaling and stripped.startswith("minReplicas:"):

            indent = line[:len(line)-len(line.lstrip())]

            updated_lines.append(
                f"{indent}minReplicas: {min_replicas}"
            )

            continue

        if inside_autoscaling and stripped.startswith("maxReplicas:"):

            indent = line[:len(line)-len(line.lstrip())]

            updated_lines.append(
                f"{indent}maxReplicas: {max_replicas}"
            )

            continue

        updated_lines.append(line)

    updated_content = "\n".join(updated_lines)

    repo.update_file(
        path=file_path,
        message=f"AIOps updating HPA maxReplicas to {max_replicas}",
        content=updated_content,
        sha=file.sha
    )


def aiops(request):

    try:

        print("AIOps Triggered")

        vertexai.init(
            project=PROJECT_ID,
            location="us-central1"
        )

        model = GenerativeModel("gemini-2.5-pro")

        prompt = """
        Kubernetes CPU saturation predicted.

        Existing HPA:
        minReplicas=1
        maxReplicas=5

        Historical spikes:
        every 15 mins
        duration 5 mins

        Decide scaling.

        Return ONLY JSON.

        Example:

        {
          "action":"scale_up",
          "maxReplicas":8,
          "minReplicas":2
        }
        """

        response = model.generate_content(prompt)

        cleaned = response.text.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()

        print(cleaned)

        decision = json.loads(cleaned)

        action = decision.get("action")

        if action == "scale_up":

            max_replicas = decision.get(
                "maxReplicas",
                5
            )

            min_replicas = decision.get(
                "minReplicas",
                1
            )

            update_helm_values(
                max_replicas,
                min_replicas
            )

            return {
                "status": "success",
                "maxReplicas": max_replicas,
                "minReplicas": min_replicas
            }

        return {
            "status": "no_action"
        }

    except Exception as e:

        print(str(e))

        return {
            "status": "error",
            "message": str(e)
        }, 500
