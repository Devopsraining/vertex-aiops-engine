from telemetry import get_metric


def build_live_context():

    cpu = get_metric(
        "max:kubernetes.cpu.usage.total{kube_namespace:ecommerce,pod_name:dev-ecom-frontend*}"
    )

    memory = get_metric(
        "max:kubernetes.memory.usage{kube_namespace:ecommerce,pod_name:dev-ecom-frontend*}"
    )

    latency = get_metric(
        "avg:trace.http.request.duration{service:ecom-frontend}"
    )

    requests = get_metric(
        "sum:trace.http.request.hits{service:ecom-frontend}"
    )

    errors = get_metric(
        "sum:trace.http.request.errors{service:ecom-frontend}"
    )

    return {
        "service": "ecom-frontend",
        "cpu_percent": cpu,
        "memory_usage": memory,
        "latency_ms": latency,
        "request_rate": requests,
        "error_rate": errors
    }