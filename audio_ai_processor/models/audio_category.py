"""Audio category model for organizing audio tasks."""

from odoo import fields, models


class AudioCategory(models.Model):
    """Category for grouping audio transcription tasks."""

    _name = 'audio.category'
    _description = 'Audio Category'
    _order = 'sequence, name'

    name = fields.Char(
        required=True,
        translate=True,
    )

    sequence = fields.Integer(default=10)

    color = fields.Integer()

    active = fields.Boolean(default=True)

    task_ids = fields.One2many(
        comodel_name='audio.task',
        inverse_name='category_id',
    )

    task_count = fields.Integer(compute='_compute_task_count')

    def _compute_task_count(self):
        """Compute the number of tasks in each category."""
        for record in self:
            record.task_count = len(record.task_ids)
