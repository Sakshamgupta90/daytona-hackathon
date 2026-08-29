from tests.passing_math.scenario import CODER_OUTPUT, EXPECTED_STATUS
from tests.scenario_runner import run_scenario


if __name__ == "__main__":
    run_scenario(name="passing_math", coder_output=CODER_OUTPUT, expected_status=EXPECTED_STATUS)
