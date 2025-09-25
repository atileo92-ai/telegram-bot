# ati_bot.py
# Telegram Bot A.T.I (Replit-ready, python-telegram-bot v20+)

import os
import json
import random
import re
import asyncio
import pytz
from datetime import datetime, time, timedelta

import requests
import yt_dlp

from telegram import Update, ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, JobQueue
)

# ----------------------------
# Persistence helpers
# ----------------------------
DATA_DIR = "data"
GROUPS_FILE = os.path.join(DATA_DIR, "group_settings.json")
BANK_FILE = os.path.join(DATA_DIR, "bank.json")
VIOLATIONS_FILE = os.path.join(DATA_DIR, "violations.json")
AZAN_FILE = os.path.join(DATA_DIR, "azan_enabled.json")

os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error saving", path, e)

group_settings = load_json(GROUPS_FILE, {})
bank = load_json(BANK_FILE, {})
user_violations = load_json(VIOLATIONS_FILE, {})
azan_enabled = load_json(AZAN_FILE, {})

# ----------------------------
# Config & constants
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Please set BOT_TOKEN in environment (Replit Secret).")

AZKAR_LIST = [
    "🕋 سبحان الله وبحمده.",
    "🕋 لا إله إلا الله وحده لا شريك له.",
    "🕋 أستغفر الله وأتوب إليه.",
    "🕋 اللهم صلِّ على نبينا محمد.",
    "🕋 لا حول ولا قوة إلا بالله."
]

BAD_WORDS = [
    "كلب", "حيوان", "متناك", "عرص", "منيك", "زفت", "شرموط", "شرموطة", "قواد",
    "a7a", "mnkk", "mnik", "3rs", "fuck", "shit", "dick", "bitch", "asshole"
]

ADS_PATTERNS = [
    r"(t\.me/)", r"(telegram\.me/)", r"(joinchat)", r"(discord\.gg)", r"(bit\.ly)",
    r"(porn|xxx|sex|onlyfans|nude|webcam)"
]

# ----------------------------
# Utilities
# ----------------------------
def init_group(chat_id: int):
    key = str(chat_id)
    if key not in group_settings:
        group_settings[key] = {
            "lock_photos": False,
            "lock_stickers": False,
            "lock_videos": False,
            "lock_links": False,
            "lock_games": False,
            "lock_files": False,
            "lock_voice": False,
            "lock_all": False
        }
        save_json(GROUPS_FILE, group_settings)

def get_user_balance(user_id: int) -> int:
    return bank.get(str(user_id), 100)

def set_user_balance(user_id: int, amount: int):
    bank[str(user_id)] = amount
    save_json(BANK_FILE, bank)

def incr_violation(chat_id: int, user_id: int) -> int:
    key = f"{chat_id}:{user_id}"
    user_violations[key] = user_violations.get(key, 0) + 1
    save_json(VIOLATIONS_FILE, user_violations)
    return user_violations[key]

# ----------------------------
# Basic commands
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 أهلاً بك في بوت A.T.I.\n"
        "🛡 للحماية 🎮 للألعاب 🎵 للموسيقى 🕌 للأذكار.\n\n"
        "اكتب /مساعدة لرؤية الأوامر."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 قائمة الأوامر:\n\n"
        "🛡 الحماية:\n"
        "/قفل_الصور – /فتح_الصور\n/قفل_الملصقات – /فتح_الملصقات\n/قفل_الكل – /فتح_الكل\n\n"
        "🎮 الألعاب:\n"
        "/اكس /نرد /ذكاء /حب /حظ /رصيدي /توب\n\n"
        "🎵 الموسيقى:\n"
        "/شغل <اسم أو رابط>  /فيديو <رابط>\n\n"
        "🕌 الأذكار:\n"
        "/تشغيل_الاذان /ايقاف_الاذان\n"
    )

# ----------------------------
# Protection
# ----------------------------
async def lock_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_group(chat_id)
    group_settings[str(chat_id)]["lock_photos"] = True
    save_json(GROUPS_FILE, group_settings)
    await update.message.reply_text("✅ تم قفل الصور.")

async def unlock_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_group(chat_id)
    group_settings[str(chat_id)]["lock_photos"] = False
    save_json(GROUPS_FILE, group_settings)
    await update.message.reply_text("✅ تم فتح الصور.")

