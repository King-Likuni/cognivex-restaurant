from datetime import date

import pytest

from app.orders.numbering import (
    format_display_number,
    generate_payment_reference,
    next_daily_sequence,
)


@pytest.mark.parametrize(
    ("sequence", "display_number"),
    [
        (1, "#001"),
        (37, "#037"),
        (1234, "#1234"),
    ],
)
def test_format_display_number(sequence, display_number):
    assert format_display_number(sequence) == display_number


def test_format_display_number_rejects_zero():
    with pytest.raises(ValueError):
        format_display_number(0)


@pytest.mark.parametrize(
    ("current_max", "next_sequence"),
    [
        (None, 1),
        (0, 1),
        (37, 38),
    ],
)
def test_next_daily_sequence(current_max, next_sequence):
    assert next_daily_sequence(current_max) == next_sequence


def test_generate_payment_reference_uses_codes_date_and_sequence():
    assert generate_payment_reference("cs01", "mm", date(2026, 9, 3), 37) == "CS01-MM-260903-037"
