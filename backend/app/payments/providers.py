"""Payment provider adapter contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.orders.enums import PaymentStatus

REMOTE_PAYMENT_PROVIDERS = {"ORANGE_MONEY", "PAY2CELL"}


@dataclass(frozen=True)
class PaymentRequest:
    order_id: str
    reference: str
    amount: Decimal
    currency: str
    customer_phone_number: str | None = None


@dataclass(frozen=True)
class PaymentResult:
    provider: str
    reference: str
    status: str
    amount: Decimal
    currency: str
    provider_transaction_id: str | None = None
    raw_payload: dict | None = None


class PaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        """Start a provider payment flow."""

    @abstractmethod
    def verify_payment(self, reference: str) -> PaymentResult:
        """Fetch and normalize provider payment status."""

    @abstractmethod
    def process_callback(self, payload: dict) -> PaymentResult:
        """Normalize a provider webhook callback."""

    @abstractmethod
    def get_payment_status(self, reference: str) -> PaymentResult:
        """Return the current provider payment status."""

    @abstractmethod
    def refund_payment(self, reference: str, amount: Decimal | None = None) -> PaymentResult:
        """Request a full or partial refund."""


class CashProvider(PaymentProvider):
    provider_name = "CASH"

    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            provider=self.provider_name,
            reference=request.reference,
            status="PAID",
            amount=request.amount,
            currency=request.currency,
        )

    def verify_payment(self, reference: str) -> PaymentResult:
        raise NotImplementedError("Cash payments are verified by cashier confirmation")

    def process_callback(self, payload: dict) -> PaymentResult:
        raise NotImplementedError("Cash payments do not use callbacks")

    def get_payment_status(self, reference: str) -> PaymentResult:
        raise NotImplementedError("Cash payment status is stored locally")

    def refund_payment(self, reference: str, amount: Decimal | None = None) -> PaymentResult:
        raise NotImplementedError("Cash refunds require a manual audited workflow")


class SandboxRemotePaymentProvider(PaymentProvider):
    def __init__(self, provider_name: str) -> None:
        if provider_name not in REMOTE_PAYMENT_PROVIDERS:
            raise ValueError(f"Unsupported payment provider '{provider_name}'")
        self.provider_name = provider_name

    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            provider=self.provider_name,
            reference=request.reference,
            status=PaymentStatus.PENDING.value,
            amount=request.amount,
            currency=request.currency,
            raw_payload={
                "mode": "sandbox",
                "customer_phone_number": request.customer_phone_number,
            },
        )

    def verify_payment(self, reference: str) -> PaymentResult:
        raise NotImplementedError("Sandbox remote payments are verified by signed callbacks")

    def process_callback(self, payload: dict) -> PaymentResult:
        return PaymentResult(
            provider=self.provider_name,
            reference=payload["reference"],
            status=payload["status"],
            amount=Decimal(str(payload["amount"])),
            currency=payload["currency"],
            provider_transaction_id=payload.get("provider_transaction_id"),
            raw_payload=payload,
        )

    def get_payment_status(self, reference: str) -> PaymentResult:
        raise NotImplementedError("Remote payment status polling is provider-specific")

    def refund_payment(self, reference: str, amount: Decimal | None = None) -> PaymentResult:
        raise NotImplementedError("Remote refunds require provider-specific implementation")


def get_payment_provider(provider_name: str) -> PaymentProvider:
    normalized_provider = provider_name.upper()
    if normalized_provider == "CASH":
        return CashProvider()
    if normalized_provider in REMOTE_PAYMENT_PROVIDERS:
        return SandboxRemotePaymentProvider(normalized_provider)
    raise ValueError(f"Unsupported payment provider '{provider_name}'")
