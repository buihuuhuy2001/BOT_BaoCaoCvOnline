import os
import calendar
import telebot
from flask import Flask, request
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime, time, timedelta
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
import atexit

app = Flask(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"

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
    'Ca 1': {'tinh_hinh': 'Binh thuong', 'cong_viec_1': 'Ho tro van hanh thu phi', 'cong_viec_2': 'Bao tri , bao duong thiet bi may moc', 'cong_viec_3': 'Hoan thanh cac nhiem vu duoc giao khac', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 14},
    'Ca 2': {'tinh_hinh': 'Binh thuong', 'cong_viec_1': 'Ho tro van hanh thu phi', 'cong_viec_2': 'Bao tri , bao duong thiet bi may moc', 'cong_viec_3': 'Hoan thanh cac nhiem vu duoc giao khac', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 22},
    'Ca 3': {'tinh_hinh': 'Binh thuong', 'cong_viec_1': 'Ho tro van hanh thu phi', 'cong_viec_2': 'Bao tri , bao duong thiet bi may moc', 'cong_viec_3': 'Hoan thanh cac nhiem vu duoc giao khac', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 14},
    'Hành chính': {'tinh_hinh': 'Binh thuong', 'cong_viec_1': 'Xu ly cac su co ky thuat phat sinh va nhung tinh huong khan cap', 'cong_viec_2': 'Bao tri , bao duong thiet bi may moc', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 17},
    'Nghỉ phép': {'tinh_hinh': 'Khac', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
    'Nghỉ bù - Nghỉ Chủ nhật': {'tinh_hinh': 'Khac', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
    'Khác': {'tinh_hinh': 'Khac', 'cong_viec_1': '', 'cong_viec_2': '', 'cong_viec_3': '', 'cong_viec_4': '', 'cong_viec_5': '', 'min_hour': 8},
}

# Tên hiển thị cho CA_CONFIG keys (giữ tiếng Việt để gửi form)
CA_DISPLAY = {
    'Ca 1': 'Ca 1',
    'Ca 2': 'Ca 2',
    'Ca 3': 'Ca 3',
    'Hành chính': 'Hành chính',
    'Nghỉ phép': 'Nghỉ phép',
    'Nghỉ bù - Nghỉ Chủ nhật': 'Nghỉ bù - Nghỉ Chủ nhật',
    'Khác': 'Khác',
}

NAME_OPTIONS = ["Bùi Hữu Huy", "Trần Văn Quang"]
NAME_DISPLAY = {k: k for k in NAME_OPTIONS}

USER_PROFILES = {
    "Bùi Hữu Huy": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP QL279 - Cao tốc"},
    "Trần Văn Quang": {"chuc_vu": "Nhân viên Kỹ thuật - Công nghệ", "dia_diem": "TTP TL242 - Cao tốc"},
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

STATE_FILE = "user_states.json"
try:
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        user_states = json.load(f)
except FileNotFoundError:
    user_states = {}

def save_states():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_states, f, ensure_ascii=False, indent=4)

known_chat_ids = set()
vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")

def has_reported(name, date_str):
    return reported_data.get(name, {}).get(date_str, False)
def get_missing_days(name, year, month):
    today = datetime.now(vn_tz).date()
    max_day = calendar.monthrange(year, month)[1]
    missing = []

    for d in range(1, max_day + 1):
        date_obj = datetime(year, month, d).date()
        if date_obj > today:
            continue

        date_str = f"{d:02d}/{month:02d}/{year}"
        if not has_reported(name, date_str):
            missing.append(date_str)

    return missing
    
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
        f'entry.{entry_ids["ho_ten"]}': NAME_DISPLAY.get(report['name'], report['name']),
        f'entry.{entry_ids["ngay_base"]}_year': str(year),
        f'entry.{entry_ids["ngay_base"]}_month': f'{month:02d}',
        f'entry.{entry_ids["ngay_base"]}_day': f'{day:02d}',
        f'entry.{entry_ids["ca_lam_viec"]}': CA_DISPLAY.get(report['ca'], report['ca']),
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
        required_datetime = datetime.combine(report_date, time(min_hour, 1)).replace(tzinfo=vn_tz)
        if now >= required_datetime:
            to_submit.append(report)
        else:
            remaining.append(report)
    for report in to_submit:
        success = submit_to_form(report)
        if success:
            mark_as_reported(report['name'], report['date'])
            if 'chat_id' in report and report.get('message_id'):
                try:
                    bot.edit_message_text(
                        f"Báo cáo ngày {report['date']}, ca {CA_DISPLAY.get(report['ca'], report['ca'])} đã được gửi tự động lúc {now.strftime('%H:%M')}!",
                        report['chat_id'], report['message_id']
                    )
                except Exception as e:
                    print("Lỗi thông báo pending:", e)
            else:
                for cid in known_chat_ids:
                    try:
                        name_display = NAME_DISPLAY.get(report['name'], report['name'])
                        ca_display = CA_DISPLAY.get(report['ca'], report['ca'])
                        bot.send_message(cid, f"[TỰ ĐỘNG] Đã gửi báo cáo: {name_display} - {report['date']} - {ca_display}")
                    except Exception:
                        pass
    pending_reports = remaining
    save_pending()

def send_hourly_reminder():
    now = datetime.now(vn_tz)
    if not (8 <= now.hour <= 22):
        return
    today = now.strftime("%d/%m/%Y")
    unreported = []
    for name in NAME_OPTIONS:
        if not has_reported(name, today):
            pending_today = any(r['date'] == today and r['name'] == name for r in pending_reports)
            if not pending_today:
                unreported.append(NAME_DISPLAY.get(name, name))
    if unreported:
        msg = f"Hôm nay ({today}) vẫn còn người chưa báo cáo ca: {', '.join(unreported)}. Ai chưa thì gửi /report nhé!"
        for chat_id in known_chat_ids:
            try:
                bot.send_message(chat_id, msg)
            except Exception as e:
                print(f"Lỗi gửi nhắc: {e}")

def report_all_status(chat_id):
    today = datetime.now(vn_tz).strftime("%d/%m/%Y")
    status_lines = [f"Tình hình báo cáo hôm nay ({today}):"]
    for name in NAME_OPTIONS:
        display = NAME_DISPLAY.get(name, name)
        if has_reported(name, today):
            status_lines.append(f"- {display}: Đã báo hôm nay")
        else:
            pending_for_name = [r for r in pending_reports if r['date'] == today and r['name'] == name]
            if pending_for_name:
                for p in pending_for_name:
                    min_hour = CA_CONFIG[p['ca']]['min_hour']
                    ca_display = CA_DISPLAY.get(p['ca'], p['ca'])
                    status_lines.append(f"- {display}: Đang chờ gửi {ca_display} (sau {min_hour:02d}:01)")
            else:
                status_lines.append(f"- {display}: Chưa báo hôm nay")
    bot.send_message(chat_id, "\n".join(status_lines))

scheduler = BackgroundScheduler(timezone=vn_tz)
scheduler.add_job(process_pending_reports, IntervalTrigger(minutes=5), timezone=vn_tz)
scheduler.add_job(process_pending_reports, CronTrigger(hour='1,7,10,15', minute=1), timezone=vn_tz)
scheduler.add_job(send_hourly_reminder, CronTrigger(hour='1-15', minute=0), timezone=vn_tz)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

import threading
def _set_webhook_later():
    import time as _time
    _time.sleep(3)
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Webhook set OK: {WEBHOOK_URL}")
    except Exception as e:
        print(f"Webhook error: {e}")
threading.Thread(target=_set_webhook_later, daemon=True).start()


# ================================================================
#  /report -- Bao cao 1 ngay
# ================================================================

@bot.message_handler(commands=['start', 'report'])
def start_report(message):
    chat_id = message.chat.id
    known_chat_ids.add(chat_id)
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(NAME_DISPLAY[name], callback_data=f"name_{name}"))
    bot.reply_to(message, "Chọn tên của bạn để bắt đầu báo cáo:", reply_markup=markup)

@bot.message_handler(commands=['missing'])
def handle_missing(message):
    chat_id = message.chat.id
    known_chat_ids.add(chat_id)

    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(NAME_DISPLAY[name], callback_data=f"ms_name_{name}"))

    bot.reply_to(message, "📊 Kiểm tra báo cáo tháng\nChọn tên:", reply_markup=markup)


