import os
import telebot
from flask import Flask, request, abort
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime
import json

app = Flask(__name__)

# Token từ env (Render sẽ set biến BOT_TOKEN)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Entry IDs (giữ nguyên từ code cũ của bạn)
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

# Thông tin mặc định
HO_TEN = "Bùi Hữu Huy"
CHUC_VU = "Nhân viên Kỹ thuật - Công nghệ"
DIA_DIEM = "TTP QL279 - Cao tốc"

# URL Google Form
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScjsFj9xeDHd6T7BwPCt5XzfCGKNhwuh3BxtSfCOADwBhao6w/formResponse"

# Config ca làm việc (giữ nguyên từ code cũ)
CA_CONFIG = {
    'Ca 1': {'tinh_hinh': 'Bình thường', 
             'cong_viec_1': 'Hỗ trợ vận hành thu phí', 
             'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 
             'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 
             'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 2': {'tinh_hinh': 'Bình thường', 
             'cong_viec_1': 'Hỗ trợ vận hành thu phí', 
             'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 
             'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 
             'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 3': {'tinh_hinh': 'Bình thường', 
             'cong_viec_1': 'Hỗ trợ vận hành thu phí', 
             'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 
             'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 
             'cong_viec_4': '', 'cong_viec_5': ''},
    'Hành chính': {'tinh_hinh': 'Bình thường', 
                   'cong_viec_1': 'Xử lý các sự cố kỹ thuật phát sinh và những tình huống khẩn cấp', 
                   'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 
                   'cong_viec_3': '', 
                   'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ phép': {'tinh_hinh': 'Khác', 
                  'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 
                  'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ bù - Nghỉ Chủ nhật': {'tinh_hinh': 'Khác', 
                                'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 
                                'cong_viec_4': '', 'cong_viec_5': ''},
    'Khác': {'tinh_hinh': 'Khác', 
             'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 
             'cong_viec_4': '', 'cong_viec_5': ''},
}

# Lưu trạng thái người dùng
user_states = {}  # {chat_id: {'step': int, 'date': str, 'ca': str}}

# Handler lệnh /start và /report
@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    print(f"DEBUG: Received command from {message.chat.id}: {message.text}")
    bot.reply_to(message, "Chào Bùi Hữu Huy! Bắt đầu báo cáo công việc.\nBước 1: Nhập ngày (dd/mm/yyyy, ví dụ: 09/01/2026):")
    user_states[message.chat.id] = {'step': 1, 'date': '', 'ca': ''}

# Handler tin nhắn thường (xử lý ngày và các bước tiếp)
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        bot.reply_to(message, "Gửi /report để bắt đầu báo cáo.")
        return

    state = user_states[chat_id]
    print(f"DEBUG: Handling message from {chat_id}, step {state['step']}, text: {message.text}")

    if state['step'] == 1:
        date_str = message.text.strip()
        try:
            day, month, year = map(int, date_str.split('/'))
            datetime(year, month, day)  # Kiểm tra ngày hợp lệ
            state['date'] = date_str
            # Menu chọn ca
            markup = InlineKeyboardMarkup()
            for ca in CA_CONFIG:
                markup.add(InlineKeyboardButton(ca, callback_data=ca))
            bot.reply_to(message, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['step'] = 2
        except:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy.")

# Handler nút chọn ca
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    if chat_id not in user_states or user_states[chat_id]['step'] != 2:
        return

    ca = call.data
    print(f"DEBUG: Callback selected ca: {ca} from {chat_id}")

    if ca not in CA_CONFIG:
        bot.answer_callback_query(call.id, "Ca không hợp lệ!")
        return

    state = user_states[chat_id]
    state['ca'] = ca
    config = CA_CONFIG[ca]

    bot.edit_message_text("Đang gửi báo cáo...", chat_id, call.message.message_id)

    # Parse ngày
    day, month, year = map(int, state['date'].split('/'))

    # Data submit form
    data = {
        'fvv': '1',
        'pageHistory': '0,1',
        'fbzx': '1',
        'submissionTimestamp': '-1',
        
        f'entry.{entry_ids["ho_ten"]}': HO_TEN,
        f'entry.{entry_ids["ngay_base"]}_year': str(year),
        f'entry.{entry_ids["ngay_base"]}_month': f'{month:02d}',
        f'entry.{entry_ids["ngay_base"]}_day': f'{day:02d}',
        f'entry.{entry_ids["ca_lam_viec"]}': ca,
        f'entry.{entry_ids["chuc_vu"]}': CHUC_VU,
        f'entry.{entry_ids["dia_diem"]}': DIA_DIEM,
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
                f"Thông tin: {HO_TEN} - {CHUC_VU} - {DIA_DIEM}\nChi tiết:\n{summary}",
                chat_id, call.message.message_id
            )
        else:
            bot.edit_message_text(f"❌ Lỗi gửi form (code {response.status_code})", chat_id, call.message.message_id)
    except Exception as e:
        print("ERROR submit form:", str(e))
        bot.edit_message_text(f"❌ Lỗi kết nối: {str(e)}", chat_id, call.message.message_id)

    del user_states[chat_id]
    bot.answer_callback_query(call.id)

# Webhook route với debug
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

# Health check cho Render
@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Flask server starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))