from odoo import _, fields, models
from odoo.exceptions import UserError


class AudioUploadWizard(models.TransientModel):
    _name = 'audio.upload.wizard'
    _description = 'Upload Multiple Audio Files'

    file_ids = fields.One2many(
        comodel_name='audio.upload.wizard.line',
        inverse_name='wizard_id',
        string='Audio Files',
    )

    def action_upload(self):
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
    _name = 'audio.upload.wizard.line'
    _description = 'Audio Upload Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='audio.upload.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    audio_file = fields.Binary(
        string='Audio File',
        required=True,
    )

    filename = fields.Char(
        string='Filename',
    )