@bot.message_handler(commands=['reportall'])
def handle_reportall(message):
    report_all_status(message.chat.id)
    
@bot.message_handler(commands=['reportall'])
def handle_reportall(message):
    report_all_status(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('name_'))
def handle_name_callback(call):
    bot.answer_callback_query(call.id, text="Đang xử lý...")
    chat_id = call.message.chat.id
    selected_name = call.data.replace('name_', '')
    if selected_name not in NAME_OPTIONS:
        return
    bot.edit_message_text(
        f"Đã chọn: {NAME_DISPLAY[selected_name]}\nChọn loại ngày báo cáo:",
        chat_id, call.message.message_id
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("Ngày hiện tại", callback_data="date_today"))
    markup.add(InlineKeyboardButton("Tự chọn ngày khác", callback_data="date_custom"))
    sent_msg = bot.send_message(chat_id, "Chọn ngày báo cáo:", reply_markup=markup)
    user_states[str(chat_id)] = {
        'step': 'choose_date_type',
        'name': selected_name,
        'message_id': sent_msg.message_id
    }
    save_states()
    known_chat_ids.add(chat_id)

@bot.callback_query_handler(func=lambda call: call.data in ["date_today", "date_custom"])
def handle_date_type(call):
    bot.answer_callback_query(call.id, text="Đang xử lý...")
    chat_id = call.message.chat.id
    state = user_states.get(str(chat_id))
    if not state or state.get('step') != 'choose_date_type':
        return
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
    if call.data == "date_today":
        today = datetime.now(vn_tz).strftime("%d/%m/%Y")
        state['date'] = today
        state['step'] = 2
        markup = InlineKeyboardMarkup(row_width=2)
        for ca_key in CA_CONFIG:
            markup.add(InlineKeyboardButton(CA_DISPLAY[ca_key], callback_data=ca_key))
        sent_msg = bot.send_message(chat_id, f"Ngày báo cáo: {today} (hôm nay)\nChọn ca làm việc:", reply_markup=markup)
        state['message_id'] = sent_msg.message_id
        save_states()
    else:
        state['step'] = 1
        bot.send_message(chat_id, "Nhập ngày báo cáo (dd/mm/yyyy):")
        save_states()


