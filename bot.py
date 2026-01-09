import os
import telebot
from flask import Flask, request, abort
from telebot.types import Update
import requests
from datetime import datetime

app = Flask(__name__)

# Token từ env
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Giữ nguyên entry_ids, CA_CONFIG, HO_TEN, CHUC_VU, DIA_DIEM, FORM_URL từ code cũ
# (copy paste toàn bộ phần đó vào đây)

# user_states, handlers giống cũ (start_report, handle_message, handle_callback)
# Copy toàn bộ @bot.message_handler, @bot.callback_query_handler từ code cũ

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

# Set webhook khi start (chạy 1 lần thủ công hoặc trong deploy)
# Sau deploy, mở browser hoặc dùng curl/postman: https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://your-bot-name.onrender.com/webhook

@app.route('/')
def health():
    return "Bot is alive!", 200  # Để Render check healthy, tránh restart

if __name__ == '__main__':
    # Local test polling (optional)
    # bot.infinity_polling()
    print("Flask server starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))