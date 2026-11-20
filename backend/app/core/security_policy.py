"""Small deployment-secret policy shared by runtime and release validation.

This detects common configuration mistakes, not cryptographic entropy. Generate
production signing keys with a CSPRNG (for example, secrets.token_urlsafe(48)); never
reuse the public fixtures in tests or CI as deployment credentials.
"""

PLACEHOLDER_PREFIXES = (
    "change-me",
    "changeme",
    "change_this",
    "change-this",
    "replace-me",
    "replace_me",
    "replace-this",
    "replace_this",
    "your-secret",
    "your_secret",
    "example",
    "test-secret",
    "test_secret",
    "ci-only",
    "development-secret",
    "default-secret",
    "secret-key-here",
)


def secret_is_strong(value: str) -> bool:
    """Reject short, low-diversity, placeholder and completely periodic keys."""
    if not isinstance(value, str) or len(value) < 32 or len(set(value)) < 16:
        return False
    # Padding must not make an otherwise short/weak key appear to pass policy.
    candidate = value.strip()
    if len(candidate) < 32 or len(set(candidate)) < 16:
        return False
    normalized = candidate.casefold()
    if normalized.startswith(PLACEHOLDER_PREFIXES):
        return False
    # A complete repetition appears inside its doubled value after removing the
    # two trivial endpoint occurrences. Case-only variations remain predictable.
    return normalized not in (normalized + normalized)[1:-1]