# ================================================================
#  /reportmissing -- Bao cao / len lich nhieu ngay cung luc
# ================================================================

def parse_day_input(text, year, month):
    """Parse '1, 3, 5-10, 15' thanh list date_str dd/mm/yyyy."""
    max_day = calendar.monthrange(year, month)[1]
    days = set()
    parts = [p.strip() for p in text.replace('\uff0c', ',').split(',')]
    for part in parts:
        if '-' in part:
            bounds = part.split('-')
            if len(bounds) == 2:
                try:
                    start, end = int(bounds[0].strip()), int(bounds[1].strip())
                    for d in range(start, end + 1):
                        if 1 <= d <= max_day:
                            days.add(d)
                except ValueError:
                    pass
        else:
            try:
                d = int(part)
                if 1 <= d <= max_day:
                    days.add(d)
            except ValueError:
                pass
    return [f"{d:02d}/{month:02d}/{year}" for d in sorted(days)]


def _ask_ca_for_day(chat_id, state):
    """Hỏi ca cho từng ngày lần lượt."""
    dates = state['rm_dates']
    idx = state['rm_index']
    if idx >= len(dates):
        _finish_rm(chat_id, state)
        return
    date_str = dates[idx]
    markup = InlineKeyboardMarkup(row_width=2)
    for ca_key in CA_CONFIG:
        markup.add(InlineKeyboardButton(CA_DISPLAY[ca_key], callback_data=f"rm_ca_{ca_key}"))
    bot.send_message(
        chat_id,
        f"Ngày {date_str} ({idx + 1}/{len(dates)})\nChọn ca làm việc:",
        reply_markup=markup
    )


