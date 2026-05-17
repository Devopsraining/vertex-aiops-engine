import json
import os
import textwrap
from github import Github
import vertexai
from vertexai.generative_models import GenerativeModel

# ENV VARIABLES
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME")
HELM_PATH = os.environ.get("HELM_PATH")

# INIT VERTEX AI
vertexai.init(project=PROJECT_ID, location=REGION)

# LOAD GEMINI MODEL
model = GenerativeModel("gemini-1.5-flash")


def update_helm_and_push(new_replicas):
    print(f"Updating replicas to {new_replicas}")
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    file_path = f"{HELM_PATH}/values.yaml"
    file = repo.get_contents(file_path)
    content = file.decoded_content.decode()
    lines = content.splitlines()
    updated_lines = []
    found = False

    for line in lines:
        if line.startswith("replicaCount:"):
            updated_lines.append(f"replicaCount: {new_replicas}")
            found = True
        else:
            updated_lines.append(line)

    if not found:
        updated_lines.append(f"replicaCount: {new_replicas}")

    updated_content = "\n".join(updated_lines)
    repo.update_file(
        path=file_path,
        message=f"AIOps scaling replicas to {new_replicas}",
        content=updated_content,
        sha=file.sha,
    )
    print("GitHub values.yaml updated successfully")


def aiops(request):
    try:
        body = request.get_json(silent=True)
        print("Received Alert:")
        print(body)

        prompt = textwrap.dedent(
            """
            You are an AI SRE engineer.

            Current Kubernetes frontend workload CPU usage is predicted
            to reach saturation soon.

            Decide:
            1. Should replicas increase?
            2. Recommended replica count.

            Return ONLY JSON.

            Example:
            {
              "action": "scale_up",
              "replicas": 6
            }
            """
        )

        response = model.generate_content(prompt)
        print("Gemini Response:")
        print(response.text)

        cleaned = response.text.replace("```json", "").replace("```", "").strip()
        decision = json.loads(cleaned)

        action = decision.get("action")
        replicas = decision.get("replicas")

        if action == "scale_up":
            replicas_int = int(replicas)
            update_helm_and_push(replicas_int)
            return {
                "status": "success",
                "message": f"Scaled to {replicas_int}",
            }

        return {"status": "no_action"}

    except Exception as e:
        print(str(e))
        return {"status": "error", "message": str(e)}, 500