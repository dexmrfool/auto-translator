import os
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

# We will use Gemini for high-quality translation
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logging.getLogger("google").setLevel(logging.ERROR)

load_dotenv()

# Configuration
API_ID = int(os.getenv("API_ID", "2282111"))
API_HASH = os.getenv("API_HASH", "da58a1841a16c352a2a999171bbabcad")
SESSION_STRING = os.getenv("SESSION_STRING") # The session of the account you use to chat
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Define the group you want the bot to listen to
TARGET_CHAT = "receive_suppurt_gc" # Replace with your target group link or ID

if not SESSION_STRING:
    logging.error("Please add SESSION_STRING to your environment variables.")
    exit(1)
if not GEMINI_API_KEY:
    logging.error("Please add GEMINI_API_KEY to your environment variables.")
    exit(1)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def translate_text(text, target_language):
    """Uses Gemini to translate text accurately."""
    try:
        # We tell Gemini to ignore English and Hindi so it doesn't spam translations for messages you already understand!
        prompt = f"If the following text is mostly in English or Hindi, output exactly 'NO_TRANSLATION'. Otherwise, translate the text to {target_language}. Respond ONLY with the translated text (or 'NO_TRANSLATION'), nothing else. Text: '{text}'"
        response = await gemini_client.aio.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        result = response.text.strip()
        if "NO_TRANSLATION" in result:
            return None
        return result
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return None

import re

# Global variable to track if the translator is currently active
TRANSLATOR_ENABLED = True

@client.on(events.NewMessage(chats=TARGET_CHAT))
async def translator_handler(event):
    global TRANSLATOR_ENABLED

    # 1. OUTGOING MESSAGES (Commands & Manual Translation)
    if event.out:
        # Command to pause the auto-translator
        if event.raw_text.strip() == '.tr_off':
            TRANSLATOR_ENABLED = False
            await event.edit("❌ **Auto-Translator Paused.** I will ignore incoming messages.")
            return
            
        # Command to resume the auto-translator
        if event.raw_text.strip() == '.tr_on':
            TRANSLATOR_ENABLED = True
            await event.edit("✅ **Auto-Translator Resumed.** I am listening again.")
            return

        # Automatically translate everything you type to Persian!
        # (It ignores messages starting with '.' so you can still use commands like .tr_off)
        if not event.raw_text.startswith('.'):
            original_text = event.raw_text
            translated = await translate_text(original_text, "Persian")
            if translated:
                await event.edit(translated)
                logging.info(f"Translated Outgoing: {original_text} -> {translated}")
        return

    # 2. INCOMING MESSAGES (Persian guy typing -> Bot replies in the group with English)
    
    # If you paused the translator, immediately stop and do nothing.
    if not TRANSLATOR_ENABLED:
        return
        
    if not event.out and event.raw_text:
        # Only call the Gemini API if the message actually contains Persian/Arabic characters!
        if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', event.raw_text):
            # Tell Gemini to translate it to English
            translated = await translate_text(event.raw_text, "English")
            
            if translated:
                # Send the translation directly into the group as a reply to the foreign message!
                msg = f"**[Auto-Translation]**\n{translated}"
                await event.reply(msg)
                logging.info(f"Replied in group with translation.")

from aiohttp import web

async def dummy_server():
    try:
        async def hello(request):
            return web.Response(text="Auto-Translator is running live on Render!")
        app = web.Application()
        app.add_routes([web.get('/', hello)])
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logging.info(f"Render health-check server started on port {port}")
    except Exception as e:
        logging.error(f"Failed to start web server: {e}")

async def main():
    logging.info("Starting Auto-Translator Userbot...")
    
    # Start web server for Render health checks
    await dummy_server()
    
    await client.start()
    logging.info("Translator is running! Listening to target chat...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
