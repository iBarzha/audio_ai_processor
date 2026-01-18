import logging

from openai import OpenAI

_logger = logging.getLogger(__name__)


class WhisperService:

    MIME_TYPES = {
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'webm': 'audio/webm',
        'm4a': 'audio/mp4',
        'ogg': 'audio/ogg',
        'flac': 'audio/flac',
    }

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def transcribe(self, audio_binary, filename, language=None, model='whisper-1'):
        if not audio_binary:
            raise ValueError('Audio file is empty')

        mime_type = self._get_mime_type(filename)

        _logger.info('Starting transcription: file=%s, language=%s', filename, language)

        transcript = self.client.audio.transcriptions.create(
            model=model,
            file=(filename, audio_binary, mime_type),
            language=language,
            response_format='text',
        )

        _logger.info('Transcription completed: %d characters', len(transcript))
        return transcript

    def _get_mime_type(self, filename):
        extension = filename.lower().rsplit('.', 1)[-1]
        return self.MIME_TYPES.get(extension, 'audio/mpeg')
