"""Extension of res.partner model for audio tasks."""

from odoo import fields, models


class ResPartner(models.Model):
    """Extend partner to add audio task relationship."""

    _inherit = 'res.partner'

    audio_task_ids = fields.One2many(
        comodel_name='audio.task',
        inverse_name='partner_id',
    )

    audio_task_count = fields.Integer(
        compute='_compute_audio_task_count',
    )

    def _compute_audio_task_count(self):
        """Compute the number of audio tasks for each partner."""
        for record in self:
            record.audio_task_count = len(record.audio_task_ids)

    def action_view_audio_tasks(self):
        """Open audio tasks related to this partner."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Audio Tasks',
            'res_model': 'audio.task',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
