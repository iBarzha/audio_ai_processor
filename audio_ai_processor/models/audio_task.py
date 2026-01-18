import base64
import logging
import threading
import time
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.env_utils import new_environment
from ..services.whisper_service import WhisperService

_logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 0.5


class AudioTask(models.Model):
    _name = 'audio.task'
    _description = 'Audio Transcription Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        required=True,
        default='New Audio Task',
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pending', 'In Queue'),
            ('transcribing', 'Transcribing'),
            ('done', 'Done'),
            ('error', 'Error'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    audio_file = fields.Binary(
        string='Audio File',
        help='Supported formats: MP3, WAV, M4A, OGG, FLAC',
    )

    audio_filename = fields.Char(
        string='Filename',
    )

    transcription = fields.Text(
        string='Transcription',
        readonly=True,
    )

    transcription_time = fields.Float(
        string='Transcription Time (sec)',
        readonly=True,
    )

    result_file = fields.Binary(
        string='Result File',
        readonly=True,
        attachment=True,
    )

    result_filename = fields.Char(
        string='Result Filename',
        readonly=True,
    )

    error_message = fields.Text(
        string='Error',
        readonly=True,
    )

    queue_position = fields.Integer(
        string='Queue Position',
        compute='_compute_queue_position',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )

    @api.depends('state', 'create_date')
    def _compute_queue_position(self):
        pending_tasks = self.search(
            [('state', '=', 'pending')],
            order='create_date asc'
        )
        position_map = {task.id: idx + 1 for idx, task in enumerate(pending_tasks)}
        for record in self:
            record.queue_position = position_map.get(record.id, 0)

    def action_add_to_queue(self):
        self.ensure_one()
        self._validate_audio_file()

        api_key = self._get_config('openai_api_key')
        if not api_key:
            raise UserError(_('Please configure OpenAI API key in Settings.'))

        self.write({
            'state': 'pending',
            'error_message': False,
        })

        self.message_post(body=_('Added to processing queue.'))

        mode = self._get_config('processing_mode', 'immediate')
        if mode == 'immediate':
            self._trigger_queue_processing()

        return True

    def action_reset(self):
        self.ensure_one()
        self.write({
            'state': 'draft',
            'transcription': False,
            'transcription_time': 0,
            'result_file': False,
            'result_filename': False,
            'error_message': False,
        })
        return True

    def action_cancel_queue(self):
        self.ensure_one()
        if self.state == 'pending':
            self.write({'state': 'draft'})
            self.message_post(body=_('Removed from queue.'))
        return True

    @api.model
    def _cron_process_queue(self):
        if not self._is_processing_allowed():
            _logger.info("Processing not allowed at this time, skipping.")
            return

        if self._has_active_transcription():
            _logger.info("Transcription already in progress, skipping.")
            return

        next_task = self.search(
            [('state', '=', 'pending')],
            order='create_date asc',
            limit=1
        )

        if next_task:
            _logger.info("Processing task %d from queue", next_task.id)
            next_task._process_transcription()

    def _process_transcription(self):
        self.ensure_one()

        api_key = self._get_config('openai_api_key')
        if not api_key:
            self._set_error('OpenAI API key not configured.')
            return

        audio_content = base64.b64decode(self.audio_file)
        language = self._get_config('whisper_language', 'uk')

        self.write({'state': 'transcribing'})
        self.message_post(body=_('Transcription started...'))

        self._start_thread(
            target=self._transcribe_thread,
            args=(self.id, audio_content, self.audio_filename, api_key, language),
        )

    def _transcribe_thread(self, task_id, audio_content, filename, api_key, language):
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context)

        start_time = time.time()

        try:
            whisper = WhisperService(api_key=api_key)
            transcription = whisper.transcribe(
                audio_binary=audio_content,
                filename=filename,
                language=language,
            )

            if not transcription or not transcription.strip():
                raise ValueError("Empty transcription received")

            elapsed = time.time() - start_time
            self._save_transcription(task_id, transcription, elapsed, dbname, uid, context)

        except Exception as e:
            _logger.exception("Transcription error: %s", e)
            self._save_error(task_id, str(e), dbname, uid, context)

    def _save_transcription(self, task_id, transcription, elapsed, dbname, uid, context):
        for attempt in range(MAX_RETRIES):
            try:
                with new_environment(dbname, uid, context) as env:
                    task = env['audio.task'].sudo().browse(task_id)
                    if not task.exists():
                        return

                    filename = f"transcription_{task_id}.txt"
                    file_binary = base64.b64encode(transcription.encode('utf-8'))

                    task.write({
                        'state': 'done',
                        'transcription': transcription,
                        'transcription_time': elapsed,
                        'result_file': file_binary,
                        'result_filename': filename,
                    })

                    env['ir.attachment'].create({
                        'name': filename,
                        'datas': file_binary,
                        'res_model': 'audio.task',
                        'res_id': task_id,
                        'type': 'binary',
                    })

                    preview = transcription[:500]
                    if len(transcription) > 500:
                        preview += '...'

                    task.message_post(
                        body=_('Transcription completed in %.2f sec.\n\n%s', elapsed, preview)
                    )

                    env.cr.commit()
                    _logger.info("Transcription saved for task %d", task_id)

                    task._trigger_queue_processing()
                    return

            except Exception as e:
                if 'could not serialize' in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise

    def _save_error(self, task_id, error_message, dbname, uid, context):
        try:
            with new_environment(dbname, uid, context) as env:
                task = env['audio.task'].sudo().browse(task_id)
                if not task.exists():
                    return

                task.write({
                    'state': 'error',
                    'error_message': error_message,
                })

                task.message_post(body=_('Error: %s', error_message))
                env.cr.commit()

                task._trigger_queue_processing()

        except Exception as e:
            _logger.error("Failed to save error for task %d: %s", task_id, e)

    def _set_error(self, message):
        self.write({
            'state': 'error',
            'error_message': message,
        })
        self.message_post(body=_('Error: %s', message))

    def _trigger_queue_processing(self):
        mode = self._get_config('processing_mode', 'immediate')
        if mode == 'immediate':
            self.env.ref(
                'audio_ai_processor.ir_cron_process_audio_queue'
            )._trigger()

    def _is_processing_allowed(self):
        mode = self._get_config('processing_mode', 'immediate')

        if mode == 'immediate':
            return True

        hour_from = int(self._get_config('scheduled_hour_from', '22'))
        hour_to = int(self._get_config('scheduled_hour_to', '6'))
        current_hour = datetime.now().hour

        if hour_from <= hour_to:
            return hour_from <= current_hour < hour_to
        else:
            return current_hour >= hour_from or current_hour < hour_to

    def _has_active_transcription(self):
        return self.search_count([('state', '=', 'transcribing')]) > 0

    def _validate_audio_file(self):
        if not self.audio_file:
            raise UserError(_('Please upload an audio file first.'))

        if not self.audio_filename:
            raise UserError(_('Audio filename is missing.'))

        valid_extensions = ('.mp3', '.wav', '.m4a', '.ogg', '.flac')
        if not self.audio_filename.lower().endswith(valid_extensions):
            raise UserError(_(
                'Invalid audio format. Supported: %s',
                ', '.join(valid_extensions)
            ))

    def _get_config(self, param_name, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'audio_ai_processor.{param_name}',
            default
        )

    def _start_thread(self, target, args):
        thread = threading.Thread(
            target=target,
            args=args,
            daemon=True,
        )
        thread.start()