def _finish_rm(chat_id, state):
    """Gửi ngay hoặc lên lịch pending cho tất cả ngày trong rm_ca_map."""
    global pending_reports
    now = datetime.now(vn_tz)
    name = state['rm_name']
    ca_map = state['rm_ca_map']
    sent_now, scheduled, errors = [], [], []

    for date_str, ca in ca_map.items():
        report_data = {
            'name': name,
            'date': date_str,
            'ca': ca,
            'chat_id': chat_id,
            'message_id': None
        }
        day, month, year = map(int, date_str.split('/'))
        min_hour = CA_CONFIG[ca]['min_hour']
        required_dt = datetime.combine(
            datetime(year, month, day).date(), time(min_hour, 1)
        ).replace(tzinfo=vn_tz)

        # Xoa pending cu neu co
        pending_reports = [
            r for r in pending_reports
            if not (r['name'] == name and r['date'] == date_str)
        ]
        mark_as_reported(name, date_str)

        if now >= required_dt:
            ok = submit_to_form(report_data)
            if ok:
                sent_now.append(f"{date_str} ({CA_DISPLAY.get(ca, ca)})")
            else:
                errors.append(f"{date_str} (lỗi gửi)")
        else:
            pending_reports.append(report_data)
            scheduled.append(f"{date_str} ({CA_DISPLAY.get(ca, ca)}) - tự gửi sau {min_hour:02d}:01")

    save_pending()

    name_display = NAME_DISPLAY.get(name, name)
    lines = [f"Kết quả lên lịch cho {name_display}:"]
    if sent_now:
        lines.append("\nĐã gửi ngay:")
        lines += [f"  • {x}" for x in sent_now]
    if scheduled:
        lines.append("\nĐã lên lịch gửi tự động:")
        lines += [f"  • {x}" for x in scheduled]
    if errors:
        lines.append("\nLoi:")
        lines += [f"  • {x}" for x in errors]

    bot.send_message(chat_id, "\n".join(lines))
    if str(chat_id) in user_states:
        del user_states[str(chat_id)]
    save_states()


def _send_day_input_prompt(chat_id, state, year, month):
    state['rm_year'] = year
    state['rm_month'] = month
    state['step'] = 'rm_input_days'
    save_states()
    max_day = calendar.monthrange(year, month)[1]
    bot.send_message(
        chat_id,
        f"Tháng {month:02d}/{year} (có {max_day} ngày)\n\n"
        f"Nhập các ngày cần báo cáo:\n"
        f"• Ngày lẻ dùng dấu ,   ví dụ: 1, 3, 7\n"
        f"• Ngày liên tiếp dùng dấu -   ví dụ: 5-10\n"
        f"• Kết hợp: 1, 3, 5-10, 15, 20-25\n\n"
        f"(Ngày tương lai sẽ được lên lịch gửi tự động)"
    )


