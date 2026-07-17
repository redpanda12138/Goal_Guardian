"""Typed gateway error categories reserved for the new workflow boundary."""


class MASGatewayError(Exception):
    category = "gateway"

    def __init__(self, service_name: str, endpoint: str, message: str):
        super().__init__(message)
        self.service_name = service_name
        self.endpoint = endpoint


class UnknownMASServiceError(MASGatewayError):
    category = "unknown_service"


class MASGatewayTimeoutError(MASGatewayError):
    category = "timeout"


class MASGatewayHTTPError(MASGatewayError):
    category = "http"


class MASGatewayTransportError(MASGatewayError):
    category = "transport"


class MASGatewayUnexpectedError(MASGatewayError):
    category = "unexpected"
