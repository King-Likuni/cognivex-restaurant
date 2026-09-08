"""Order numbering and payment reference helpers."""

from datetime import date


def format_display_number(daily_sequence: int) -> str:
    if daily_sequence < 1:
        raise ValueError("Daily sequence must be greater than zero")
    return f"#{daily_sequence:03d}"


def next_daily_sequence(current_max: int | None) -> int:
    return int(current_max or 0) + 1


def generate_payment_reference(
    restaurant_code: str,
    branch_code: str,
    business_date: date,
    daily_sequence: int,
) -> str:
    return "-".join(
        [
            restaurant_code.upper(),
            branch_code.upper(),
            business_date.strftime("%y%m%d"),
            f"{daily_sequence:03d}",
        ]
    )