@bot.message_handler(commands=['reportmissing'])
def start_report_missing(message):
    chat_id = message.chat.id
    known_chat_ids.add(chat_id)
    markup = InlineKeyboardMarkup(row_width=1)
    for name in NAME_OPTIONS:
        markup.add(InlineKeyboardButton(NAME_DISPLAY[name], callback_data=f"rm_name_{name}"))
    bot.reply_to(message, "Báo cáo / Lên lịch nhiều ngày\nChọn tên của bạn:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('rm_name_'))
def handle_rm_name(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    name = call.data.replace('rm_name_', '')
    if name not in NAME_OPTIONS:
        return
    now = datetime.now(vn_tz)
    cur_m, cur_y = now.month, now.year
    prev_m = cur_m - 1 if cur_m > 1 else 12
    prev_y = cur_y if cur_m > 1 else cur_y - 1
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(f"Tháng {cur_m}/{cur_y} (tháng này)", callback_data=f"rm_month_{cur_y}_{cur_m}"))
    markup.add(InlineKeyboardButton(f"Tháng {prev_m}/{prev_y} (tháng trước)", callback_data=f"rm_month_{prev_y}_{prev_m}"))
    markup.add(InlineKeyboardButton("Nhập tháng khác", callback_data="rm_month_custom"))
    bot.edit_message_text(
        f"Đã chọn: {NAME_DISPLAY[name]}\nChọn tháng cần báo cáo:",
        chat_id, call.message.message_id,
        reply_markup=markup
    )
    user_states[str(chat_id)] = {'step': 'rm_choose_month', 'rm_name': name}
    save_states()


@bot.callback_query_handler(func=lambda call: call.data.startswith('rm_month_'))
def handle_rm_month(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = user_states.get(str(chat_id), {})
    if state.get('step') != 'rm_choose_month':
        return
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
    suffix = call.data.replace('rm_month_', '')
    if suffix == 'custom':
        state['step'] = 'rm_input_month'
        save_states()
        bot.send_message(chat_id, "Nhập tháng/năm cần báo (định dạng mm/yyyy, ví dụ: 03/2025):")
        return
    year, month = int(suffix.split('_')[0]), int(suffix.split('_')[1])
    _send_day_input_prompt(chat_id, state, year, month)


@bot.callback_query_handler(func=lambda call: call.data.startswith('rm_ca_'))
def handle_rm_ca(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = user_states.get(str(chat_id), {})
    if state.get('step') != 'rm_pick_ca':
        return
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
    ca = call.data.replace('rm_ca_', '')
    if ca not in CA_CONFIG:
        return
    dates = state['rm_dates']
    idx = state['rm_index']
    state['rm_ca_map'][dates[idx]] = ca
    state['rm_index'] = idx + 1
    save_states()
    _ask_ca_for_day(chat_id, state)


# ================================================================
#  Message handler (nhap text)
# ================================================================

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    state = user_states.get(str(chat_id))
    if not state:
        bot.reply_to(message, "Gửi /report để báo cáo 1 ngày, hoặc /reportmissing để lên lịch nhiều ngày.")
        return

    # /reportmissing buoc 1: nhap thang tu chon
    if state.get('step') == 'rm_input_month':
        text = message.text.strip()
        try:
            parts = text.split('/')
            month, year = int(parts[0]), int(parts[1])
            assert 1 <= month <= 12 and year >= 2000
            _send_day_input_prompt(chat_id, state, year, month)
        except Exception:
            bot.reply_to(message, "Sai định dạng! Nhập lại mm/yyyy, ví dụ: 03/2025")
        return

    # /reportmissing buoc 2: nhap danh sach ngay
    if state.get('step') == 'rm_input_days':
        text = message.text.strip()
        year = state['rm_year']
        month = state['rm_month']
        dates = parse_day_input(text, year, month)
        if not dates:
            bot.reply_to(message, "Không tìm thấy ngày hợp lệ! Nhập lại, ví dụ: 1, 3, 5-10")
            return
        state['rm_dates'] = dates
        state['rm_index'] = 0
        state['rm_ca_map'] = {}
        state['step'] = 'rm_pick_ca'
        save_states()
        bot.send_message(
            chat_id,
            f"Đã nhận {len(dates)} ngày: {', '.join(dates)}\n\nBắt đầu chọn ca cho từng ngày:"
        )
        _ask_ca_for_day(chat_id, state)
        return

    # /report: nhap ngay tu chon
    if state.get('step') == 1:
        date_str = message.text.strip()
        try:
            day, month, year = map(int, date_str.split('/'))
            datetime(year, month, day)
            state['date'] = date_str
            state['step'] = 2
            markup = InlineKeyboardMarkup(row_width=2)
            for ca_key in CA_CONFIG:
                markup.add(InlineKeyboardButton(CA_DISPLAY[ca_key], callback_data=ca_key))
            sent_msg = bot.send_message(chat_id, f"Ngày báo cáo: {date_str}\nChọn ca làm việc:", reply_markup=markup)
            state['message_id'] = sent_msg.message_id
            save_states()
        except Exception:
            bot.reply_to(message, "Ngày sai định dạng! Nhập lại dd/mm/yyyy.")



# ================================================================
#  Callback handler chung (cho /report)
# ================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('ms_name_'))
def handle_ms_name(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    name = call.data.replace('ms_name_', '')
    if name not in NAME_OPTIONS:
        return

    now = datetime.now(vn_tz)
    year, month = now.year, now.month
    today = now.day

    missing_days = get_missing_days(name, year, month)

    if not missing_days:
        bot.send_message(chat_id, f"✅ {NAME_DISPLAY[name]} đã báo đủ tháng {month:02d}/{year}")
        return

    reported_count = today - len(missing_days)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("Cập nhật", callback_data="ms_yes"),
        InlineKeyboardButton("Không", callback_data="ms_no")
    )

    bot.send_message(
        chat_id,
        f"📊 Thống kê tháng {month:02d}/{year}\n\n"
        f"👤 {NAME_DISPLAY[name]}\n"
        f"✔️ Đã báo: {reported_count} ngày\n"
        f"❌ Chưa báo: {len(missing_days)} ngày\n\n"
        f"{', '.join(missing_days)}\n\n"
        f"Bạn có muốn bổ sung không?",
        reply_markup=markup
    )

    user_states[str(chat_id)] = {
        'step': 'ms_confirm',
        'rm_name': name,
        'rm_dates': missing_days
    }
    save_states()


@bot.callback_query_handler(func=lambda call: call.data in ["ms_yes", "ms_no"])
def handle_missing_confirm(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    state = user_states.get(str(chat_id), {})
    if state.get('step') != 'ms_confirm':
        return

    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())

    if call.data == "ms_no":
        bot.send_message(chat_id, "OK, bỏ qua 👍")
        del user_states[str(chat_id)]
        save_states()
        return

    state['step'] = 'rm_pick_ca'
    state['rm_index'] = 0
    state['rm_ca_map'] = {}
    save_states()

    bot.send_message(chat_id, "Bắt đầu bổ sung từng ngày...")
    _ask_ca_for_day(chat_id, state)
    
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id, text="Đang xử lý...")
    chat_id = call.message.chat.id
    state = user_states.get(str(chat_id))
    if not state:
        print("[DEBUG] State not found for chat", chat_id)
        bot.send_message(chat_id, "Lỗi trạng thái, vui lòng gửi /report lại!")
        return
    try:
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=InlineKeyboardMarkup())
        if state.get('step') == 'confirm_overwrite':
            if call.data == 'yes_overwrite':
                schedule_report(chat_id, state, overwrite=True)
            else:
                bot.send_message(chat_id, "Đã hủy. Gửi /report để thử lại!")
                del user_states[str(chat_id)]
                save_states()
            return
        if state.get('step') != 2:
            print("[DEBUG] Invalid step:", state.get('step'))
            bot.send_message(chat_id, "Trạng thái không hợp lệ, gửi /report lại!")
            return
        ca = call.data
        if ca not in CA_CONFIG:
            bot.send_message(chat_id, "Ca không hợp lệ!")
            return
        state['ca'] = ca
        known_chat_ids.add(chat_id)
        if has_reported(state['name'], state['date']):
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("Báo lại", callback_data='yes_overwrite'),
                InlineKeyboardButton("Hủy", callback_data='no_overwrite')
            )
            ca_display = CA_DISPLAY.get(ca, ca)
            config = CA_CONFIG[ca]
            bot.send_message(chat_id, f"Đã báo ngày {state['date']}! Ghi đè với {ca_display} ({config['tinh_hinh']})?", reply_markup=markup)
            state['step'] = 'confirm_overwrite'
            save_states()
            return
        schedule_report(chat_id, state, overwrite=False)
    except Exception as e:
        print(f"[CALLBACK ERROR] {e}")
        bot.send_message(chat_id, f"Lỗi xử lý: {str(e)}. Gửi /report lại nhé!")


