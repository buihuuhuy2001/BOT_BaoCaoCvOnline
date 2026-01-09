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

# File lưu trạng thái đã báo cáo: { "chat_id": { "dd/mm/yyyy": true } }
REPORTED_FILE = "reported.json"

try:
    with open(REPORTED_FILE, 'r', encoding='utf-8') as f:
        reported_dates = json.load(f)
except FileNotFoundError:
    reported_dates = {}

def save_reported(chat_id, date_str):
    chat_id_str = str(chat_id)
    if chat_id_str not in reported_dates:
        reported_dates[chat_id_str] = {}
    reported_dates[chat_id_str][date_str] = True
    with open(REPORTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(reported_dates, f, ensure_ascii=False, indent=4)
    print(f"Đã lưu báo cáo cho {chat_id} ngày {date_str}")

def has_reported_date(chat_id, date_str):
    chat_id_str = str(chat_id)
    return reported_dates.get(chat_id_str, {}).get(date_str, False)

# Trạng thái người dùng
user_states = {}

# Scheduler
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

def send_reminders():
    now = datetime.now()
    today = now.strftime("%d/%m/%Y")
    
    for chat_id_str in list(reported_dates.keys()):
        chat_id = int(chat_id_str)
        if has_reported_date(chat_id, today):
            continue  # Đã báo hôm nay rồi → không nhắc
        if 8 <= now.hour <= 22 and now.minute < 5:
            try:
                bot.send_message(chat_id, "Chào bạn! Hôm nay bạn chưa báo cáo ca làm việc. Gửi /report để báo cáo nhé! 😊")
            except Exception as e:
                print("Lỗi gửi nhắc nhở:", str(e))

def daily_stats():
    today = datetime.now().strftime("%d/%m/%Y")
    stats = []
    for name in NAME_OPTIONS:
        # Tìm xem có chat_id nào của tên này đã báo hôm nay chưa (giản lược, chỉ để thông báo chung)
        status = "Chưa báo cáo"
        for dates in reported_dates.values():
            if dates.get(today):
                status = "Đã báo cáo"  # Nếu có ai báo hôm nay thì tạm đánh dấu (có thể cải thiện sau)
                break
        stats.append(f"- {name}: {status}")
    message = f"Thống kê hôm nay ({today}):\n" + "\n".join(stats) + "\nAi chưa làm thì gửi /report nhé!"
    
    for chat_id_str in list(reported_dates.keys()):
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
    
    bot.edit_message_text(
        f"Đã chọn: {selected_name}\nBắt đầu báo cáo công việc.\nBước 1: Nhập ngày (dd/mm/yyyy, ví dụ: {datetime.now().strftime('%d/%m/%Y')}):",
        call.message.chat.id, call.message.message_id
    )
    
    user_states[chat_id] = {
        'step': 1,
        'date': '',
        'ca': '',
        'selected_name': selected_name,
        'message_id': call.message.message_id  # Lưu message_id để edit sau
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
            datetime(year, month, day)  # Validate ngày hợp lệ
            state['date'] = date_str
            markup = InlineKeyboardMarkup(row_width=2)
            for ca in CA_CONFIG:
                markup.add(InlineKeyboardButton(ca, callback_data=ca))
            bot.send_message(chat_id, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['step'] = 2
        except:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy (ví dụ: 09/01/2026).")

# Hàm thực hiện submit form (tách riêng để dùng lại khi xác nhận báo lại)
def perform_submit(chat_id, state):
    config = CA_CONFIG[state['ca']]
    selected_name = state['selected_name']
    user_info = USER_PROFILES[selected_name]
    
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
        f'entry.{entry_ids["ca_lam_viec"]}': state['ca'],
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
            summary = f"- Tình hình: {config['tinh_hinh']}\n- CV1: {config['cong_viec_1'] or 'Trống'}\n- CV2: {config['cong_viec_2'] or 'Trống'}\n- CV3: {config['cong_viec_3'] or 'Trống'}"
            overwrite_note = "\n*(Đã ghi đè báo cáo cũ)*" if has_reported_date(chat_id, state['date']) else ""
            bot.edit_message_text(
                f"✅ Báo cáo ngày {state['date']}, ca {state['ca']} gửi thành công!{overwrite_note}\n"
                f"Thông tin: {selected_name} - {user_info['chuc_vu']} - {user_info['dia_diem']}\nChi tiết:\n{summary}",
                chat_id, state['message_id']
            )
            save_reported(chat_id, state['date'])
        else:
            bot.edit_message_text(f"❌ Lỗi gửi form (code {response.status_code})", chat_id, state['message_id'])
    except Exception as e:
        print("ERROR submit form:", str(e))
        bot.edit_message_text(f"❌ Lỗi kết nối: {str(e)}", chat_id, state['message_id'])
    
    # Kết thúc flow
    if chat_id in user_states:
        del user_states[chat_id]

# Handler callback (chọn ca + xác nhận báo lại)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    state = user_states.get(chat_id)

    # Xử lý nút xác nhận báo lại
    if state and state.get('step') == 'confirm_overwrite':
        if call.data == 'yes_overwrite':
            bot.edit_message_text("Đang gửi báo cáo lại (ghi đè)...", chat_id, state['message_id'])
            perform_submit(chat_id, state)
        else:
            bot.edit_message_text("Đã hủy báo cáo lại. Gửi /report để báo cáo ngày khác nhé! 😊", chat_id, state['message_id'])
            if chat_id in user_states:
                del user_states[chat_id]
        bot.answer_callback_query(call.id)
        return

    # Xử lý chọn ca bình thường
    if not state or state.get('step') != 2:
        return
    
    ca = call.data
    if ca not in CA_CONFIG:
        bot.answer_callback_query(call.id, "Ca không hợp lệ!")
        return
    
    state['ca'] = ca

    # Kiểm tra đã báo ngày này chưa
    if has_reported_date(chat_id, state['date']):
        # ĐÃ BÁO → HỎI XÁC NHẬN
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Có, báo lại", callback_data='yes_overwrite'),
            InlineKeyboardButton("❌ Không, hủy", callback_data='no_overwrite')
        )
        config = CA_CONFIG[ca]
        summary = f"- Ca: {ca}\n- Tình hình: {config['tinh_hinh']}\n- CV1: {config['cong_viec_1'] or 'Trống'}"
        bot.edit_message_text(
            f"⚠️ Bạn đã báo cáo ngày {state['date']} rồi!\n"
            f"Dữ liệu cũ sẽ bị ghi đè nếu tiếp tục.\n\n"
            f"Xem trước nội dung mới:\n{summary}\n\n"
            f"Bạn có chắc chắn muốn báo lại không?",
            chat_id, state['message_id'], reply_markup=markup
        )
        state['step'] = 'confirm_overwrite'
        bot.answer_callback_query(call.id)
        return

    # CHƯA BÁO → submit ngay
    bot.edit_message_text("Đang gửi báo cáo...", chat_id, state['message_id'])
    perform_submit(chat_id, state)
    bot.answer_callback_query(call.id)

# Webhook và health
@app.route('/webhook', methods=['POST'])
def webhook():
    print("=== DEBUG: NEW WEBHOOK REQUEST ===")
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update_dict = json.loads(json_string)
            update = Update.de_json(update_dict)
            if update:
                bot.process_new_updates([update])
        except Exception as e:
            print("ERROR in webhook:", str(e))
    return '', 200

@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Flask server starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))