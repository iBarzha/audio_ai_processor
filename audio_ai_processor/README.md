# Audio AI Processor

Odoo 17 module for audio transcription using OpenAI Whisper API.

## Features

- Upload audio files (MP3, WAV, M4A, OGG, FLAC)
- Queue-based processing
- Automatic transcription
- Download results as text files

## Installation

1. Copy module to Odoo addons folder
2. Install Python dependency: `pip install openai`
3. Restart Odoo and install the module

## Configuration

1. Go to **Settings**
2. Find **Audio AI Processor** section
3. Enter your **OpenAI API Key**
4. Select transcription language
5. Choose processing mode:
   - **Immediate** - process tasks one after another
   - **Scheduled** - process only during specific hours

## Usage

1. Go to **Audio AI** menu
2. Create new task or use **Upload Multiple Files**
3. Upload audio file
4. Click **Add to Queue**
5. Wait for transcription to complete

## License

LGPL-3
