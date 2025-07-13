import pytest
from orca_agent import k8s_tools

def test_get_namespaces():
    try:
        namespaces = k8s_tools.get_namespaces()
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise

def test_get_pod_summaries():
    try:
        pods = k8s_tools.get_pod_summaries()
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise

def test_get_pod_container_statuses():
    try:
        if k8s_tools.K8S is None:
            k8s_tools.K8S = k8s_tools._get_api_client()
        pod_list = k8s_tools.K8S.list_namespaced_pod(namespace="default").items
        if not pod_list:
            pytest.skip("No pods found in namespace 'default'.")
        pod_name = pod_list[0].metadata.name
        k8s_tools.get_pod_container_statuses(pod_name, "default")
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise

def test_get_pod_events():
    try:
        if k8s_tools.K8S is None:
            k8s_tools.K8S = k8s_tools._get_api_client()
        pod_list = k8s_tools.K8S.list_namespaced_pod(namespace="default").items
        if not pod_list:
            pytest.skip("No pods found in namespace 'default'.")
        pod_name = pod_list[0].metadata.name
        k8s_tools.get_pod_events(pod_name, "default")
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise

def test_get_pod_spec():
    try:
        if k8s_tools.K8S is None:
            k8s_tools.K8S = k8s_tools._get_api_client()
        pod_list = k8s_tools.K8S.list_namespaced_pod(namespace="default").items
        if not pod_list:
            pytest.skip("No pods found in namespace 'default'.")
        pod_name = pod_list[0].metadata.name
        k8s_tools.get_pod_spec(pod_name, "default")
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise

def test_retrieve_logs_for_pod_and_container():
    try:
        if k8s_tools.K8S is None:
            k8s_tools.K8S = k8s_tools._get_api_client()
        pod_list = k8s_tools.K8S.list_namespaced_pod(namespace="default").items
        if not pod_list:
            pytest.skip("No pods found in namespace 'default'.")
        pod_name = pod_list[0].metadata.name
        logs = k8s_tools.get_logs_for_pod_and_container(pod_name, "default")
        assert isinstance(logs, str)
    except Exception as e:
        if e.__class__.__name__ == "K8SConfigError":
            pytest.skip("K8S client could not be initialized.")
        else:
            raise
