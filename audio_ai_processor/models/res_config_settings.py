from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    openai_api_key = fields.Char(
        string='OpenAI API Key',
        help='API key for Whisper transcription',
        config_parameter='audio_ai_processor.openai_api_key',
    )

    whisper_language = fields.Selection(
        selection=[
            ('uk', 'Ukrainian'),
            ('en', 'English'),
            ('ru', 'Russian'),
            ('de', 'German'),
            ('fr', 'French'),
            ('es', 'Spanish'),
        ],
        string='Whisper Language',
        default='uk',
        help='Language hint for audio transcription',
        config_parameter='audio_ai_processor.whisper_language',
    )

    processing_mode = fields.Selection(
        selection=[
            ('immediate', 'Immediate (one after another)'),
            ('scheduled', 'Scheduled (specific hours only)'),
        ],
        string='Processing Mode',
        default='immediate',
        help='Immediate: process next task right after previous completes. '
             'Scheduled: process only during specified hours.',
        config_parameter='audio_ai_processor.processing_mode',
    )

    scheduled_hour_from = fields.Integer(
        string='Process From Hour',
        default=22,
        help='Start processing from this hour (0-23)',
        config_parameter='audio_ai_processor.scheduled_hour_from',
    )

    scheduled_hour_to = fields.Integer(
        string='Process Until Hour',
        default=6,
        help='Process until this hour (0-23)',
        config_parameter='audio_ai_processor.scheduled_hour_to',
    )
