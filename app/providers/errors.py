class ProviderError(Exception):
    """Base class for all provider-call failures."""

    def __init__(self, message: str, provider: str = ""):
        super().__init__(message)
        self.message = message
        self.provider = provider


class RetryableProviderError(ProviderError):
    """Transient failure; safe to retry and/or fall back to another provider."""


class ProviderTimeoutError(RetryableProviderError):
    pass


class ProviderRateLimitError(RetryableProviderError):
    pass


class ProviderServerError(RetryableProviderError):
    pass


class NonRetryableProviderError(ProviderError):
    """Permanent failure; retrying or falling back will not help."""


class ProviderAuthError(NonRetryableProviderError):
    pass
