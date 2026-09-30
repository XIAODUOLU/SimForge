"""Display expected errors in the UI and log full tracebacks for unexpected errors."""


class SimForgeError(Exception):
    """An operation error suitable for display to the user."""


class FeatureNotImplemented(SimForgeError):
    """A service entry point is not implemented and must not report success."""


class CompatibilityError(SimForgeError):
    """The current Blender version or an optional dependency lacks a required capability."""
