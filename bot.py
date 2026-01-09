import os
import telebot
from flask import Flask, request, abort
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime, time, timedelta
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

app = Flask(__name__)

# Token từ env
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Entry IDs, FORM_URL, CA_CONFIG giữ nguyên như cũ của bạn (copy từ file cũ)
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

CA_CONFIG = {
    'Ca 1': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 2': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Ca 3': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Hành chính': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Xử lý các sự cố kỹ thuật phát sinh và những tình huống khẩn cấp', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ phép': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Nghỉ bù - Nghỉ Chủ nhật': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
    'Khác': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': ''},
}

# Danh sách tên cố định (2 option)
NAME_OPTIONS = ["Bùi Hữu Huy", "Trịnh Xuân Tân"]

# Thông tin chức vụ & địa điểm theo tên
USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trịnh Xuân Tân": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP Km102 - Cao tốc"}  # chỉnh lại nếu khác
}

# File lưu trạng thái đã báo cáo hôm nay (per user)
REPORTED_FILE = "reported.json"

# Load reported status
try:
    with open(REPORTED_FILE, 'r', encoding='utf-8') as f:
        reported_today = json.load(f)
except FileNotFoundError:
    reported_today = {}

# Lưu trạng thái báo cáo trong ngày (chat_id -> date)
def save_reported(chat_id, date_str):
    reported_today[str(chat_id)] = date_str
    with open(REPORTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(reported_today, f, ensure_ascii=False, indent=4)

def has_reported_today(chat_id):
    today = datetime.now().strftime("%d/%m/%Y")
    return reported_today.get(str(chat_id)) == today

# Lưu trạng thái người dùng
user_states = {}

# Scheduler cho nhắc nhở
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

def send_reminders():
    now = datetime.now()
    current_time = now.time()
    today = now.strftime("%d/%m/%Y")
    
    for chat_id_str, data in reported_today.items():
        chat_id = int(chat_id_str)
        if data != today:  # Ngày mới, reset
            continue
        
        # Nếu đã báo cáo hôm nay → bỏ qua
        if has_reported_today(chat_id):
            continue
        
        # Nhắc từ 8h sáng mỗi 1 tiếng
        if current_time.hour >= 8 and current_time.minute < 5:  # kiểm tra mỗi giờ
            try:
                bot.send_message(chat_id, "Chào bạn! Hôm nay bạn chưa báo cáo ca làm việc. Gửi /report để báo cáo nhé! 😊")
            except:
                pass

scheduler.add_job(send_reminders, IntervalTrigger(minutes=5))  # kiểm tra mỗi 5 phút
scheduler.start()

# Tắt scheduler khi app shutdown
atexit.register(lambda: scheduler.shutdown())

# Handler chọn tên khi /report
@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(name, callback_data=f"name_{name}"))
    bot.reply_to(message, "Chọn tên của bạn để bắt đầu báo cáo:", reply_markup=markup)

# Callback chọn tên
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

# Các handler còn lại giữ nguyên như cũ (handle_message, handle_callback, webhook, health)
# (copy phần còn lại từ file cũ của bạn vào đây, chỉ thay HO_TEN, CHUC_VU, DIA_DIEM bằng lấy từ selected_name)

# Trong handle_callback, khi submit thành công, thêm dòng này:
# save_reported(chat_id, state['date'])  # đánh dấu đã báo cáo ngày đó

# Ví dụ (thêm vào cuối try nếu success):
save_reported(chat_id, state['date'])

if __name__ == '__main__':
    print("Flask server starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))