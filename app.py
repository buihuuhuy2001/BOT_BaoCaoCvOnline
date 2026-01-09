import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime
import json
from flask import Flask, request, abort

app = Flask(__name__)

# Thay bằng token bot thật của bạn
BOT_TOKEN = '8527505483:AAFGovkQFLNv74Shmxzr7ghmKgkv2ayEd0I'
bot = telebot.TeleBot(BOT_TOKEN)

# Entry IDs (giữ nguyên)
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

# URL submit form
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScjsFj9xeDHd6T7BwPCt5XzfCGKNhwuh3BxtSfCOADwBhao6w/formResponse"

# Config logic (giữ nguyên)
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

user_states = {}  # {'step': 1, 'date': '', 'ca': ''}

@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    bot.reply_to(message, "Chào Bùi Hữu Huy! Bắt đầu báo cáo công việc.\nBước 1: Nhập ngày (dd/mm/yyyy, ví dụ: 09/01/2026):")
    user_states[message.chat.id] = {'step': 1, 'date': '', 'ca': ''}

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
            for ca in CA_CONFIG.keys():
                markup.row(InlineKeyboardButton(ca, callback_data=ca))
            bot.reply_to(message, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['step'] = 2
        except ValueError:
            bot.reply_to(message, "Định dạng ngày sai! Nhập lại theo dd/mm/yyyy.")

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
    
    bot.edit_message_text("Đang gửi báo cáo...", chat_id, call.message.message_id)
    
    day, month, year = map(int, state['date'].split('/'))
    
    # Data single submit for multi-page
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
        if response.status_code in [200, 302]:
            summary = f"- Tình hình ca: {config['tinh_hinh']}\n- Công việc 1: {config['cong_viec_1']}\n- Công việc 2: {config['cong_viec_2']}\n- Công việc 3: {config['cong_viec_3']}"
            bot.edit_message_text(f"✅ Báo cáo ngày {state['date']}, ca {ca} đã gửi thành công!\nThông tin mặc định: Họ tên {HO_TEN}, Chức vụ {CHUC_VU}, Địa điểm {DIA_DIEM}\nChi tiết:\n{summary}", chat_id, call.message.message_id)
            print(f"Báo cáo ngày {state['date']}, ca {ca} đã gửi thành công")
        else:
            bot.edit_message_text(f"❌ Lỗi gửi form (status {response.status_code}). Kiểm tra console!", chat_id, call.message.message_id)
            print(f"Lỗi gửi báo cáo ngày {state['date']}, ca {ca} (status {response.status_code})")
    except Exception as e:
        bot.edit_message_text(f"❌ Lỗi kết nối: {str(e)}", chat_id, call.message.message_id)
        print(f"Lỗi kết nối báo cáo ngày {state['date']}, ca {ca}: {str(e)}")
    
    del user_states[chat_id]
    bot.answer_callback_query(call.id)

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

if __name__ == '__main__':
    # Set webhook (cập nhật URL sau deploy)
    bot.remove_webhook()
    bot.set_webhook(url='YOUR_WEBHOOK_URL')  # Ví dụ: https://yourapp.onrender.com/webhook
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))