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

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

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
    'Ca 1': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 14},
    'Ca 2': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 22},
    'Ca 3': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Hỗ trợ vận hành thu phí', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': 'Hoàn thành các nhiệm vụ được giao khác', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 14},
    'Hành chính': {'tinh_hinh': 'Bình thường', 'cong_viec_1': 'Xử lý các sự cố kỹ thuật phát sinh và những tình huống khẩn cấp', 'cong_viec_2': 'Bảo trì , bảo dưỡng thiết bị máy móc', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 17},
    'Nghỉ phép': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
    'Nghỉ bù - Nghỉ Chủ nhật': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
    'Khác': {'tinh_hinh': 'Khác', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
}

NAME_OPTIONS = ["Bùi Hữu Huy", "Trịnh Xuân Tân"]

USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trịnh Xuân Tân": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP Km102 - Cao tốc"}
}

REPORTED_FILE = "reported.json"
try:
    with open(REPORTED_FILE, 'r', encoding='utf-8') as f:
        reported_data = json.load(f)
except FileNotFoundError:
    reported_data = {}

PENDING_FILE = "pending_reports.json"
try:
    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
        pending_reports = json.load(f)
except FileNotFoundError:
    pending_reports = []

user_states = {}

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

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
        print(f"Submit {report['name']} {report['date']} {report['ca']} -> {response.status_code}")
        return response.status_code in (200, 302)
    except Exception as e:
        print("Error submitting:", e)
        return False

def process_pending_reports():
    global pending_reports
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

    for report in to_submit:
        success = submit_to_form(report)
        if success:
            mark_as_reported(report['name'], report['date'])
            if 'chat_id' in report and 'message_id' in report:
                try:
                    bot.edit_message_text(
                        f"✅ Báo cáo ngày {report['date']}, ca {report['ca']} đã được gửi tự động lúc {now.strftime('%H:%M')}!\n"
                        f"Thông tin: {report['name']} - {USER_PROFILES[report['name']]['chuc_vu']} - {USER_PROFILES[report['name']]['dia_diem']}\n"
                        f"- Ca: {report['ca']}\n- Tình hình: {CA_CONFIG[report['ca']]['tinh_hinh']}",
                        report['chat_id'], report['message_id']
                    )
                except Exception as e:
                    print("Lỗi thông báo pending:", e)

    pending_reports = remaining
    save_pending()

scheduler.add_job(process_pending_reports, IntervalTrigger(minutes=5))
scheduler.add_job(process_pending_reports, CronTrigger(hour='8,14,17,22', minute=1))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

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

            sent_msg = bot.send_message(chat_id, "Bước 2: Chọn ca làm việc:", reply_markup=markup)
            state['message_id'] = sent_msg.message_id
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

    # Kiểm tra đã báo ngày này chưa
    if has_reported(state['name'], state['date']):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Có, báo lại (ghi đè)", callback_data='yes_overwrite'),
            InlineKeyboardButton("❌ Không, hủy", callback_data='no_overwrite')
        )
        config = CA_CONFIG[ca]
        bot.edit_message_text(
            f"⚠️ {state['name']} đã báo cáo ngày {state['date']} rồi!\n"
            f"(Có thể đang chờ gửi hoặc đã gửi)\n\n"
            f"Nếu tiếp tục, báo cáo cũ sẽ bị ghi đè.\n\n"
            f"Ca mới: {ca}\n"
            f"Tình hình: {config['tinh_hinh']}\n\n"
            f"Bạn có chắc muốn báo lại không?",
            chat_id, state['message_id'], reply_markup=markup
        )
        state['step'] = 'confirm_overwrite'
        bot.answer_callback_query(call.id)
        return

    # Không trùng → xử lý bình thường
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

    # Đánh dấu đã báo ngay lập tức
    mark_as_reported(state['name'], state['date'])

    if now >= required_time:
        bot.edit_message_text("Đang gửi báo cáo...", chat_id, state['message_id'])
        success = submit_to_form(report_data)
        if success:
            summary = f"- Ca: {state['ca']}\n- Tình hình: {CA_CONFIG[state['ca']]['tinh_hinh']}"
            note = "\n*(Đã ghi đè báo cáo cũ)*" if overwrite else ""
            bot.edit_message_text(
                f"✅ Báo cáo ngày {state['date']}, ca {state['ca']} gửi thành công!{note}\n"
                f"Thông tin: {state['name']} - {USER_PROFILES[state['name']]['chuc_vu']} - {USER_PROFILES[state['name']]['dia_diem']}\nChi tiết:\n{summary}",
                chat_id, state['message_id']
            )
        else:
            bot.edit_message_text("❌ Lỗi gửi form. Vui lòng thử lại sau.", chat_id, state['message_id'])
    else:
        global pending_reports
        # Xóa báo cũ nếu đang ghi đè
        pending_reports = [r for r in pending_reports if not (r['name'] == state['name'] and r['date'] == state['date'])]
        pending_reports.append(report_data)
        save_pending()

        hour_str = f"{min_hour:02d}:00"
        note = " (đã ghi đè báo cáo cũ)" if overwrite else ""
        bot.edit_message_text(
            f"✅ Đã nhận báo cáo {state['ca']} ngày {state['date']}{note}.\n"
            f"Báo cáo sẽ tự động gửi sau {hour_str} ngày {state['date']} nhé! ⏰",
            chat_id, state['message_id']
        )

    del user_states[chat_id]

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