def schedule_report(chat_id, state, overwrite=False):
    print(f"[SCHEDULE] Bat dau cho {state['name']}, ca {state['ca']}, date {state['date']}")
    report_date_obj = datetime.strptime(state['date'], "%d/%m/%Y")
    report_date = report_date_obj.date()
    min_hour = CA_CONFIG[state['ca']]['min_hour']
    required_datetime = datetime.combine(report_date, time(min_hour, 1)).replace(tzinfo=vn_tz)
    now = datetime.now(vn_tz)
    report_data = {
        'name': state['name'],
        'date': state['date'],
        'ca': state['ca'],
        'chat_id': chat_id,
        'message_id': state['message_id']
    }
    mark_as_reported(state['name'], state['date'])
    if now >= required_datetime:
        try:
            bot.send_message(chat_id, "Đang gửi báo cáo...")
            success = submit_to_form(report_data)
            if success:
                note = " (Ghi đè cũ)" if overwrite else ""
                ca_display = CA_DISPLAY.get(state['ca'], state['ca'])
                bot.send_message(chat_id, f"Gửi thành công {ca_display} ngày {state['date']}{note}!")
            else:
                bot.send_message(chat_id, "Lỗi gửi form, thử lại sau!")
        except Exception as e:
            print(f"[SCHEDULE ERROR] {e}")
            bot.send_message(chat_id, "Lỗi khi gửi, thử lại!")
    else:
        global pending_reports
        pending_reports = [r for r in pending_reports if not (r['name'] == state['name'] and r['date'] == state['date'])]
        pending_reports.append(report_data)
        save_pending()
        ca_display = CA_DISPLAY.get(state['ca'], state['ca'])
        bot.send_message(chat_id, f"Đã nhận {ca_display} ngày {state['date']}. Tự gửi sau {min_hour:02d}:01")
    del user_states[str(chat_id)]
    save_states()


# ================================================================
#  Flask routes
# ================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            update = Update.de_json(request.get_json())
            bot.process_new_updates([update])
            print("Webhook received")
        except Exception as e:
            print("Webhook error:", e)
    return '', 200

@app.route('/set_webhook')
def set_webhook_route():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set: {WEBHOOK_URL}", 200
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/')
def health():
    return "Bot alive", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
