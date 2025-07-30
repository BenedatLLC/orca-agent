# Development log

## 2025-07-29
* Moved k8s_tools.py to a separate package (`k8stools`).
* Changed agent.py to make it possible to mock the tools.
* Added test_agent.py, which has a completely mocked out test and a test that
  only mocks the kubernetes tools, but uses a real LLM.
* Added a GitHub workflow to run the tests upon checkin

## 2025-07-13
* Updated k8s_tools.py to use the kubernetes APIs directly. I found that Pydantic.ai
  could not serialize the kubernetes client types. I either hand-created and populated
  associated Pydantic models or I called to_dict() on the return from the K8S APIs.
  In the later case, I made sure to document all the top-level dictionary fields in the
  docstring.
* Updated the agent's prompt, as it wasn't calling the tools. I changed the text to make
  the request for tools firmer.
* Removed uncessary dependencies.

## 2025-07-12
* Working on removing mcp for kubernetes APIs and calling the underlying K8S Python API directly
* Tried generating Pydantic models for all of K8S, from the OpenAPI spec in the K8S repo. Here's
  the command I ran:
  ```sh
  datamodel-codegen --input /Users/jfischer/code/kubernetes/api/openapi-spec/v3/ --input-file-type openapi --output k8s_models
  ```
  Eventually, decided against this.

