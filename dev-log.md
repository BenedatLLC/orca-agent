# Development log

## 2025-07-12
* Working on removing mcp for kubernetes APIs and calling the underlying K8S Python API directly
* Tried generating Pydantic models for all of K8S, from the OpenAPI spec in the K8S repo. Here's
  the command I ran:
  ```sh
  datamodel-codegen --input /Users/jfischer/code/kubernetes/api/openapi-spec/v3/ --input-file-type openapi --output k8s_models
  ```