async def lock_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_group(chat_id)
    group_settings[str(chat_id)]["lock_all"] = True
    save_json(GROUPS_FILE, group_settings)
    await update.message.reply_text("🚫 تم قفل الكل.")

async def unlock_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_group(chat_id)
    group_settings[str(chat_id)]["lock_all"] = False
    save_json(GROUPS_FILE, group_settings)
    await update.message.reply_text("✅ تم فتح الكل.")

async def message_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    init_group(update.effective_chat.id)
    settings = group_settings.get(str(update.effective_chat.id), {})
    msg = update.effective_message

    if settings.get("lock_all"):
        try:
            await msg.delete()
            return
        except Exception:
            return

    if settings.get("lock_photos") and msg.photo:
        await msg.delete()
        return

    if settings.get("lock_stickers") and msg.sticker:
        await msg.delete()
        return

    text = (msg.text or "").lower()
    if text:
        found_bad = any(w in text for w in BAD_WORDS) or any(re.search(p, text) for p in ADS_PATTERNS)
        if found_bad:
            try:
                await msg.delete()
                incr_violation(update.effective_chat.id, msg.from_user.id)
                await context.bot.send_message(update.effective_chat.id,
                                               f"🚫 {msg.from_user.first_name} أرسل رسالة ممنوعة.")
            except Exception:
                pass

# ----------------------------
# Games & Bank
# ----------------------------
async def xo_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = [random.choice(["❌", "⭕️"]) for _ in range(9)]
    board = f"{items[0]} | {items[1]} | {items[2]}\n---------\n{items[3]} | {items[4]} | {items[5]}\n---------\n{items[6]} | {items[7]} | {items[8]}"
    await update.message.reply_text(f"🎮 لعبة XO:\n\n{board}")

async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🎲 النتيجة: {random.randint(1,6)}")

async def iq_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🧠 نسبة ذكاءك: {random.randint(50,160)} IQ")

async def love_meter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗️ مثال: /حب @username")
        return
    target = context.args[0]
    await update.message.reply_text(f"💖 نسبة الحب بينك وبين {target}: {random.randint(1,100)}%")

async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bal = get_user_balance(uid)
    await update.message.reply_text(f"💰 رصيدك: {bal} جنيه.")

async def invest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bal = get_user_balance(uid)
    change = random.choice([-1,1]) * random.randint(5,60)
    set_user_balance(uid, bal + change)
    if change >= 0:
        await update.message.reply_text(f"📈 ربحت {change} جنيه.")
    else:
        await update.message.reply_text(f"📉 خسرت {abs(change)} جنيه.")

async def luck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bal = get_user_balance(uid)
    amount = random.randint(5,50)
    if random.choice([True, False]):
        set_user_balance(uid, bal + amount)
        await update.message.reply_text(f"🍀 ربحت {amount} جنيه.")
    else:
        set_user_balance(uid, max(0, bal - amount))
        await update.message.reply_text(f"💔 خسرت {amount} جنيه.")

