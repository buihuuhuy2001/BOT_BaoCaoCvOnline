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

# Config ca + giờ tối thiểu để submit
CA_CONFIG = {
    'Ca 1': {
        'tinh_hinh': 'Bình thường',
        'cong_viec_1': 'Hỗ trợ vận hành thu phí',
        'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc',
        'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác',
        'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 14  # Sau 14h
    },
    'Ca 2': {
        'tinh_hinh': 'Bình thường',
        'cong_viec_1': 'Hỗ trợ vận hành thu phí',
        'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc',
        'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác',
        'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 22  # Sau 22h
    },
    'Ca 3': {
        'tinh_hinh': 'Bình thường',
        'cong_viec_1': 'Hỗ trợ vận hành thu phí',
        'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc',
        'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác',
        'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 14  # Giả sử giống Ca 1, bạn có thể đổi
    },
    'Hành chính': {
        'tinh_hinh': 'Bình thường',
        'cong_viec_1': 'Xử lý các sự cố kỹ thuật phát sinh và những tình huống khẩn cấp',
        'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc',
        'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 17  # Sau 17h
    },
    'Nghỉ phép': {
        'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 8   # Sau 8h sáng
    },
    'Nghỉ bù - Nghỉ Chủ nhật': {
        'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 8
    },
    'Khác': {
        'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '',
        'min_hour': 8
    },
}

NAME_OPTIONS = ["Bùi Hữu Huy", "Trịnh Xuân Tân"]

USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trịnh Xuân Tân": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP Km102 - Cao tốc"}
}

# File lưu báo cáo đã submit thành công: { "name": { "dd/mm/yyyy": true } }
REPORTED_FILE = "reported.json"
try:
    with open(REPORTED_FILE, 'r', encoding='utf-8') as f:
        reported_data = json.load(f)
except FileNotFoundError:
    reported_data = {}

# File lưu các báo cáo đang chờ submit
PENDING_FILE = "pending_reports.json"
try:
    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
        pending_reports = json.load(f)
except FileNotFoundError:
    pending_reports = []  # Danh sách các dict báo cáo chờ

# Trạng thái người dùng (đang nhập liệu)
user_states = {}

# Scheduler
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

# --- Hàm hỗ trợ lưu / kiểm tra báo cáo ---
def has_reported(name, date_str):
    return reported_data.get(name, {}).get(date_str, False)

