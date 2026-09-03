"""Model registry for the common app.

ActivityLog is defined in audit.py alongside the helpers that write it; Django
only discovers models declared in (or imported into) models.py.
"""

from .audit import ActivityLog  # noqa: F401
