"""Utilities for environment management in background threads."""

import contextlib

from odoo import SUPERUSER_ID, api, registry


@contextlib.contextmanager
def new_environment(dbname, uid=None, context=None):
    """Create new Odoo environment for use in background threads.

    Args:
        dbname: Database name
        uid: User ID (defaults to SUPERUSER_ID)
        context: Odoo context dict

    Yields:
        api.Environment: New Odoo environment
    """
    if context is None:
        context = {}

    with registry(dbname).cursor() as cursor:
        env = api.Environment(cursor, uid or SUPERUSER_ID, context)
        yield env
        cursor.commit()
