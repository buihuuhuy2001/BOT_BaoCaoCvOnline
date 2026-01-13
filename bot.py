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

# Debug múi giờ khởi động
print("=== DEBUG MÚI GIỜ KHI BOT KHỞI ĐỘNG ===")
print("Server local time (UTC):", datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
print("Timezone name:", time.tzname)
print("VN time (ZoneInfo):", datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d %H:%M:%S"))
print("Current VN hour:", datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).hour)
print("=======================================")

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# Tự động set webhook khi bot khởi động
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"[WEBHOOK SUCCESS] Webhook đã set: {WEBHOOK_URL}")
except Exception as e:
    print(f"[WEBHOOK ERROR] Lỗi set webhook: {str(e)}")

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

NAME_OPTIONS = ["Bùi Hữu Huy", "Trần Văn Quang"]

USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trần Văn Quang": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP TL242 - Cao tốc"}
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
known_chat_ids = set()

vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")

scheduler = BackgroundScheduler(timezone=vn_tz)

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
    now = datetime.now(vn_tz)
    to_submit = []
    remaining = []
    for report in pending_reports:
        report_date_obj = datetime.strptime(report['date'], "%d/%m/%Y")
        report_date = report_date_obj.date()
        min_hour = CA_CONFIG[report['ca']]['min_hour']
        required_datetime = vn_tz.localize(datetime.combine(report_date, time(min_hour, 1)))
        if now >= required_datetime:
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

def send_hourly_reminder():
    now = datetime.now(vn_tz)
    print(f"[REMINDER] Gọi nhắc nhở lúc {now.strftime('%H:%M')} VN")
    if not (8 <= now.hour <= 22):
        return
    today = now.strftime("%d/%m/%Y")
    unreported = [name for name in NAME_OPTIONS if not has_reported(name, today)]
    if unreported:
        message = f"Hôm nay ({today}) vẫn còn người chưa báo cáo ca: {', '.join(unreported)}. Ai chưa thì gửi /report nhé! 😊"
        for chat_id in known_chat_ids:
            try:
                bot.send_message(chat_id, message)
                print(f"[REMINDER] Đã gửi đến chat {chat_id}")
            except Exception as e:
                print(f"Lỗi gửi nhắc: {e}")

def report_all_status(chat_id):
    today = datetime.now(vn_tz).strftime("%d/%m/%Y")
    status_lines = [f"Tình hình báo cáo hôm nay ({today}):"]
    for name in NAME_OPTIONS:
        if has_reported(name, today):
            status_lines.append(f"- {name}: Đã báo hôm nay")
        else:
            pending_for_name = [r for r in pending_reports if r['date'] == today and r['name'] == name]
            if pending_for_name:
                for p in pending_for_name:
                    min_hour = CA_CONFIG[p['ca']]['min_hour']
                    status_lines.append(f"- {name}: Đang chờ gửi Ca {p['ca']} (sau {min_hour:02d}:01)")
            else:
                status_lines.append(f"- {name}: Chưa báo hôm nay")
    if len(status_lines) == 1:
        status_lines.append("Tất cả đã báo hôm nay! Tuyệt vời! 🎉")
    bot.send_message(chat_id, "\n".join(status_lines))
    print(f"[REPORTALL] Gửi trạng thái cho chat {chat_id}")

# Scheduler jobs - bù trừ vì server UTC
scheduler.add_job(process_pending_reports, IntervalTrigger(minutes=5), timezone=vn_tz)
scheduler.add_job(process_pending_reports, CronTrigger(hour='1,7,10,15', minute=1), timezone=vn_tz)  # 8,14,17,22 VN
scheduler.add_job(send_hourly_reminder, CronTrigger(hour='1-15', minute=0), timezone=vn_tz)  # 8-22 VN

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# --- Handlers ---

@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(name, callback_data=f"name_{name}"))
    bot.reply_to(message, "Chọn tên của bạn để bắt đầu báo cáo:", reply_markup=markup)

@bot.message_handler(commands=['reportall'])
def handle_reportall(message):
    report_all_status(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('name_'))
def handle_name_callback(call):
    print(f"[CALLBACK] Chọn tên: {call.data}")
    bot.answer_callback_query(call.id)  # Dừng loading ngay
    chat_id = call.message.chat.id
    selected_name = call.data.replace('name_', '')
    if selected_name not in NAME_OPTIONS:
        bot.answer_callback_query(call.id, "Tên không hợp lệ!")
        return
    bot.edit_message_text(
        f"Đã chọn: {selected_name}\nChọn loại ngày báo cáo:",
        chat_id, call.message.message_id
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("Ngày hiện tại", callback_data="date_today"))
    markup.add(InlineKeyboardButton("Tự chọn ngày khác", callback_data="date_custom"))
    sent_msg = bot.send_message(chat_id, "Chọn ngày báo cáo:", reply_markup=markup)
    user_states[chat_id] = {
        'step': 'choose_date_type',
        'name': selected_name,
        'message_id': sent_msg.message_id,
        'chat_id': chat_id
    }
    known_chat_ids.add(chat_id)

