{
    'name': 'Audio AI Processor',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Transcribe audio files using OpenAI Whisper',
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
        'security/audio_ai_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'report/audio_task_report.xml',
        'wizard/audio_upload_wizard_views.xml',
        'views/audio_category_views.xml',
        'views/audio_tag_views.xml',
        'views/audio_task_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
