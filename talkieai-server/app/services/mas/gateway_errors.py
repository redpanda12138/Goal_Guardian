"""Typed gateway error categories reserved for the new workflow boundary."""


class MASGatewayError(Exception):
    category = "gateway"

    def __init__(self, service_name: str, endpoint: str, message: str, *, cause=None):
        super().__init__(message)
        self.service_name = service_name
        self.endpoint = endpoint
        self.message = message
        self.cause_type = type(cause).__name__ if cause is not None else None


class UnknownMASServiceError(MASGatewayError, ValueError):
    category = "unknown_service"


class MASGatewayTimeoutError(MASGatewayError):
    category = "timeout"

    def __init__(self, *args, timeout_seconds=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout_seconds = timeout_seconds


class MASGatewayHTTPError(MASGatewayError):
    category = "http"

    def __init__(self, *args, status_code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_code = status_code


class MASGatewayTransportError(MASGatewayError):
    category = "transport"


class MASGatewayUnexpectedError(MASGatewayError):
    category = "unexpected"
