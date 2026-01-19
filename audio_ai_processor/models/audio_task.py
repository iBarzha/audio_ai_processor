"""Audio task model for managing audio transcription tasks."""

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
    """Model for audio transcription tasks using OpenAI Whisper."""

    _name = 'audio.task'
    _description = 'Audio Transcription Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
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
        default='draft',
        required=True,
        tracking=True,
    )

    audio_file = fields.Binary(
        help='Supported formats: MP3, WAV, M4A, OGG, FLAC',
    )

    audio_filename = fields.Char()

    transcription = fields.Text(
        readonly=True,
    )

    transcription_time = fields.Float(
        readonly=True,
    )

    result_file = fields.Binary(
        readonly=True,
        attachment=True,
    )

    result_filename = fields.Char(
        readonly=True,
    )

    error_message = fields.Text(
        readonly=True,
    )

    queue_position = fields.Integer(
        compute='_compute_queue_position',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    user_id = fields.Many2one(
        comodel_name='res.users',
        default=lambda self: self.env.user,
        required=True,
    )

    category_id = fields.Many2one(
        comodel_name='audio.category',
    )

    tag_ids = fields.Many2many(
        comodel_name='audio.tag',
        relation='audio_task_tag_rel',
        column1='task_id',
        column2='tag_id',
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
    )

    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'High'),
        ],
        default='0',
    )

    color = fields.Integer()

    @api.depends('state', 'create_date')
    def _compute_queue_position(self):
        """Compute position in the processing queue."""
        pending_tasks = self.search(
            [('state', '=', 'pending')],
            order='create_date asc'
        )
        position_map = {
            task.id: idx + 1 for idx, task in enumerate(pending_tasks)
        }
        for record in self:
            record.queue_position = position_map.get(record.id, 0)

    def action_add_to_queue(self):
        """Add task to processing queue."""
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
        """Reset task to draft state and clear all results."""
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
        """Remove task from processing queue."""
        self.ensure_one()
        if self.state == 'pending':
            self.write({'state': 'draft'})
            self.message_post(body=_('Removed from queue.'))
        return True

    @api.model
    def _cron_process_queue(self):
        """Cron job to process next task in queue."""
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
        """Start transcription process in background thread."""
        self.ensure_one()

        api_key = self._get_config('openai_api_key')
        if not api_key:
            self._set_error('OpenAI API key not configured.')
            return

        audio_content = base64.b64decode(self.audio_file)
        language = self._get_config('whisper_language', 'uk')

        self.write({'state': 'transcribing'})
        self.message_post(body=_('Transcription started...'))

        thread_args = (
            self.id, audio_content, self.audio_filename, api_key, language
        )
        self._start_thread(target=self._transcribe_thread, args=thread_args)

    def _transcribe_thread(
            self, task_id, audio_content, filename, api_key, language):
        """Execute transcription in separate thread.

        Args:
            task_id: ID of the task being processed
            audio_content: Binary audio data
            filename: Original filename
            api_key: OpenAI API key
            language: Language code for transcription
        """
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
            self._save_transcription(
                task_id, transcription, elapsed, dbname, uid, context)

        except Exception as e:
            _logger.exception("Transcription error: %s", e)
            self._save_error(task_id, str(e), dbname, uid, context)

    def _save_transcription(
            self, task_id, transcription, elapsed, dbname, uid, context):
        """Save transcription result with retry logic.

        Args:
            task_id: ID of the task
            transcription: Transcription text
            elapsed: Processing time in seconds
            dbname: Database name
            uid: User ID
            context: Odoo context
        """
        # Повторні спроби при помилках серіалізації БД
        for attempt in range(MAX_RETRIES):
            try:
                with new_environment(dbname, uid, context) as env:
                    task = env['audio.task'].sudo().browse(task_id)
                    if not task.exists():
                        return

                    filename = f"transcription_{task_id}.txt"
                    encoded = transcription.encode('utf-8')
                    file_binary = base64.b64encode(encoded)

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

                    msg = _(
                        'Transcription completed in %(time).2f sec.\n\n'
                        '%(text)s',
                        time=elapsed,
                        text=preview,
                    )
                    task.message_post(body=msg)

                    env.cr.commit()
                    _logger.info("Transcription saved for task %d", task_id)

                    task._trigger_queue_processing()
                    return

            except Exception as e:
                # Затримка перед повторною спробою при помилці серіалізації
                err_str = str(e)
                can_retry = attempt < MAX_RETRIES - 1
                if 'could not serialize' in err_str and can_retry:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise

    def _save_error(self, task_id, error_message, dbname, uid, context):
        """Save error state for failed transcription.

        Args:
            task_id: ID of the task
            error_message: Error description
            dbname: Database name
            uid: User ID
            context: Odoo context
        """
        try:
            with new_environment(dbname, uid, context) as env:
                task = env['audio.task'].sudo().browse(task_id)
                if not task.exists():
                    return

                task.write({
                    'state': 'error',
                    'error_message': error_message,
                })

                task.message_post(body=_('Error: %(msg)s', msg=error_message))
                env.cr.commit()

                task._trigger_queue_processing()

        except Exception as e:
            _logger.error("Failed to save error for task %d: %s", task_id, e)

    def _set_error(self, message):
        """Set task to error state with message.

        Args:
            message: Error description
        """
        self.write({
            'state': 'error',
            'error_message': message,
        })
        self.message_post(body=_('Error: %(msg)s', msg=message))

    def _trigger_queue_processing(self):
        """Trigger cron job to process next task in queue."""
        mode = self._get_config('processing_mode', 'immediate')
        if mode == 'immediate':
            self.env.ref(
                'audio_ai_processor.ir_cron_process_audio_queue'
            )._trigger()

    def _is_processing_allowed(self):
        """Check if processing is allowed based on schedule settings.

        Returns:
            bool: True if processing is allowed
        """
        mode = self._get_config('processing_mode', 'immediate')

        if mode == 'immediate':
            return True

        # Перевірка чи поточний час входить у дозволений діапазон
        hour_from = int(self._get_config('scheduled_hour_from', '22'))
        hour_to = int(self._get_config('scheduled_hour_to', '6'))
        current_hour = datetime.now().hour

        # Обробка нічного діапазону (наприклад, 22:00 - 06:00)
        if hour_from <= hour_to:
            return hour_from <= current_hour < hour_to
        return current_hour >= hour_from or current_hour < hour_to

    def _has_active_transcription(self):
        """Check if any transcription is currently in progress.

        Returns:
            bool: True if transcription is active
        """
        return self.search_count([('state', '=', 'transcribing')]) > 0

    def _validate_audio_file(self):
        """Validate uploaded audio file format."""
        if not self.audio_file:
            raise UserError(_('Please upload an audio file first.'))

        if not self.audio_filename:
            raise UserError(_('Audio filename is missing.'))

        valid_extensions = ('.mp3', '.wav', '.m4a', '.ogg', '.flac')
        if not self.audio_filename.lower().endswith(valid_extensions):
            supported = ', '.join(valid_extensions)
            raise UserError(_(
                'Invalid audio format. Supported: %(formats)s',
                formats=supported,
            ))

    def _get_config(self, param_name, default=None):
        """Get configuration parameter value.

        Args:
            param_name: Parameter name without prefix
            default: Default value if not set

        Returns:
            Parameter value or default
        """
        return self.env['ir.config_parameter'].sudo().get_param(
            f'audio_ai_processor.{param_name}',
            default
        )

    def _start_thread(self, target, args):
        """Start daemon thread for background processing.

        Args:
            target: Thread target function
            args: Arguments for target function
        """
        thread = threading.Thread(
            target=target,
            args=args,
            daemon=True,
        )
        thread.start()
