# import time
# import requests
# from bs4 import BeautifulSoup
# import hashlib
# from plyer import notification
# import webbrowser
# import winsound  # For sound alert
# from telegram import Bot
# import asyncio
# import sys

# # URL for monitoring
# URL ='https://httpbin.org/get'
# URL1 = 'https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01'  # Replace with real page
# CHECK_INTERVAL = 1  # seconds

# # Telegram credentials
# TELEGRAM_TOKEN = '7763897628:AAEQVDEOBfHmWHbyfeF_Cx99KrJW2ILlaw0'
# CHAT_ID = '553863319'

# # Sound file path for notification
# sound_path = r"C:\Users\Blanca\Desktop\Orlando-The-Book-of-Mormon.wav"  # Replace with your actual sound file path

# def send_telegram_alert():
#     """Send an alert to Telegram with an image."""
#     async def main():
#         bot = Bot(token=TELEGRAM_TOKEN)
#         # Send a photo with a caption
#         with open(r"C:\Users\Blanca\Desktop\foto.webp", "rb") as photo:  # Replace with your image path
#             await bot.send_photo(chat_id=CHAT_ID, photo=photo, caption=f'🎭 Ticket alert! The page has changed. Please open the following link to purchase tickets {URL1}')

#     try:
#         asyncio.run(main())
#         print("📲 Telegram alert with image sent.")
#     except Exception as e:
#         print(f"❌ Failed to send Telegram image: {e}")


# def notify_change():
#     """Notify the user of a page update."""
#     # Send popup notification
#     notification.notify(
#         title='🎭 Ticket Update Detected!',
#         message='The page has changed. Click to check!',
#         timeout=10
#     )
#     print("🔔 Popup sent.")

#     # Custom sound
#     winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

#     # Optional: Open the URL automatically in a browser
#     webbrowser.open(URL1)

#     # Call the async Telegram alert function
#     asyncio.run(send_telegram_alert())

# def get_page_content(url):
#     """Fetch the content of the page."""
#     try:
#         response = requests.get(url, timeout=10)
#         response.raise_for_status()
#         soup = BeautifulSoup(response.text, 'html.parser')
#         return soup.get_text()
#     except Exception as e:
#         print(f"Error fetching page: {e}")
#         return ''

# def hash_content(content):
#     """Generate a hash of the page content."""
#     return hashlib.md5(content.encode('utf-8')).hexdigest()

# def main():
#     """Main function to monitor the page for changes and notify the user."""
#     start_time = time.time()  # Track the start time
#     print(r'''
#   _    _                   _____  _               ______     _                        _ 
#  | |  | |                 |  __ \(_)             |  ____|   | |                      (_)
#  | |__| | __ _ ___  __ _  | |  | |_  __ _  __ _  | |__   ___| |__   _____      ____ _ _ 
#  |  __  |/ _` / __|/ _` | | |  | | |/ _` |/ _` | |  __| / _ \ '_ \ / _ \ \ /\ / / _` | |
#  | |  | | (_| \__ \ (_| | | |__| | | (_| | (_| | | |___|  __/ |_) | (_) \ V  V / (_| | |
#  |_|  |_|\__,_|___/\__,_| |_____/|_|\__, |\__,_| |______\___|_.__/ \___/ \_/\_/ \__,_|_|
#                                      __/ |                                              
#                                     |___/     
#                 (╯°□°）╯︵ ┻━┻ 
#               _         _                                   __                       ___
#   __   ___.--'_`.     .'_`--.___   __                      / _|_ __ ___   __ _ ___  |  |
#  ( _`.'. -   'o` )   ( 'o`   - .`.'_ )                    | |_| '__/ _ \ / _` / __| |  |
#  _\.'_'      _.-'     `-._      `_`./_                    |  _| | | (_) | (_| \__ \ |  |
# ( \`. )    //\`         '/\\    ( .'/ )                   |_| |_|  \___/ \__, |___/ |__|     
#  \_`-'`---'\\__,       ,__//`---'`-'_/                                   |___/      (_)
#   \`        `-\         /-'        '/
#    `                               '  
# ''')
#     print("🌟✨ Iniciando Script: 🎭 Monitor de Entradas ✨🌟")
#     print("🚀  ¡Bienvenida! El monitoreo está activo.")
#     time.sleep(1)
#     print("📝  Empezando a vigilar los cambios... 🎟️")
#     print("📡 Monitoreo iniciado... 📡")
#     time.sleep(1)
#     print("\n🔍  Observando tus entradas y buscando actualizaciones 👀")
#     print("\n  ⬇️ ¡Atenta a las notificaciones! ⬇️\n")
#     time.sleep(1)
#     print("══════════════════════════════════════════")
#     print("       🕵️‍♀️👀 Monitoreo en curso... 📜")
#     print("══════════════════════════════════════════\n")
#     time.sleep(1)
#     print(f"Entra a la página web de Book of Mormon para más información (ctrl+click)\n")
#     print(URL1)

