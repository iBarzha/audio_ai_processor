import contextlib

from odoo import SUPERUSER_ID, api, registry


@contextlib.contextmanager
def new_environment(dbname, uid=None, context=None):
    if context is None:
        context = {}

    with registry(dbname).cursor() as cursor:
        env = api.Environment(cursor, uid or SUPERUSER_ID, context)
        yield env
        cursor.commit()
