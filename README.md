# Telegram TTS Bot

A Telegram bot that monitors specified channels and converts incoming text messages to speech using a text-to-speech (TTS) model from Hugging Face (facebook/mms-tts-rus). 

## Features
- Monitors Telegram channels for new messages.
- Converts text to speech using the `facebook/mms-tts-rus` model.
- Saves audio as MP3 and sends it to a specified chat (e.g., Saved Messages).

## Installation
1. Clone the repository:
    ```bash
   git clone https://github.com/your-username/telegram-tts-bot.git

2. Install dependencies:
    ```bash
    pip install -r requirements.txt

3. Set up environment variables (see Configuration).

4. fill the variables in file

5. Run audio_dictor.py
    ```bash
    python audio_dictor.py

## Requirements
Python 3.8+
FFmpeg installed
Libraries listed in requirements.txt

## License
MIT License


