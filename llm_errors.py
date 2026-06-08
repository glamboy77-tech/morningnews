"""Shared LLM error classification helpers.

These helpers intentionally avoid model-name decisions.  They only classify
provider/API failures so the daily pipeline can stop before it writes broken
cache, HTML, or script outputs.
"""


class FatalLLMError(RuntimeError):
    """An LLM/API failure that should stop the current job immediately."""


def _message(err: Exception | str) -> str:
    return str(err or "")


def is_fatal_llm_error(err: Exception | str) -> bool:
    """Return True for errors that should not be retried in this job.

    In this project, Gemini 429/RESOURCE_EXHAUSTED has repeatedly produced
    many failed requests and then broken output pages.  Treating these as
    fatal is safer than retrying or falling through to fallback publication.
    """

    msg = _message(err)
    lower = msg.lower()

    fatal_tokens = [
        "prepayment credits are depleted",
        "resource_exhausted",
        "too many requests",
        "429",
        "quota",
        "rate limit",
        "billing",
        "invalid_argument",
        "bad request",
        "400",
        "api key not valid",
        "permission_denied",
        "permission denied",
    ]
    return any(token in lower for token in fatal_tokens)


def is_retryable_llm_error(err: Exception | str) -> bool:
    """Return True for transient overload/availability errors only."""

    msg = _message(err)
    lower = msg.lower()

    if is_fatal_llm_error(msg):
        return False

    retryable_tokens = [
        "503",
        "unavailable",
        "overloaded",
        "deadline_exceeded",
        "deadline exceeded",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "read timed out",
        "timeout",
        "timed out",
    ]
    return any(token in lower for token in retryable_tokens)