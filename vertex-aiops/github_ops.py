import os
import yaml

from github import Github


GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO_NAME = os.environ["REPO_NAME"]
HELM_PATH = os.environ["HELM_PATH"]


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

    current = values["replicaCount"]

    ###########################################################
    # PREVENT DUPLICATE COMMITS
    ###########################################################

    if current == replica_count:

        print(
            "Replica count already same. "
            "Skipping commit."
        )

        return

    values["replicaCount"] = replica_count

    values["autoscaling"]["minReplicas"] = (
        min_replicas
    )

    values["autoscaling"]["maxReplicas"] = (
        max_replicas
    )

    updated_yaml = yaml.dump(values)

    repo.update_file(
        path=file_path,
        message=f"AIOps scaling to {replica_count}",
        content=updated_yaml,
        sha=contents.sha,
        branch="main"
    )

    print(f"Scaled to {replica_count}")