import os
import telebot
from flask import Flask, request
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import atexit

app = Flask(__name__)

# Token từ env
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Entry IDs và FORM_URL
entry_ids = {
    'ho_ten': '1365137621',
    'ngay_base': '505433408',
    'ca_lam_viec': '1611010004',
    'chuc_vu': '1574688835',
    'dia_diem': '309113117',
    'tinh_hinh_ca': '363320806',
    'cong_viec_1': '54322254',
    'cong_viec_2': '706440063',
    'cong_viec_3': '288416076',
    'cong_viec_4': '169401106',
    'cong_viec_5': '223495343',
}

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScjsFj9xeDHd6T7BwPCt5XzfCGKNhwuh3BxtSfCOADwBhao6w/formResponse"

# Config ca
CA_CONFIG = {
    'Ca 1': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 2': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 3': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Hành chính': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Xử lý các sự cố kỹ thuật phát sinh và những tình huống khẩn cấp', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ phép': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ bù - Nghỉ Chủ nhật': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Khác': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
}

# Tên cố định
NAME_OPTIONS = ["Bùi Hữu Huy", "Trịnh Xuân Tân"]

# Thông tin theo tên
USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trịnh Xuân Tân": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP Km102 - Cao tốc"}
}

# File lưu trạng thái đã báo cáo (chat_id: ngày đã báo cáo)
REPORTED_FILE = "reported.json"

try:
    with open(REPORTED_FILE, 'r', encoding='utf-8') as f:
        reported_today = json.load(f)
except FileNotFoundError:
    reported_today = {}

