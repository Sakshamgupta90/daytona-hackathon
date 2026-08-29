from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class ParameterLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    BODY = "body"
    COOKIE = "cookie"


class ParameterDefinition(BaseModel):
    name: str
    location: ParameterLocation
    type: str = "string"  # string, integer, boolean, number, array, object
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    enum_values: Optional[List[str]] = None


class RawEndpoint(BaseModel):
    operation_id: Optional[str] = None
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    summary: str = ""
    description: str = ""
    parameters: List[ParameterDefinition] = Field(default_factory=list)
    request_body_schema: Optional[Dict[str, Any]] = None
    response_codes: List[int] = Field(default_factory=lambda: [200])


class AuthScheme(BaseModel):
    auth_type: str = "none"  # "none", "bearer", "header", "query", "basic", "oauth2"
    header_name: str = "Authorization"
    query_param_name: Optional[str] = None
    env_var_name: str = "API_KEY"
    test_token: Optional[str] = None


class NormalizedServiceSpec(BaseModel):
    service_name: str
    base_url: str
    auth: AuthScheme
    endpoints: List[RawEndpoint] = Field(default_factory=list)


class PlannedToolParameter(BaseModel):
    name: str
    raw_name: Optional[str] = None  # Wire API parameter name if different from Python identifier
    python_type: str = "str"  # "str", "int", "float", "bool", "Optional[str]", "Optional[int]", etc.
    description: str = ""
    required: bool = True
    location: ParameterLocation = ParameterLocation.QUERY
    default_value: Optional[str] = None

    def get_wire_name(self) -> str:
        return self.raw_name or self.name


class PlannedTestCase(BaseModel):
    test_id: str
    description: str
    input_arguments: Dict[str, Any] = Field(default_factory=dict)
    expected_http_status: int = 200


class PlannedTool(BaseModel):
    tool_name: str
    docstring: str
    http_method: str
    endpoint_path: str
    parameters: List[PlannedToolParameter] = Field(default_factory=list)
    test_cases: List[PlannedTestCase] = Field(default_factory=list)


class PlannedMCPBlueprint(BaseModel):
    service_name: str
    base_url: str
    auth: AuthScheme
    tools: List[PlannedTool] = Field(default_factory=list)
    system_instruction: str = ""


class RawUIPayload(BaseModel):
    spec_format: str = "openapi_json"  # openapi_json, openapi_yaml, swagger_json, curl
    spec_content: Union[str, Dict[str, Any]]
    service_name: Optional[str] = None
    base_url: Optional[str] = None
    auth: Optional[AuthScheme] = None


class FeedbackReport(BaseModel):
    status: str = "FAIL"
    stage: str = "functional_test"  # functional_test, security_fuzzing
    service_name: Optional[str] = None
    sandbox_id: Optional[str] = None
    failing_tool: Optional[str] = None
    error_category: str = "runtime_crash"  # http_status_error, runtime_crash, syntax_error, secret_leakage, prompt_injection, type_validation_error
    tested_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: str
    traceback: Optional[str] = None
    suggested_fix: Optional[str] = None