def mark_as_reported(name, date_str):
    if name not in reported_data:
        reported_data[name] = {}
    reported_data[name][date_str] = True
    with open(REPORTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(reported_data, f, ensure_ascii=False, indent=4)

def save_pending():
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(pending_reports, f, ensure_ascii=False, indent=4)

# --- Kiểm tra và submit các báo cáo chờ ---
def process_pending_reports():
    global pending_reports  # Đặt global ở ĐẦU hàm
    now = datetime.now()
    to_submit = []
    remaining = []

    for report in pending_reports:
        report_date = datetime.strptime(report['date'], "%d/%m/%Y")
        min_hour = CA_CONFIG[report['ca']]['min_hour']
        required_time = datetime.combine(report_date.date(), time(min_hour, 0))

        if now >= required_time:
            to_submit.append(report)
        else:
            remaining.append(report)

    # Submit những cái đủ điều kiện
    for report in to_submit:
        success = submit_to_form(report)
        if success:
            mark_as_reported(report['name'], report['date'])
            # Thông báo cho người dùng (nếu có chat_id)
            if 'chat_id' in report and 'message_id' in report:
                try:
                    summary = f"- Ca: {report['ca']}\n- Tình hình: {CA_CONFIG[report['ca']]['tinh_hinh']}"
                    bot.edit_message_text(
                        f"✅ Báo cáo ngày {report['date']}, ca {report['ca']} đã được gửi tự động lúc {now.strftime('%H:%M')}!\n"
                        f"Thông tin: {report['name']} - {USER_PROFILES[report['name']]['chuc_vu']}\nChi tiết:\n{summary}",
                        report['chat_id'], report['message_id']
                    )
                except Exception as e:
                    print("Lỗi thông báo pending submit:", e)

    # Cập nhật lại pending
    pending_reports = remaining
    save_pending()
def process_pending_reports():
    global pending_reports  # Đặt global ở ĐẦU hàm
    now = datetime.now()
    to_submit = []
    remaining = []

    for report in pending_reports:
        report_date = datetime.strptime(report['date'], "%d/%m/%Y")
        min_hour = CA_CONFIG[report['ca']]['min_hour']
        required_time = datetime.combine(report_date.date(), time(min_hour, 0))

        if now >= required_time:
            to_submit.append(report)
        else:
            remaining.append(report)

    # Submit những cái đủ điều kiện
    for report in to_submit:
        success = submit_to_form(report)
        if success:
            mark_as_reported(report['name'], report['date'])
            # Thông báo cho người dùng (nếu có chat_id)
            if 'chat_id' in report and 'message_id' in report:
                try:
                    summary = f"- Ca: {report['ca']}\n- Tình hình: {CA_CONFIG[report['ca']]['tinh_hinh']}"
                    bot.edit_message_text(
                        f"✅ Báo cáo ngày {report['date']}, ca {report['ca']} đã được gửi tự động lúc {now.strftime('%H:%M')}!\n"
                        f"Thông tin: {report['name']} - {USER_PROFILES[report['name']]['chuc_vu']}\nChi tiết:\n{summary}",
                        report['chat_id'], report['message_id']
                    )
                except Exception as e:
                    print("Lỗi thông báo pending submit:", e)

    # Cập nhật lại pending
    pending_reports = remaining
    save_pending()
def submit_to_form(report):
    config = CA_CONFIG[report['ca']]
    user_info = USER_PROFILES[report['name']]
    day, month, year = map(int, report['date'].split('/'))

    data = {
        'fvv': '1', 'pageHistory': '0,1', 'fbzx': '1', 'submissionTimestamp': '-1',
        f'entry.{entry_ids["ho_ten"]}': report['name'],
        f'entry.{entry_ids["ngay_base"]}_year': str(year),
        f'entry.{entry_ids["ngay_base"]}_month': f'{month:02d}',
        f'entry.{entry_ids["ngay_base"]}_day': f'{day:02d}',
        f'entry.{entry_ids["ca_lam_viec"]}': report['ca'],
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
        print(f"Pending submit {report['name']} {report['date']} {report['ca']} -> {response.status_code}")
        return response.status_code in (200, 302)
    except Exception as e:
        print("Error submitting pending:", e)
        return False

# Scheduler jobs
scheduler.add_job(process_pending_reports, IntervalTrigger(minutes=5))
scheduler.add_job(process_pending_reports, CronTrigger(hour=8, minute=1))  # Chắc chắn chạy lúc 8h01
scheduler.add_job(process_pending_reports, CronTrigger(hour=14, minute=1))
scheduler.add_job(process_pending_reports, CronTrigger(hour=17, minute=1))
scheduler.add_job(process_pending_reports, CronTrigger(hour=22, minute=1))

# Nhắc nhở & thống kê (dùng reported_data để kiểm tra hôm nay)
def send_reminders():
    now = datetime.now()
    today = now.strftime("%d/%m/%Y")
    if not (8 <= now.hour <= 22 and now.minute < 5):
        return

    known_chat_ids = set()
    for name in reported_data:
        for date_str in reported_data[name]:
            # Giả sử chat_id được lưu tạm ở đâu đó, hoặc bỏ qua nếu không cần nhắc chính xác
            pass  # Hiện tại không có chat_id lưu theo tên → tạm bỏ nhắc theo người cụ thể

    # Bạn có thể thêm danh sách chat_id thủ công nếu cần
    # Hoặc để trống nếu không cần nhắc nữa

def daily_stats():
    today = datetime.now().strftime("%d/%m/%Y")
    stats = []
    for name in NAME_OPTIONS:
        status = "Đã báo cáo" if has_reported(name, today) else "Chưa báo cáo"
        stats.append(f"- {name}: {status}")
    message = f"Thống kê hôm nay ({today}):\n" + "\n".join(stats) + "\nAi chưa làm thì gửi /report nhé!"

    # Gửi cho các chat_id từng báo (nếu bạn lưu thêm chat_id thì tốt hơn)
    # Hiện tại bỏ qua để tránh lỗi

scheduler.add_job(send_reminders, IntervalTrigger(minutes=5))
scheduler.add_job(daily_stats, CronTrigger(hour=22, minute=0))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# --- Handler ---
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
        chat_id, call.message.message_id
    )

    user_states[chat_id] = {
        'step': 1,
        'date': '',
        'ca': '',
        'name': selected_name,
        'message_id': call.message.message_id,
        'chat_id': chat_id
    }
    bot.answer_callback_query(call.id)

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
            markup = InlineKeyboardMarkup(row_width=2)
            for ca in CA_CONFIG:
                markup.add(InlineKeyboardButton(ca, callback_data=ca))
            bot.send_message(chat_id, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['step'] = 2
        except:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    state = user_states.get(chat_id)

    # Xử lý xác nhận ghi đè
    if state and state.get('step') == 'confirm_overwrite':
        if call.data == 'yes_overwrite':
            schedule_report(chat_id, state, overwrite=True)
        else:
            bot.edit_message_text("Đã hủy báo cáo lại. Gửi /report để báo cáo mới nhé! 😊", chat_id, state['message_id'])
            del user_states[chat_id]
        bot.answer_callback_query(call.id)
        return

    if not state or state.get('step') != 2:
        return

    ca = call.data
    if ca not in CA_CONFIG:
        bot.answer_callback_query(call.id, "Ca không hợp lệ!")
        return

    state['ca'] = ca

    # Kiểm tra trùng tên + ngày
    if has_reported(state['name'], state['date']):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Có, báo lại (ghi đè)", callback_data='yes_overwrite'),
            InlineKeyboardButton("❌ Không, hủy", callback_data='no_overwrite')
        )
        config = CA_CONFIG[ca]
        bot.edit_message_text(
            f"⚠️ {state['name']} đã báo cáo ngày {state['date']} rồi!\n"
            f"Nếu tiếp tục, dữ liệu cũ sẽ bị ghi đè.\n\n"
            f"Ca mới: {ca}\nTình hình: {config['tinh_hinh']}\n\n"
            f"Bạn có chắc muốn báo lại không?",
            chat_id, state['message_id'], reply_markup=markup
        )
        state['step'] = 'confirm_overwrite'
        bot.answer_callback_query(call.id)
        return

    # Không trùng → lên lịch submit
    schedule_report(chat_id, state, overwrite=False)
    bot.answer_callback_query(call.id)

def schedule_report(chat_id, state, overwrite=False):
    report_date = datetime.strptime(state['date'], "%d/%m/%Y")
    min_hour = CA_CONFIG[state['ca']]['min_hour']
    required_time = datetime.combine(report_date.date(), time(min_hour, 0))
    now = datetime.now()

    report_data = {
        'name': state['name'],
        'date': state['date'],
        'ca': state['ca'],
        'chat_id': chat_id,
        'message_id': state['message_id']
    }

    if now >= required_time:
        # Gửi ngay
        bot.edit_message_text("Đang gửi báo cáo...", chat_id, state['message_id'])
        success = submit_to_form(report_data)
        if success:
            mark_as_reported(state['name'], state['date'])
            summary = f"- Ca: {state['ca']}\n- Tình hình: {CA_CONFIG[state['ca']]['tinh_hinh']}"
            note = "\n*(Đã ghi đè báo cáo cũ)*" if overwrite else ""
            bot.edit_message_text(
                f"✅ Báo cáo ngày {state['date']}, ca {state['ca']} gửi thành công!{note}\n"
                f"Thông tin: {state['name']} - {USER_PROFILES[state['name']]['chuc_vu']}\nChi tiết:\n{summary}",
                chat_id, state['message_id']
            )
        else:
            bot.edit_message_text("❌ Lỗi khi gửi báo cáo. Vui lòng thử lại sau.", chat_id, state['message_id'])
    else:
        # Lưu chờ
        pending_reports.append(report_data)
        save_pending()
        hour_str = f"{min_hour:02d}:00"
        date_str = state['date']
        bot.edit_message_text(
            f"✅ Đã nhận báo cáo {state['ca']} ngày {date_str}.\n"
            f"Báo cáo sẽ được tự động gửi sau {hour_str} ngày {date_str} nhé! ⏰",
            chat_id, state['message_id']
        )

    del user_states[chat_id]

# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            update = Update.de_json(request.get_json())
            bot.process_new_updates([update])
        except Exception as e:
            print("Webhook error:", e)
    return '', 200

@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Bot starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))