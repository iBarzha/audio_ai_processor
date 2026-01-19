"""Wizard for uploading multiple audio files at once."""

from odoo import _, fields, models
from odoo.exceptions import UserError


class AudioUploadWizard(models.TransientModel):
    """Wizard for batch upload of audio files."""

    _name = 'audio.upload.wizard'
    _description = 'Upload Multiple Audio Files'

    file_ids = fields.One2many(
        comodel_name='audio.upload.wizard.line',
        inverse_name='wizard_id',
    )

    def action_upload(self):
        """Create audio tasks for each uploaded file and add them to queue.

        Returns:
            dict: Window action to display created tasks
        """
        self.ensure_one()

        if not self.file_ids:
            raise UserError(_('Please add at least one audio file.'))

        AudioTask = self.env['audio.task']
        created_tasks = AudioTask

        for line in self.file_ids:
            task = AudioTask.create({
                'name': line.filename or 'Audio Task',
                'audio_file': line.audio_file,
                'audio_filename': line.filename,
            })
            task.action_add_to_queue()
            created_tasks |= task

        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Tasks'),
            'res_model': 'audio.task',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_tasks.ids)],
            'target': 'current',
        }


class AudioUploadWizardLine(models.TransientModel):
    """Line item for audio upload wizard."""

    _name = 'audio.upload.wizard.line'
    _description = 'Audio Upload Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='audio.upload.wizard',
        required=True,
        ondelete='cascade',
    )

    audio_file = fields.Binary(required=True)

    filename = fields.Char()
