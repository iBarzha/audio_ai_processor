"""Audio tag model for labeling audio tasks."""

from odoo import fields, models


class AudioTag(models.Model):
    """Tag for labeling audio transcription tasks."""

    _name = 'audio.tag'
    _description = 'Audio Tag'
    _order = 'name'

    name = fields.Char(
        required=True,
        translate=True,
    )

    color = fields.Integer()