def save_reported(chat_id, date_str):
    reported_today[str(chat_id)] = date_str
    with open(REPORTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(reported_today, f, ensure_ascii=False, indent=4)
    print(f"Đã lưu báo cáo cho {chat_id} ngày {date_str}")

def has_reported_today(chat_id):
    today = datetime.now().strftime("%d/%m/%Y")
    return reported_today.get(str(chat_id)) == today

# Trạng thái người dùng
user_states = {}

# Scheduler
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

def send_reminders():
    now = datetime.now()
    today = now.strftime("%d/%m/%Y")
    
    for chat_id_str in list(reported_today.keys()):
        chat_id = int(chat_id_str)
        if reported_today[chat_id_str] != today or has_reported_today(chat_id):
            continue
        if now.hour >= 8 and now.hour <= 22 and now.minute < 5:
            try:
                bot.send_message(chat_id, "Chào bạn! Hôm nay bạn chưa báo cáo ca làm việc. Gửi /report để báo cáo nhé! 😊")
            except Exception as e:
                print("Lỗi gửi nhắc nhở:", str(e))

def daily_stats():
    today = datetime.now().strftime("%d/%m/%Y")
    stats = []
    for name in NAME_OPTIONS:
        status = "Đã báo cáo" if any(v == today for v in reported_today.values()) else "Chưa báo cáo"
        stats.append(f"- {name}: {status}")
    message = f"Thống kê hôm nay ({today}):\n" + "\n".join(stats) + "\nAi chưa làm thì gửi /report nhé!"
    
    # Gửi cho từng người đã từng báo cáo
    for chat_id_str in list(reported_today.keys()):
        try:
            bot.send_message(int(chat_id_str), message)
        except:
            pass

scheduler.add_job(send_reminders, IntervalTrigger(minutes=5))
scheduler.add_job(daily_stats, CronTrigger(hour=22, minute=0))
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

# Handler /start và /report
@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(name, callback_data=f"name_{name}"))
    bot.reply_to(message, "Chọn tên của bạn để bắt đầu báo cáo:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('name_'))
def handle_name_callback(call):
    chat_id = call.message.chat.id
    selected_name = call.data.replace('name_', '')
    
    if selected_name not in NAME_OPTIONS:
        bot.answer_callback_query(call.id, "Tên không hợp lệ!")
        return
    
    bot.edit_message_text(f"Đã chọn: {selected_name}\nBắt đầu báo cáo công việc.\nBước 1: Nhập ngày (dd/mm/yyyy, ví dụ: {datetime.now().strftime('%d/%m/%Y')}):", call.message.chat.id, call.message.message_id)
    
    user_states[chat_id] = {
        'step': 1,
        'date': '',
        'ca': '',
        'selected_name': selected_name
    }
    bot.answer_callback_query(call.id)

# Handler nhập ngày
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        bot.reply_to(message, "Gửi /report để bắt đầu báo cáo.")
        return
    
    state = user_states[chat_id]
    if state['step'] == 1:
        date_str = message.text.strip()
        try:
            day, month, year = map(int, date_str.split('/'))
            datetime(year, month, day)
            state['date'] = date_str
            markup = InlineKeyboardMarkup()
            for ca in CA_CONFIG:
                markup.add(InlineKeyboardButton(ca, callback_data=ca))
            bot.reply_to(message, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['step'] = 2
        except:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy.")

# Handler chọn ca & submit
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    if chat_id not in user_states or user_states[chat_id]['step'] != 2:
        return
    
    ca = call.data
    if ca not in CA_CONFIG:
        bot.answer_callback_query(call.id, "Ca không hợp lệ!")
        return
    
    state = user_states[chat_id]
    state['ca'] = ca
    config = CA_CONFIG[ca]
    selected_name = state['selected_name']
    user_info = USER_PROFILES[selected_name]
    
    bot.edit_message_text("Đang gửi báo cáo...", chat_id, call.message.message_id)
    
    day, month, year = map(int, state['date'].split('/'))
    
    data = {
        'fvv': '1',
        'pageHistory': '0,1',
        'fbzx': '1',
        'submissionTimestamp': '-1',
        
        f'entry.{entry_ids["ho_ten"]}': selected_name,
        f'entry.{entry_ids["ngay_base"]}_year': str(year),
        f'entry.{entry_ids["ngay_base"]}_month': f'{month:02d}',
        f'entry.{entry_ids["ngay_base"]}_day': f'{day:02d}',
        f'entry.{entry_ids["ca_lam_viec"]}': ca,
        f'entry.{entry_ids["chuc_vu"]}': user_info['chuc_vu'],
        f'entry.{entry_ids["dia_diem"]}': user_info['dia_diem'],
        f'entry.{entry_ids["tinh_hinh_ca"]}': config['tinh_hinh'],
        
        f'entry.{entry_ids["cong_viec_1"]}': config['cong_viec_1'],
        f'entry.{entry_ids["cong_viec_2"]}': config['cong_viec_2'],
        f'entry.{entry_ids["cong_viec_3"]}': config['cong_viec_3'],
        f'entry.{entry_ids["cong_viec_4"]}': config['cong_viec_4'],
        f'entry.{entry_ids["cong_viec_5"]}': config['cong_viec_5'],
    }
    
    try:
        response = requests.post(FORM_URL, data=data)
        print(f"DEBUG: Form submit status: {response.status_code}")
        if response.status_code in (200, 302):
            summary = f"- Tình hình: {config['tinh_hinh']}\n- CV1: {config['cong_viec_1']}\n- CV2: {config['cong_viec_2']}\n- CV3: {config['cong_viec_3']}"
            bot.edit_message_text(
                f"✅ Báo cáo ngày {state['date']}, ca {ca} gửi thành công!\n"
                f"Thông tin: {selected_name} - {user_info['chuc_vu']} - {user_info['dia_diem']}\nChi tiết:\n{summary}",
                chat_id, call.message.message_id
            )
            save_reported(chat_id, state['date'])
        else:
            bot.edit_message_text(f"❌ Lỗi gửi form (code {response.status_code})", chat_id, call.message.message_id)
    except Exception as e:
        print("ERROR submit form:", str(e))
        bot.edit_message_text(f"❌ Lỗi kết nối: {str(e)}", chat_id, call.message.message_id)
    
    del user_states[chat_id]
    bot.answer_callback_query(call.id)

# Webhook và health
@app.route('/webhook', methods=['POST'])
def webhook():
    print("=== DEBUG: NEW WEBHOOK REQUEST ===")
    print("From IP:", request.remote_addr)
    print("Content-Type:", request.headers.get('content-type'))
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            print("Raw JSON from Telegram:", json_string)
            update_dict = json.loads(json_string)
            update = Update.de_json(update_dict)
            if update:
                print("Update parsed successfully. Message text:", update.message.text if update.message else "No message")
                bot.process_new_updates([update])
                print("process_new_updates called OK")
            else:
                print("Update parse failed: None")
        except Exception as e:
            print("ERROR in webhook:", str(e))
    else:
        print("Not JSON request")
    return '', 200

@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Flask server starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))