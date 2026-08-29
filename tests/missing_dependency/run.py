from tests.missing_dependency.scenario import CODER_OUTPUT, EXPECTED_STATUS
from tests.scenario_runner import run_scenario


if __name__ == "__main__":
    run_scenario(name="missing_dependency", coder_output=CODER_OUTPUT, expected_status=EXPECTED_STATUS)