async def top_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bank:
        await update.message.reply_text("🚫 لا يوجد لاعبين.")
        return
    top_players = sorted(bank.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = []
    for i, (uid_str, bal) in enumerate(top_players):
        lines.append(f"{i+1}. ID {uid_str} - {bal} جنيه")
    await update.message.reply_text("🏆 التوب:\n\n" + "\n".join(lines))

# ----------------------------
# Music with yt-dlp
# ----------------------------
async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎵 مثال: /شغل despacito")
        return
    query = " ".join(context.args)
    await update.message.reply_text("⏳ جاري التحضير...")

    if query.startswith("http"):
        target = query
    else:
        target = f"ytsearch1:{query}"

    def download():
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DATA_DIR, "song.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "prefer_ffmpeg": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=True)
            if "entries" in info:
                info = info["entries"][0]
            filepath = ydl.prepare_filename(info)
            return filepath, info.get("title"), info.get("webpage_url")

    try:
        filepath, title, url = await asyncio.to_thread(download)
    except Exception as e:
        await update.message.reply_text("❌ فشل التشغيل، جرب بالرابط مباشرة.")
        return

    try:
        await update.message.reply_chat_action(action=ChatAction.UPLOAD_AUDIO)
        with open(filepath, "rb") as f:
            await update.message.reply_audio(audio=f, title=title)
    except Exception:
        await update.message.reply_text(f"🎶 {title}\n{url}")
    finally:
        try: os.remove(filepath)
        except: pass

async def play_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎬 مثال: /فيديو <رابط>")
        return
    await update.message.reply_text("⚠️ تحميل الفيديو تقيل على Replit. هاهو الرابط:")
    await update.message.reply_text(context.args[0])

# ----------------------------
# Azan
# ----------------------------
def parse_time_str(tstr: str):
    try:
        h, m = map(int, tstr.split(":"))
        return time(h, m)
    except: return None

async def fetch_prayer_times(city="Cairo", country="Egypt", method=5):
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method={method}"
        r = await asyncio.to_thread(requests.get, url, timeout=10)
        data = r.json().get("data", {}).get("timings", {})
        return {k: v for k, v in data.items() if k in ("Fajr","Dhuhr","Asr","Maghrib","Isha")}
    except: return None

async def schedule_azan_jobs(app):
    times = await fetch_prayer_times()
    if not times: return
    tz = pytz.timezone("Africa/Cairo")
    jq: JobQueue = app.job_queue
    now = datetime.now(tz)
    for prayer, tstr in times.items():
        t = parse_time_str(tstr)
        if not t: continue
        first_run = tz.localize(datetime.combine(now.date(), t))
        if first_run < now: first_run += timedelta(days=1)
        async def cb(context: ContextTypes.DEFAULT_TYPE, name=prayer):
            for chat_str, enabled in azan_enabled.items():
                if enabled:
                    try:
                        await context.bot.send_message(int(chat_str), f"🕌 حان الآن موعد {name}.")
                        await context.bot.send_message(int(chat_str), random.choice(AZKAR_LIST))
                    except: pass
        jq.run_repeating(cb, interval=timedelta(days=1), first=first_run)

async def start_azan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    azan_enabled[chat_id] = True
    save_json(AZAN_FILE, azan_enabled)
    await update.message.reply_text("🕌 تم تفعيل الأذان + الأذكار.")

async def stop_azan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    azan_enabled[chat_id] = False
    save_json(AZAN_FILE, azan_enabled)
    await update.message.reply_text("🕌 تم إيقاف الأذان + الأذكار.")

# ----------------------------
# Auto responses
# ----------------------------
AUTO_RESPONSES = {
    "تصبحوا على خير": "🌙 تصبح على خير.",
    "بحبك": "❤️ وانا بحبك اكتر.",
    "سلام": "✋ في امان الله.",
    "صباح الخير": "☀️ صباح النور.",
    "مساء الخير": "🌙 مساء الفل.",
}

async def auto_responses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    for k, v in AUTO_RESPONSES.items():
        if k in text:
            await update.message.reply_text(v)
            return

# ----------------------------
# Main
# ----------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("مساعدة", help_command))

    # protection
    app.add_handler(CommandHandler("قفل_الصور", lock_photos))
    app.add_handler(CommandHandler("فتح_الصور", unlock_photos))
    app.add_handler(CommandHandler("قفل_الكل", lock_all))
    app.add_handler(CommandHandler("فتح_الكل", unlock_all))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), message_filter))

    # games
    app.add_handler(CommandHandler("اكس", xo_game))
    app.add_handler(CommandHandler("نرد", dice_game))
    app.add_handler(CommandHandler("ذكاء", iq_test))
    app.add_handler(CommandHandler("حب", love_meter))
    app.add_handler(CommandHandler("رصيدي", my_balance))
    app.add_handler(CommandHandler("استثمار", invest))
    app.add_handler(CommandHandler("حظ", luck))
    app.add_handler(CommandHandler("توب", top_balance))

    # music
    app.add_handler(CommandHandler("شغل", play_music))
    app.add_handler(CommandHandler("فيديو", play_video))

    # azan
    app.add_handler(CommandHandler("تشغيل_الاذان", start_azan_cmd))
    app.add_handler(CommandHandler("ايقاف_الاذان", stop_azan_cmd))

    # auto responses
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), auto_responses))

    async def on_startup(app):
        await schedule_azan_jobs(app)
    app.post_init = on_startup

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
