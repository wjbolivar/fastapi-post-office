"""Stable exceptions exposed by the public API."""


class PostOfficeError(Exception):
    """Base class for library domain errors (DB/driver errors retain their types)."""


class ValidationError(PostOfficeError, ValueError):
    pass


class IdempotencyError(ValidationError):
    pass


class MessageNotFoundError(PostOfficeError, ValueError):
    pass


class TemplateNotFoundError(PostOfficeError, ValueError):
    pass


class SuppressedRecipientError(ValidationError):
    pass


class TransactionModeError(PostOfficeError, RuntimeError):
    pass


class InvalidTransitionError(PostOfficeError, ValueError):
    pass
