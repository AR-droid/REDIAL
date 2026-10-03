import pytest

from scripts.place_voice_call import APPROVED_NUMBER, build_call

ENV = {
    "APPROVED_CALL_NUMBER": APPROVED_NUMBER,
    "TWILIO_FROM_NUMBER": "+12792363632",
    "PUBLIC_BASE_URL": "https://example.test/",
}


def test_builds_call_to_approved_number_for_scenario():
    call = build_call(ENV, 3)
    assert call["To"] == APPROVED_NUMBER
    assert call["From"] == "+12792363632"
    assert call["Url"] == "https://example.test/voice/twiml?customer_id=cust_003"


def test_refuses_any_other_destination_in_env():
    env = {**ENV, "APPROVED_CALL_NUMBER": "+15555550100"}
    with pytest.raises(SystemExit):
        build_call(env, 1)


def test_refuses_when_from_number_equals_approved_number():
    env = {**ENV, "TWILIO_FROM_NUMBER": APPROVED_NUMBER}
    with pytest.raises(SystemExit):
        build_call(env, 1)


@pytest.mark.parametrize("scenario", [0, 11])
def test_refuses_scenarios_outside_1_to_10(scenario):
    with pytest.raises(SystemExit):
        build_call(ENV, scenario)
