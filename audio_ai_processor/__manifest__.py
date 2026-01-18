{
    'name': 'Audio AI Processor',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Transcribe audio files using OpenAI Whisper',
    'description': """
Audio AI Processor
==================
This module provides audio transcription:
* Upload audio files (MP3, WAV, M4A, OGG, FLAC)
* Transcribe audio using OpenAI Whisper API
* Queue-based sequential processing
* Download transcription results
    """,
    'author': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'external_dependencies': {
        'python': ['openai'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'wizard/audio_upload_wizard_views.xml',
        'views/audio_task_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
