from telemetry import get_metric
from kubernetes import client


###############################################################
# REPLICAS
###############################################################

def get_current_replicas():

    try:

        apps_v1 = client.AppsV1Api()

        deployment = apps_v1.read_namespaced_deployment(
            name="dev-ecom-frontend",
            namespace="ecommerce"
        )

        return {
            "desired": deployment.spec.replicas,
            "ready": deployment.status.ready_replicas or 0
        }

    except Exception as e:

        print(str(e))

        return {
            "desired": 0,
            "ready": 0
        }


###############################################################
# HPA
###############################################################

def get_hpa():

    try:

        autoscaling = client.AutoscalingV2Api()

        hpa = autoscaling.read_namespaced_horizontal_pod_autoscaler(
            name="dev-ecom-frontend-autoscale",
            namespace="ecommerce"
        )

        return {
            "current": hpa.status.current_replicas or 0,
            "desired": hpa.status.desired_replicas or 0,
            "min": hpa.spec.min_replicas or 1,
            "max": hpa.spec.max_replicas or 1
        }

    except Exception as e:

        print(str(e))

        return {
            "current": 0,
            "desired": 0,
            "min": 1,
            "max": 1
        }


###############################################################
# POD RESTARTS
###############################################################

def get_pod_restarts():

    try:

        v1 = client.CoreV1Api()

        pods = v1.list_namespaced_pod(
            namespace="ecommerce"
        )

        restarts = 0

        for pod in pods.items:

            if "dev-ecom-frontend" not in pod.metadata.name:
                continue

            for c in pod.status.container_statuses or []:

                restarts += c.restart_count

        return restarts

    except Exception:

        return 0


###############################################################
# BUILD CONTEXT
###############################################################

def build_live_context():

    replicas = get_current_replicas()

    hpa = get_hpa()

    ###########################################################
    # USE POD_NAME ONLY
    ###########################################################

    cpu = get_metric(
        "avg:kubernetes.cpu.usage.total{pod_name:dev-ecom-frontend*}"
    )

    memory = get_metric(
        "avg:kubernetes.memory.working_set{pod_name:dev-ecom-frontend*}"
    )

    network_rx = get_metric(
        "avg:kubernetes.network.rx_bytes{pod_name:dev-ecom-frontend*}"
    )

    network_tx = get_metric(
        "avg:kubernetes.network.tx_bytes{pod_name:dev-ecom-frontend*}"
    )

    ###########################################################
    # CONVERSIONS
    ###########################################################

    cpu_mcores = round(cpu / 1000000, 2)

    memory_mb = round(
        memory / (1024 * 1024),
        2
    )

    context = {

        "service": "ecom-frontend",

        "current_replicas":
        replicas["desired"],

        "ready_replicas":
        replicas["ready"],

        "hpa_current_replicas":
        hpa["current"],

        "hpa_desired_replicas":
        hpa["desired"],

        "hpa_min_replicas":
        hpa["min"],

        "hpa_max_replicas":
        hpa["max"],

        "cpu_mcores":
        cpu_mcores,

        "memory_mb":
        memory_mb,

        "network_rx_bytes":
        network_rx,

        "network_tx_bytes":
        network_tx,

        "pod_restarts":
        get_pod_restarts()
    }

    print(context)

    return context