@bot.callback_query_handler(func=lambda call: call.data in ["date_today", "date_custom"])
def handle_date_type(call):
    print(f"[CALLBACK] Chọn loại ngày: {call.data}")
    bot.answer_callback_query(call.id)  # Dừng loading
    chat_id = call.message.chat.id
    state = user_states.get(chat_id)
    if not state or state.get('step') != 'choose_date_type':
        return
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
    if call.data == "date_today":
        today = datetime.now(vn_tz).strftime("%d/%m/%Y")
        state['date'] = today
        state['step'] = 2
        markup = InlineKeyboardMarkup(row_width=2)
        for ca in CA_CONFIG:
            markup.add(InlineKeyboardButton(ca, callback_data=ca))
        sent_msg = bot.send_message(chat_id, f"Ngày báo cáo: {today} (hôm nay)\nChọn ca làm việc:", reply_markup=markup)
        state['message_id'] = sent_msg.message_id
    else:
        state['step'] = 1
        bot.send_message(chat_id, "Nhập ngày báo cáo (dd/mm/yyyy, ví dụ: 09/01/2026):")

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
            state['step'] = 2
            markup = InlineKeyboardMarkup(row_width=2)
            for ca in CA_CONFIG:
                markup.add(InlineKeyboardButton(ca, callback_data=ca))
            sent_msg = bot.send_message(chat_id, f"Ngày báo cáo: {date_str}\nChọn ca làm việc:", reply_markup=markup)
            state['message_id'] = sent_msg.message_id
        except:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    print(f"[CALLBACK DEBUG] Nhận callback: data={call.data} | chat_id={call.message.chat.id}")
    bot.answer_callback_query(call.id)  # Dừng loading ngay lập tức

    chat_id = call.message.chat.id
    state = user_states.get(chat_id)
    if state and state.get('step') == 'confirm_overwrite':
        if call.data == 'yes_overwrite':
            schedule_report(chat_id, state, overwrite=True)
        else:
            bot.edit_message_text("Đã hủy báo cáo lại. Gửi /report để thử lại nhé! 😊", chat_id, state['message_id'])
            del user_states[chat_id]
        return

    if not state or state.get('step') != 2:
        print("[DEBUG] State không hợp lệ hoặc step không phải 2")
        return

    ca = call.data
    if ca not in CA_CONFIG:
        bot.answer_callback_query(call.id, "Ca không hợp lệ!")
        return

    state['ca'] = ca
    known_chat_ids.add(chat_id)

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
        return

    schedule_report(chat_id, state, overwrite=False)

def schedule_report(chat_id, state, overwrite=False):
    report_date_obj = datetime.strptime(state['date'], "%d/%m/%Y")
    report_date = report_date_obj.date()
    min_hour = CA_CONFIG[state['ca']]['min_hour']
    required_datetime = vn_tz.localize(datetime.combine(report_date, time(min_hour, 1)))
    now = datetime.now(vn_tz)
    report_data = {
        'name': state['name'],
        'date': state['date'],
        'ca': state['ca'],
        'chat_id': chat_id,
        'message_id': state['message_id']
    }
    mark_as_reported(state['name'], state['date'])
    print(f"[SCHEDULE] Lên lịch cho {state['name']}, ca {state['ca']}, ngày {state['date']}, required {required_datetime}")
    if now >= required_datetime:
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
        pending_reports = [r for r in pending_reports if not (r['name'] == state['name'] and r['date'] == state['date'])]
        pending_reports.append(report_data)
        save_pending()
        hour_str = f"{min_hour:02d}:01"
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
        json_string = request.get_data().decode('utf-8')
        try:
            update = Update.de_json(json_string)
            if update:
                print(f"[WEBHOOK] Nhận update: update_id={update.update_id}")
                bot.process_new_updates([update])
                return '', 200
            else:
                print("[WEBHOOK] Không parse được update")
                return 'Invalid update', 400
        except Exception as e:
            print(f"[WEBHOOK ERROR] {e}")
            return 'Error', 500
    print("[WEBHOOK] Request không phải JSON")
    return 'Not JSON', 403

@app.route('/')
def health():
    return "Bot is alive!", 200

if __name__ == '__main__':
    print("Bot starting...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))