#     dots = 0  # To count the number of dots in the animation
#     old_hash = ''

#     while True:
#         # Calculate elapsed time
#         elapsed_time = time.time() - start_time
#         minutes = int(elapsed_time // 60)
#         seconds = int(elapsed_time % 60)

#         # Show dot animation and elapsed time
#         sys.stdout.write(f'\rTime Elapsed: {minutes:02}:{seconds:02}  Checking for updates{"." * (dots % 4)}   ')
#         sys.stdout.flush()

#         # Increment the dot counter and adjust the delay for the animation
#         dots += 1
#         time.sleep(0.01)  # Adjust the speed of the dots animation
        
#         content = get_page_content(URL)
#         if not content:
#             time.sleep(CHECK_INTERVAL)
#             continue

#         new_hash = hash_content(content)
#         if old_hash and new_hash != old_hash:
#             notify_change()

#         old_hash = new_hash
#         time.sleep(CHECK_INTERVAL)

# # Run the main function
# if __name__ == '__main__':
#     main()
import time
import requests
from bs4 import BeautifulSoup
import hashlib
from plyer import notification
import webbrowser
import winsound
from telegram import Bot
import asyncio
import sys
from urllib3.util.retry import Retry

# List of URLs to monitor
URLS = [
    'https://wickedelmusical.com/',
    'https://wickedelmusical.com/elenco',
    'https://www.houdinielmusical.com',
    'https://miserableselmusical.es/',
    'https://thebookofmormonelmusical.es/elenco/',
    'https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01'
]

CHECK_INTERVAL = 2  # Seconds between checks
MAX_CONSECUTIVE_FAILURES = 5  # Attempts before disabling temporarily
RETRY_BACKOFF = {url: 30 for url in URLS}  # Initial retry delay (in seconds)

# Telegram credentials
TELEGRAM_TOKEN = '7763897628:AAEQVDEOBfHmWHbyfeF_Cx99KrJW2ILlaw0'
CHAT_ID = '553863319'

# Sound file path for notification
sound_path = r"C:\Users\Blanca\Desktop\Orlando-The-Book-of-Mormon.wav"

# Initialize state
old_hashes = {url: '' for url in URLS}
start_time = time.time()
consecutive_failures = {url: 0 for url in URLS}
disabled_urls = set()

def create_session():
    """Create a requests session with retry strategy."""
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = create_session()

def send_telegram_alert(url, changes, timestamp):
    """Send an alert to Telegram when a change is detected, with time and details."""
    async def main():
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🎭 *Ticket Alert!*\n"
            f"🌐 URL: {url}\n"
            f"🕒 Cambio detectado: {timestamp}\n"
            f"📄 Cambios:\n```{changes[:3500]}```"
        )
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    
    try:
        asyncio.run(main())
        print(f"📲 Telegram alert sent for {url}")
    except Exception as e:
        print(f"❌ Failed to send Telegram alert: {e}")

        
import websockets  # Make sure you install `websockets` library

async def notify_godot(url):
    """Send a WebSocket message to Godot when a change is detected."""
    async with websockets.connect("ws://localhost:8765") as ws:
        await ws.send(f"UPDATE:{url}")


import difflib

# Modify the old_hashes dictionary to store actual content instead of just hashes
old_contents = {url: "" for url in URLS}

def find_differences(old_text, new_text):
    """Generate a diff showing changes between old and new content."""
    diff = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="")
    return "\n".join(diff)

def notify_change(url, old_text, new_text):
    """Notify the user of a page update with details."""
    changes = find_differences(old_text, new_text)
    short_message = f'The page {url} has changed. Click to check!\nChanges:\n{changes}'
    
    # Windows notification balloon message must be ≤ 256 chars
    max_length = 250
    if len(short_message) > max_length:
        short_message = short_message[:max_length] + '...'

    notification.notify(
        title='🎭 Ticket Update Detected!',
        message=short_message,
        timeout=10
    )
    
    print(f"🔔 Notification sent for {url}")
    print(f"📝 Changes detected:\n{changes}")

    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    webbrowser.open(url)
    send_telegram_alert(url)

    
