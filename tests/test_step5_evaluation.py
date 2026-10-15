
"""Unit tests for the Step 5 evaluation expectations."""

from eval_runner import evaluate_response
from eval_scenarios import Scenario


def make_case(expectation, arguments=None, expected_status=None):
    return Scenario(
        id="TEST",
        persona="citizen_a",
        prompt="Test scenario",
        tool="test_tool",
        arguments=arguments or {},
        expectation=expectation,
        expected_status=expected_status,
    )


def test_application_list_success():
    case = make_case("application_list")
    passed, _ = evaluate_response(case, [
        {"application_no": "TEST-1", "status": "PENDING"}
    ])
    assert passed


def test_application_list_invalid_structure():
    case = make_case("application_list")
    passed, _ = evaluate_response(case, [
        {"application_no": "TEST-1"}
    ])
    assert not passed


def test_ownership_isolation_success():
    case = make_case("not_found")
    passed, _ = evaluate_response(case, {"found": False})
    assert passed


def test_ownership_isolation_failure():
    case = make_case("not_found")
    passed, _ = evaluate_response(case, {
        "found": True,
        "application_no": "TEST-1",
        "status": "PENDING",
    })
    assert not passed


def test_pending_queue_success():
    case = make_case("pending_queue", {"limit": 5})
    passed, _ = evaluate_response(case, [
        {"application_no": "TEST-1", "status": "PENDING"}
    ])
    assert passed


def test_pending_queue_wrong_status():
    case = make_case("pending_queue", {"limit": 5})
    passed, _ = evaluate_response(case, [
        {"application_no": "TEST-1", "status": "APPROVED"}
    ])
    assert not passed


def test_status_counts_success():
    case = make_case("status_counts")
    passed, _ = evaluate_response(case, {
        "PENDING": 10,
        "APPROVED": 20,
    })
    assert passed


def test_status_counts_negative_value():
    case = make_case("status_counts")
    passed, _ = evaluate_response(case, {"PENDING": -1})
    assert not passed


def test_known_application_success():
    case = make_case(
        "found",
        {"application_no": "TEST-1"},
        "PENDING",
    )
    passed, _ = evaluate_response(case, {
        "found": True,
        "application_no": "TEST-1",
        "status": "PENDING",
    })
    assert passed


def test_known_application_wrong_status():
    case = make_case(
        "found",
        {"application_no": "TEST-1"},
        "APPROVED",
    )
    passed, _ = evaluate_response(case, {
        "found": True,
        "application_no": "TEST-1",
        "status": "PENDING",
    })
    assert not passed
