from veyralock.password import check_password_strength


def test_dangerously_short_password_is_blocked() -> None:
    result = check_password_strength("short")

    assert result.is_dangerously_short is True
    assert result.is_acceptable is False
    assert any("at least 8 characters" in warning for warning in result.warnings)


def test_common_weak_password_is_flagged() -> None:
    result = check_password_strength("password123")

    assert result.is_dangerously_short is False
    assert any("common weak password" in warning for warning in result.warnings)


def test_recommended_but_not_strong_length_gets_guidance() -> None:
    result = check_password_strength("LongerPass12")

    assert result.meets_recommended_length is True
    assert result.meets_strong_length is False
    assert any("16+ characters is stronger" in warning for warning in result.warnings)


def test_strong_password_has_no_warnings() -> None:
    result = check_password_strength("CorrectHorseBatteryStaple!2026")

    assert result.is_acceptable is True
    assert result.meets_recommended_length is True
    assert result.meets_strong_length is True
    assert result.warnings == ()