def get_page_content(url):
    """Fetch the content of a page with robust error handling."""
    try:
        response = SESSION.get(url, timeout=15)  
        response.raise_for_status()

        if not response.text.strip():
            raise ValueError("Empty response content")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()

    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error fetching {url}: {str(e)[:200]}")
        return ''

def hash_content(content):
    """Generate a hash of the page content."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def elapsed_time():
    """Display elapsed monitoring time with animation."""
    seconds = int(time.time() - start_time)
    minutes = seconds // 60
    seconds %= 60
    animations = ["|", "/", "-", "\\"]
    animation = animations[seconds % len(animations)]
    return f"\r🔍 Observando entradas... ⏳ Tiempo transcurrido: {minutes} min {seconds} sec {animation}"

def print_banner():
    """Print the script banner."""
    print(r'''
  _    _                   _____  _               ______     _                        _ 
 | |  | |                 |  __ \(_)             |  ____|   | |                      (_)
 | |__| | __ _ ___  __ _  | |  | |_  __ _  __ _  | |__   ___| |__   _____      ____ _ _ 
 |  __  |/ _ / __|/ _ | | |  | | |/ _ |/ _ | |  __| / _ \ '_ \ / _ \ \ /\ / / _ | |
 | |  | | (_| \__ \ (_| | | |__| | | (_| | (_| | | |___|  __/ |_) | (_) \ V  V / (_| | |
 |_|  |_|\__,_|___/\__,_| |_____/|_|\__, |\__,_| |______\___|_.__/ \___/ \_/\_/ \__,_|_|
                                     __/ |                                              
                                    |___/     
                (╯°□°）╯︵ ┻━┻ 
              _         _                                   __                       _
  __   ___.--'_.     .'_--.___   __                      / _|_ __ ___   __ _ ___  | |
 ( _.'. -   'o )   ( 'o   - ..'_ )                    | |_| '__/ _ \ / _ / __| | |
 _\.'_'      _.-'     -._      _./_                    |  _| | | (_) | (_| \__ \ | |
( \. )    //\         '/\\    ( .'/ )                   |_| |_|  \___/ \__, |___/ |_|     
 \_-'---'\\__,       ,__//---'-'_/                                   |___/      (_)
  \        -\         /-'        '/
                                  '  
''')
    print("🌟✨ Iniciando Script: 🎭 Monitor de Entradas ✨🌟")
    print("🚀  ¡Bienvenida! El monitoreo está activo.")
    time.sleep(1)
    print("📝  Empezando a vigilar los cambios... 🎟️")
    print("📡 Monitoreo iniciado... 📡")
    time.sleep(1)
    print("\n🔍  Observando tus entradas y buscando actualizaciones 👀")
    print("\n  ⬇️ ¡Atenta a las notificaciones! ⬇️\n")
    time.sleep(1)
    print("══════════════════════════════════════════")
    print("       🕵️‍♀️👀 Monitoreo en curso... 📜")
    print("══════════════════════════════════════════\n")
    time.sleep(1)

def reenable_disabled_urls():
    """Attempt to re-enable URLs after a backoff period."""
    global disabled_urls
    for url in list(disabled_urls):
        print(f"\n♻️ Reintentando conexión con {url}...")
        content = get_page_content(url)
        if content:
            print(f"✅ ¡Rehabilitado {url}!")
            disabled_urls.remove(url)
            consecutive_failures[url] = 0
            RETRY_BACKOFF[url] = 30  # Reset backoff
        else:
            RETRY_BACKOFF[url] = min(RETRY_BACKOFF[url] * 2, 600)  # Max 10 min

def main():
    """Main monitoring function with change detection."""
    print_banner()

    while True:
        sys.stdout.write(elapsed_time())
        sys.stdout.flush()

        for url in URLS:
            if url in disabled_urls:
                continue  
            
            content = get_page_content(url)
            if not content:
                consecutive_failures[url] += 1
                continue
            
            consecutive_failures[url] = 0  
            
            if old_contents[url] and content != old_contents[url]:  
                notify_change(url, old_contents[url], content)
            
            old_contents[url] = content  

        reenable_disabled_urls()
        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Script detenido manualmente. ¡Hasta pronto!")
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")