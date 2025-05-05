import asyncio
import logging
import os
import time
import wave
from telethon import TelegramClient, events
from transformers import pipeline
import torch 
import soundfile as sf
import subprocess
import numpy as np
from dotenv import load_dotenv

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = 'my_telegram_session'
FFMPEG_PATH = os.getenv('FFMPEG_PATH')

# List of numeric channel IDs to monitor
CHANNELS_TO_MONITOR = [-1001114591086]

# Hugging Face model for Russian TTS
TTS_MODEL_NAME = "facebook/mms-tts-rus"

# Directory for saving audio files
AUDIO_OUTPUT_DIR = 'generated_audio'

# Target chat for sending audio (e.g., 'me' for "Saved Messages")
TARGET_CHAT_ENTITY = 'me'

# Logging configuration
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)

# --- Initialization ---

# Create Telegram client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Initialize TTS pipeline
logging.info(f"Loading TTS pipeline with model: {TTS_MODEL_NAME}...")
try:
    tts_pipeline = pipeline("text-to-speech", model=TTS_MODEL_NAME, device=0 if torch.cuda.is_available() else -1)
    logging.info("TTS pipeline successfully loaded.")
    if torch.cuda.is_available():
        logging.info("Using GPU for TTS.")
    else:
        logging.info("Using CPU for TTS.")
except Exception as e:
    logging.error(f"Error loading TTS pipeline: {e}")
    logging.error("Please ensure the transformers library is correctly installed (version 4.20+) and torch is installed with required dependencies.")
    exit()

# Create audio directory if it doesn't exist
if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)
    logging.info(f"Created audio directory: {AUDIO_OUTPUT_DIR}")

# --- New message handler ---

@client.on(events.NewMessage(chats=CHANNELS_TO_MONITOR))
async def handler_new_message(event):
    chat_id = event.chat_id
    message_id = event.id
    chat_title = 'Unknown'

    try:
        chat_entity = await client.get_entity(chat_id)
        chat_title = getattr(chat_entity, 'title', getattr(chat_entity, 'username', str(chat_id)))
    except Exception as e:
        logging.warning(f"Could not retrieve chat title for {chat_id}: {e}")

    logging.info(f"New message [{message_id}] in chat '{chat_title}' ({chat_id})")

    message_text = event.message.text
    if not message_text:
        logging.info(f"Message [{message_id}] in '{chat_title}' contains no text. Skipping.")
        return

    logging.info(f"Message text [{message_id}]: \"{message_text[:100]}...\"")

    # Convert text to speech
    logging.info(f"Starting TTS for message [{message_id}]...")
    try:
        output = tts_pipeline(message_text)
        speech_np = output['audio']
        sampling_rate = int(output['sampling_rate'])

        speech_np = speech_np.squeeze()
        if speech_np.size == 0:
            logging.error("speech_np array is empty. Check TTS pipeline output.")
            return

        base_filename = f"msg_{abs(chat_id)}_{message_id}_{int(time.time())}"
        wav_filepath = os.path.abspath(os.path.join(AUDIO_OUTPUT_DIR, f"{base_filename}.wav"))
        mp3_filepath = os.path.join(AUDIO_OUTPUT_DIR, f"{base_filename}.mp3")

        # Save WAV file
        sf.write(wav_filepath, speech_np, sampling_rate)
        time.sleep(1)  # Delay to ensure file writing completes
        logging.info(f"WAV file saved: {wav_filepath}")

        # Check if file exists
        if not os.path.exists(wav_filepath):
            logging.error(f"File {wav_filepath} not found after saving!")
            return

        # Verify file opening with wave
        try:
            with wave.open(wav_filepath, 'rb') as wav_file:
                logging.info(f"File {wav_filepath} successfully opened with wave.")
        except Exception as e:
            logging.error(f"Error opening WAV file with wave: {e}")
            return

        # Check file permissions
        if not os.access(wav_filepath, os.R_OK):
            logging.error(f"No read permissions for file {wav_filepath}!")
            return

        # Convert to MP3 using FFmpeg
        try:
            result = subprocess.run([
                FFMPEG_PATH,
                "-i", wav_filepath,
                mp3_filepath
            ], check=True, capture_output=True, text=True)
            logging.info(f"MP3 file saved: {mp3_filepath}")
            logging.info(f"FFmpeg output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error converting to MP3: {e.stderr}")
            return
        except FileNotFoundError:
            logging.error(f"FFmpeg not found at path: {FFMPEG_PATH}. Check the path or install FFmpeg.")
            return

        # Delete WAV file
        try:
            os.remove(wav_filepath)
            logging.info(f"Temporary WAV file deleted: {wav_filepath}")
        except Exception as e:
            logging.error(f"Error deleting WAV file: {e}")

    except Exception as e:
        logging.error(f"Error during TTS or audio saving for message [{message_id}]: {e}")
        return

    # Send audio to target chat
    try:
        target_entity = await client.get_entity(TARGET_CHAT_ENTITY)
        await client.send_file(target_entity, mp3_filepath,
                              caption=f"Audio from channel '{chat_title}' (Message #{message_id})")
        logging.info(f"MP3 file successfully sent to '{TARGET_CHAT_ENTITY}'.")
    except Exception as e:
        logging.error(f"Error sending MP3 file for message [{message_id}]: {e}")

# --- Client startup ---

async def main():
    """
    Main function to start the application.
    """
    print("Starting Telegram client...")

    # Connect to Telegram
    await client.start(phone=PHONE_NUMBER)
    print("Telegram client started.")

    if not CHANNELS_TO_MONITOR:
        logging.error("CHANNELS_TO_MONITOR list is empty! Please populate it with channel IDs or usernames.")
        print("Error: CHANNELS_TO_MONITOR list is empty. Populate it and restart.")
        return

    print(f"Monitoring channels: {CHANNELS_TO_MONITOR}")
    print(f"Audio will be sent to chat: '{TARGET_CHAT_ENTITY}'")
    print(f"Audio files will be saved in directory: '{AUDIO_OUTPUT_DIR}'")

    print("Application started. Waiting for new messages...")
    await client.run_until_disconnected()
    print("Telegram client stopped.")

if __name__ == '__main__':
    # Check for FFmpeg
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-version"],
            capture_output=True,
            text=True,
            check=True
        )
        logging.info(f"FFmpeg version: {result.stdout.splitlines()[0]}")
    except FileNotFoundError:
        print("-" * 50)
        print(f"ERROR: FFmpeg not found at path {FFMPEG_PATH}. Ensure FFmpeg is installed and the path is correct.")
        print("-" * 50)
        exit(1)
    except subprocess.CalledProcessError as e:
        print("-" * 50)
        print(f"ERROR: Could not run FFmpeg: {e}")
        print("-" * 50)
        exit(1)
    except Exception as e:
        print("-" * 50)
        print(f"ERROR: Unknown error while checking FFmpeg: {e}")
        print("-" * 50)
        exit(1)

    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application stopped by user.")
    except Exception as e:
        logging.exception("An unexpected error occurred:")