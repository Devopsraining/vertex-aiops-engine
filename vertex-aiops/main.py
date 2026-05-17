import os
import json

import vertexai

from github import Github

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


model = GenerativeModel("gemini-2.0-flash-001")


def update_helm_values(replicas):

    g = Github(GITHUB_TOKEN)

    repo = g.get_repo(REPO_NAME)

    file_path = f"{HELM_PATH}/values.yaml"

    file = repo.get_contents(file_path)

    content = file.decoded_content.decode()

    updated_lines = []

    found = False

    for line in content.splitlines():

        if line.startswith("replicaCount:"):

            updated_lines.append(f"replicaCount: {replicas}")

            found = True

        else:

            updated_lines.append(line)

    if not found:

        updated_lines.append(f"replicaCount: {replicas}")

    updated_content = "\n".join(updated_lines)

    repo.update_file(
        path=file_path,
        message=f"AIOps scaling replicas to {replicas}",
        content=updated_content,
        sha=file.sha
    )

    print("GitHub updated successfully")


def aiops(request):

    try:

        print("AIOps Triggered")

        prompt = """
        CPU spike prediction detected.

        Decide:
        1. scale_up
        2. recommended replicas

        Return JSON only.

        Example:
        {
          "action": "scale_up",
          "replicas": 5
        }
        """

        response = model.generate_content(prompt)

        cleaned = response.text.replace("```json", "").replace("```", "").strip()

        print(cleaned)

        decision = json.loads(cleaned)

        action = decision.get("action")

        replicas = decision.get("replicas")

        if action == "scale_up":

            update_helm_values(replicas)

            return {
                "status": "success",
                "replicas": replicas
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