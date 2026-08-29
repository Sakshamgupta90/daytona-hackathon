import json
import re
import shlex
from typing import Dict, Any, List, Optional, Union, Set
from urllib.parse import urlparse, parse_qs

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from shared.models import (
        RawUIPayload,
        NormalizedServiceSpec,
        RawEndpoint,
        ParameterDefinition,
        ParameterLocation,
        AuthScheme,
    )
except ImportError:
    from models import (
        RawUIPayload,
        NormalizedServiceSpec,
        RawEndpoint,
        ParameterDefinition,
        ParameterLocation,
        AuthScheme,
    )


class SpecNormalizer:
    """
    Parses heterogeneous input specifications (OpenAPI 3.x, Swagger 2.0, cURL, YAML/JSON)
    into NormalizedServiceSpec with full JSON-Pointer ($ref) resolution and auth deduction.
    """

    @classmethod
    def normalize(cls, payload: RawUIPayload) -> NormalizedServiceSpec:
        format_type = (payload.spec_format or "openapi_json").lower().strip()

        if format_type in ["openapi_json", "swagger_json", "json"]:
            raw_data = payload.spec_content
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            return cls._from_openapi(raw_data, payload)

        elif format_type in ["openapi_yaml", "swagger_yaml", "yaml", "yml"]:
            raw_data = payload.spec_content
            if isinstance(raw_data, str):
                if HAS_YAML:
                    raw_data = yaml.safe_load(raw_data)
                else:
                    # Fallback to json parser if PyYAML is absent
                    raw_data = json.loads(raw_data)
            return cls._from_openapi(raw_data, payload)

        elif format_type == "curl":
            return cls._from_curl(str(payload.spec_content), payload)

        else:
            # Flexible type autodetection
            if isinstance(payload.spec_content, dict):
                return cls._from_openapi(payload.spec_content, payload)
            
            content_str = str(payload.spec_content).strip()
            if content_str.startswith("curl ") or content_str.startswith("curl\n"):
                return cls._from_curl(content_str, payload)

            if HAS_YAML and not (content_str.startswith("{") or content_str.startswith("[")):
                try:
                    parsed_yaml = yaml.safe_load(content_str)
                    if isinstance(parsed_yaml, dict):
                        return cls._from_openapi(parsed_yaml, payload)
                except Exception:
                    pass

            try:
                raw_data = json.loads(content_str)
                return cls._from_openapi(raw_data, payload)
            except Exception as e:
                raise ValueError(f"Unsupported or invalid spec format '{payload.spec_format}': {str(e)}") from e

    @classmethod
    def _resolve_ref(cls, ref: str, root_doc: Dict[str, Any], seen_refs: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Resolves JSON Pointer references ($ref) with recursion and circular reference prevention."""
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return {}

        if seen_refs is None:
            seen_refs = set()

        if ref in seen_refs:
            return {}  # Guard against circular definitions
        seen_refs.add(ref)

        parts = ref.lstrip("#/").split("/")
        curr = root_doc
        for p in parts:
            p = p.replace("~1", "/").replace("~0", "~")
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return {}

        if isinstance(curr, dict) and "$ref" in curr:
            return cls._resolve_ref(curr["$ref"], root_doc, seen_refs)

        return curr if isinstance(curr, dict) else {}

    @classmethod
    def _dereference_schema(cls, schema: Dict[str, Any], root_doc: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """Recursively dereferences schemas and resolves allOf/anyOf."""
        if not isinstance(schema, dict) or depth > 10:
            return schema

        if "$ref" in schema:
            resolved = cls._resolve_ref(schema["$ref"], root_doc)
            merged = {**resolved, **{k: v for k, v in schema.items() if k != "$ref"}}
            return cls._dereference_schema(merged, root_doc, depth + 1)

        # Merge allOf composited schemas
        if "allOf" in schema and isinstance(schema["allOf"], list):
            merged_props: Dict[str, Any] = {}
            required_props: List[str] = list(schema.get("required", []))
            for sub_schema in schema["allOf"]:
                deref_sub = cls._dereference_schema(sub_schema, root_doc, depth + 1)
                if isinstance(deref_sub, dict):
                    merged_props.update(deref_sub.get("properties", {}))
                    required_props.extend(deref_sub.get("required", []))
            result = dict(schema)
            result["properties"] = {**merged_props, **result.get("properties", {})}
            result["required"] = list(set(required_props))
            return result

        return schema

    @classmethod
    def _from_openapi(cls, data: Dict[str, Any], payload: RawUIPayload) -> NormalizedServiceSpec:
        service_name = payload.service_name
        if not service_name:
            title = data.get("info", {}).get("title", "GeneratedService")
            service_name = re.sub(r'[^a-zA-Z0-9_]', '_', title).strip('_') or "GeneratedService"

        base_url = payload.base_url
        if not base_url:
            if "servers" in data and isinstance(data["servers"], list) and len(data["servers"]) > 0:
                base_url = data["servers"][0].get("url", "https://api.example.com")
            elif "host" in data:
                schemes = data.get("schemes", ["https"])
                base_path = data.get("basePath", "")
                base_url = f"{schemes[0]}://{data['host']}{base_path}"
            else:
                base_url = "https://api.example.com"
        base_url = base_url.rstrip('/')

        # Determine Auth Scheme
        auth = payload.auth or AuthScheme()
        if not payload.auth:
            sec_schemes = (
                data.get("components", {}).get("securitySchemes", {})
                or data.get("securityDefinitions", {})
            )
            detected = False
            for _, s_def in sec_schemes.items():
                if "$ref" in s_def:
                    s_def = cls._resolve_ref(s_def["$ref"], data)
                s_type = s_def.get("type", "").lower()
                scheme = s_def.get("scheme", "").lower()

                if s_type in ["http", "bearer"] or scheme == "bearer":
                    auth.auth_type = "bearer"
                    auth.header_name = "Authorization"
                    auth.env_var_name = f"{service_name.upper()}_TOKEN"
                    detected = True
                    break
                elif s_type == "apikey":
                    auth.auth_type = "header" if s_def.get("in", "header").lower() == "header" else "query"
                    auth.header_name = s_def.get("name", "X-API-Key")
                    if auth.auth_type == "query":
                        auth.query_param_name = s_def.get("name", "api_key")
                    auth.env_var_name = f"{service_name.upper()}_API_KEY"
                    detected = True
                    break
                elif scheme == "basic" or s_type == "basic":
                    auth.auth_type = "basic"
                    auth.header_name = "Authorization"
                    auth.env_var_name = f"{service_name.upper()}_BASIC_AUTH"
                    detected = True
                    break
                elif s_type == "oauth2":
                    auth.auth_type = "bearer"
                    auth.header_name = "Authorization"
                    auth.env_var_name = f"{service_name.upper()}_OAUTH_TOKEN"
                    detected = True
                    break

            if not detected and not auth.auth_type:
                auth.auth_type = "none"

        endpoints: List[RawEndpoint] = []
        paths = data.get("paths", {})

        loc_map = {
            "path": ParameterLocation.PATH,
            "query": ParameterLocation.QUERY,
            "header": ParameterLocation.HEADER,
            "body": ParameterLocation.BODY,
            "cookie": ParameterLocation.COOKIE,
        }

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters inherited by all HTTP methods
            common_params = path_item.get("parameters", [])

            for method, op in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    continue
                if not isinstance(op, dict):
                    continue

                op_id = op.get("operationId")
                if not op_id:
                    clean_path = re.sub(r'[^a-zA-Z0-9]+', '_', path.strip('/')).strip('_')
                    op_id = f"{method.lower()}_{clean_path}" if clean_path else f"{method.lower()}_root"
                else:
                    op_id = re.sub(r'[^a-zA-Z0-9_]+', '_', op_id).strip('_')

                summary = op.get("summary", "")
                description = op.get("description", summary)

                parameters: List[ParameterDefinition] = []
                param_names_seen: Set[str] = set()

                # Merge path-level and operation-level parameters
                all_params = list(op.get("parameters", [])) + [
                    p for p in common_params if p.get("name") not in {x.get("name") for x in op.get("parameters", [])}
                ]

                for p in all_params:
                    if "$ref" in p:
                        p = cls._resolve_ref(p["$ref"], data)
                    p_name = p.get("name")
                    if not p_name or p_name in param_names_seen:
                        continue
                    param_names_seen.add(p_name)

                    p_in = p.get("in", "query").lower()
                    loc = loc_map.get(p_in, ParameterLocation.QUERY)
                    schema = p.get("schema", {})
                    if "$ref" in schema:
                        schema = cls._dereference_schema(schema, data)

                    p_type = schema.get("type", p.get("type", "string"))

                    parameters.append(
                        ParameterDefinition(
                            name=p_name,
                            location=loc,
                            type=str(p_type),
                            description=p.get("description", ""),
                            required=bool(p.get("required", loc == ParameterLocation.PATH)),
                            default=schema.get("default", p.get("default")),
                            enum_values=schema.get("enum", p.get("enum")),
                        )
                    )

                # OpenAPI 3.x requestBody resolution
                body_schema = None
                req_body = op.get("requestBody", {})
                if "$ref" in req_body:
                    req_body = cls._resolve_ref(req_body["$ref"], data)

                if req_body and isinstance(req_body, dict):
                    content = req_body.get("content", {})
                    json_media = content.get("application/json", {}) or content.get("*/*", {})
                    raw_body_schema = json_media.get("schema", {})
                    if raw_body_schema:
                        body_schema = cls._dereference_schema(raw_body_schema, data)

                    if body_schema and isinstance(body_schema, dict):
                        properties = body_schema.get("properties", {})
                        required_list = set(body_schema.get("required", []))
                        for prop_name, prop_def in properties.items():
                            if prop_name in param_names_seen:
                                continue
                            param_names_seen.add(prop_name)

                            if "$ref" in prop_def:
                                prop_def = cls._dereference_schema(prop_def, data)

                            parameters.append(
                                ParameterDefinition(
                                    name=prop_name,
                                    location=ParameterLocation.BODY,
                                    type=str(prop_def.get("type", "string")),
                                    description=prop_def.get("description", ""),
                                    required=prop_name in required_list,
                                    default=prop_def.get("default"),
                                    enum_values=prop_def.get("enum"),
                                )
                            )

                # Extract response status codes
                resp_codes = []
                for code in op.get("responses", {}).keys():
                    if str(code).isdigit():
                        resp_codes.append(int(code))
                if not resp_codes:
                    resp_codes = [200]

                endpoints.append(
                    RawEndpoint(
                        operation_id=op_id,
                        path=path,
                        method=method.upper(),
                        summary=summary,
                        description=description,
                        parameters=parameters,
                        request_body_schema=body_schema,
                        response_codes=resp_codes,
                    )
                )

        return NormalizedServiceSpec(
            service_name=service_name,
            base_url=base_url,
            auth=auth,
            endpoints=endpoints,
        )

    @classmethod
    def _from_curl(cls, curl_command: str, payload: RawUIPayload) -> NormalizedServiceSpec:
        cleaned_cmd = curl_command.replace("\\\n", " ").replace("\n", " ").strip()

        # Extract HTTP Method
        method = "GET"
        method_match = re.search(r'(?:-X|--request)\s+([A-Z]+)', cleaned_cmd)
        if method_match:
            method = method_match.group(1).upper()
        elif any(flag in cleaned_cmd for flag in ["-d ", "--data ", "--data-raw ", "--data-binary "]):
            method = "POST"

        # Extract URL
        url_match = re.search(r"'(https?://[^']+)'|\"(https?://[^\"]+)\"|(https?://[^\s'\"]+)", cleaned_cmd)
        url = ""
        if url_match:
            url = next(u for u in url_match.groups() if u)

        parsed = urlparse(url)
        base_url = payload.base_url or (f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else "https://api.example.com")
        path = parsed.path if parsed.path else "/"

        # Auth & Header parsing from cURL
        auth = payload.auth or AuthScheme()
        headers = re.findall(r'(?:-H|--header)\s+[\'"]([^\'"]+)[\'"]', cleaned_cmd)
        
        service_name = payload.service_name or "CustomCurlService"
        for h in headers:
            if ":" in h:
                h_k, h_v = h.split(":", 1)
                h_k, h_v = h_k.strip(), h_v.strip()
                if h_k.lower() == "authorization":
                    if h_v.lower().startswith("bearer "):
                        auth.auth_type = "bearer"
                        auth.header_name = "Authorization"
                        auth.env_var_name = f"{service_name.upper()}_TOKEN"
                    elif h_v.lower().startswith("basic "):
                        auth.auth_type = "basic"
                        auth.header_name = "Authorization"
                        auth.env_var_name = f"{service_name.upper()}_BASIC_AUTH"
                elif "key" in h_k.lower() or "token" in h_k.lower():
                    auth.auth_type = "header"
                    auth.header_name = h_k
                    auth.env_var_name = f"{service_name.upper()}_API_KEY"

        # Extract Query Parameters from URL
        parameters: List[ParameterDefinition] = []
        if parsed.query:
            qs = parse_qs(parsed.query)
            for q_name, q_vals in qs.items():
                parameters.append(
                    ParameterDefinition(
                        name=q_name,
                        location=ParameterLocation.QUERY,
                        type="string",
                        description=f"Query parameter {q_name}",
                        required=False,
                        default=q_vals[0] if q_vals else None,
                    )
                )

        # Extract Body data
        body_schema = None
        data_match = re.search(r'(?:-d|--data|--data-raw|--data-binary)\s+[\'"]([^\'"]+)[\'"]', cleaned_cmd)
        if data_match:
            try:
                body_json = json.loads(data_match.group(1))
                if isinstance(body_json, dict):
                    body_schema = {"type": "object", "properties": {}}
                    for k, v in body_json.items():
                        v_type = "string"
                        if isinstance(v, bool):
                            v_type = "boolean"
                        elif isinstance(v, int):
                            v_type = "integer"
                        elif isinstance(v, float):
                            v_type = "number"
                        elif isinstance(v, list):
                            v_type = "array"
                        elif isinstance(v, dict):
                            v_type = "object"

                        body_schema["properties"][k] = {"type": v_type}
                        parameters.append(
                            ParameterDefinition(
                                name=k,
                                location=ParameterLocation.BODY,
                                type=v_type,
                                description=f"Body field {k}",
                                required=True,
                                default=v,
                            )
                        )
            except Exception:
                pass

        clean_path_slug = re.sub(r'[^a-zA-Z0-9]+', '_', path.strip('/')).strip('_')
        op_name = f"{method.lower()}_{clean_path_slug or 'root'}"

        endpoint = RawEndpoint(
            operation_id=op_name,
            path=path,
            method=method,
            summary=f"Executes {method} request to {path}",
            description=f"Automated cURL tool for {path}",
            parameters=parameters,
            request_body_schema=body_schema,
            response_codes=[200],
        )

        return NormalizedServiceSpec(
            service_name=service_name,
            base_url=base_url,
            auth=auth,
            endpoints=[endpoint],
        )

