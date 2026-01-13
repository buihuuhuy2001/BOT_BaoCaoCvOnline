import os
import telebot
from flask import Flask, request
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime, time
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
import atexit
import time

app = Flask(__name__)

# Debug múi giờ
print("=== DEBUG MÚI GIỜ ===")
print("Server UTC:", datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
print("VN time:", datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d %H:%M:%S"))
print("=======================================")

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Tự động set webhook
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"[WEBHOOK SUCCESS] Set: {WEBHOOK_URL}")
except Exception as e:
    print(f"[WEBHOOK ERROR] {str(e)}")

# File lưu state bền vững (tránh mất khi restart)
STATE_FILE = "user_states.json"
try:
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        user_states = json.load(f)
except FileNotFoundError:
    user_states = {}

def save_states():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_states, f, ensure_ascii=False, indent=4)

# Các config còn lại giữ nguyên (entry_ids, FORM_URL, CA_CONFIG, NAME_OPTIONS, USER_PROFILES, reported/pending files, functions has_reported, mark_as_reported, save_pending, submit_to_form, process_pending_reports, send_hourly_reminder, report_all_status)

# Scheduler bù trừ -7h (UTC server)
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
scheduler.add_job(process_pending_reports, IntervalTrigger(minutes=5))
scheduler.add_job(process_pending_reports, CronTrigger(hour='1,7,10,15', minute=1))
scheduler.add_job(send_hourly_reminder, CronTrigger(hour='1-15', minute=0))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# --- Handlers với FIX LOADING & STATE BỀN VỮNG ---

@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(name, callback_data=f"name_{name}"))
    bot.reply_to(message, "Chọn tên của bạn để bắt đầu báo cáo:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('name_'))
def handle_name_callback(call):
    print(f"[CALLBACK NAME] data={call.data} chat_id={call.message.chat.id}")
    bot.answer_callback_query(call.id, text="Đang xử lý...")  # Dừng loading, hiển thị thông báo
    chat_id = str(call.message.chat.id)  # dùng str để lưu JSON
    selected_name = call.data.replace('name_', '')
    if selected_name not in NAME_OPTIONS:
        return
    bot.edit_message_text(
        f"Đã chọn: {selected_name}\nChọn loại ngày báo cáo:",
        call.message.chat.id, call.message.message_id
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("Ngày hiện tại", callback_data="date_today"))
    markup.add(InlineKeyboardButton("Tự chọn ngày khác", callback_data="date_custom"))
    sent_msg = bot.send_message(call.message.chat.id, "Chọn ngày báo cáo:", reply_markup=markup)
    user_states[chat_id] = {
        'step': 'choose_date_type',
        'name': selected_name,
        'message_id': sent_msg.message_id,
        'chat_id': call.message.chat.id
    }
    save_states()
    known_chat_ids.add(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data in ["date_today", "date_custom"])
def handle_date_type(call):
    print(f"[CALLBACK DATE] data={call.data}")
    bot.answer_callback_query(call.id, text="Đang xử lý...")
    chat_id = str(call.message.chat.id)
    state = user_states.get(chat_id)
    if not state or state.get('step') != 'choose_date_type':
        print("[DEBUG] State không hợp lệ ở date_type")
        return
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
    if call.data == "date_today":
        today = datetime.now(vn_tz).strftime("%d/%m/%Y")
        state['date'] = today
        state['step'] = 2
        markup = InlineKeyboardMarkup(row_width=2)
        for ca in CA_CONFIG:
            markup.add(InlineKeyboardButton(ca, callback_data=ca))
        sent_msg = bot.send_message(call.message.chat.id, f"Ngày báo cáo: {today} (hôm nay)\nChọn ca làm việc:", reply_markup=markup)
        state['message_id'] = sent_msg.message_id
        save_states()
    else:
        state['step'] = 1
        bot.send_message(call.message.chat.id, "Nhập ngày báo cáo (dd/mm/yyyy):")
        save_states()

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    print(f"[CALLBACK CA] data={call.data} chat_id={call.message.chat.id}")
    bot.answer_callback_query(call.id, text="Đang xử lý...")  # Dừng loading

    chat_id_str = str(call.message.chat.id)
    state = user_states.get(chat_id_str)
    if not state:
        print("[DEBUG] Không tìm thấy state cho chat", chat_id_str)
        bot.edit_message_text("Lỗi trạng thái, vui lòng gửi /report lại nhé!", call.message.chat.id, call.message.message_id)
        return

    try:
        if state.get('step') == 'confirm_overwrite':
            if call.data == 'yes_overwrite':
                schedule_report(call.message.chat.id, state, overwrite=True)
            else:
                bot.edit_message_text("Đã hủy. Gửi /report để thử lại!", call.message.chat.id, state['message_id'])
                del user_states[chat_id_str]
                save_states()
            return

        if state.get('step') != 2:
            print("[DEBUG] Step không phải 2:", state.get('step'))
            bot.edit_message_text("Trạng thái không hợp lệ, gửi /report lại nhé!", call.message.chat.id, state['message_id'])
            return

        ca = call.data
        if ca not in CA_CONFIG:
            bot.answer_callback_query(call.id, "Ca không hợp lệ!")
            return

        state['ca'] = ca
        known_chat_ids.add(call.message.chat.id)

        # Xóa nút chọn ca ngay lập tức
        bot.edit_message_reply_markup(call.message.chat.id, state['message_id'], reply_markup=InlineKeyboardMarkup())

        if has_reported(state['name'], state['date']):
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("✅ Có, báo lại", callback_data='yes_overwrite'),
                InlineKeyboardButton("❌ Không", callback_data='no_overwrite')
            )
            config = CA_CONFIG[ca]
            bot.edit_message_text(
                f"⚠️ {state['name']} đã báo ngày {state['date']}!\nCa mới: {ca}\nTình hình: {config['tinh_hinh']}\n\nChắc chắn báo lại?",
                call.message.chat.id, state['message_id'], reply_markup=markup
            )
            state['step'] = 'confirm_overwrite'
            save_states()
            return

        schedule_report(call.message.chat.id, state, overwrite=False)
    except Exception as e:
        print(f"[CALLBACK ERROR] {str(e)}")
        bot.edit_message_text("Có lỗi xảy ra. Vui lòng gửi /report lại!", call.message.chat.id, state.get('message_id', call.message.message_id))

def schedule_report(chat_id, state, overwrite=False):
    # Giữ nguyên hàm này, chỉ thêm print debug
    print(f"[SCHEDULE] Bắt đầu gửi cho {state['name']}, ca {state['ca']}")
    # ... code còn lại giữ nguyên

# Webhook với debug
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        try:
            update = Update.de_json(json_string)
            if update:
                print(f"[WEBHOOK] Nhận update_id={update.update_id}")
                bot.process_new_updates([update])
                return '', 200
        except Exception as e:
            print(f"[WEBHOOK ERROR] {e}")
    return '', 200

@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Bot starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))