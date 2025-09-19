# ati_bot_part1.py (الجزء 1 من 2)
# -*- coding: utf-8 -*-

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import random, time, threading, json, os, re
from datetime import datetime, timedelta

# ------------------ CONFIG ------------------
TOKEN = "8048222360:AAEx-c8wGmNDfav3u5xBXv_jzJpGIXckEcM"  # ضع توكنك هنا
DATA_FILE = "data.json"
LOG_FILE = "bot_logs.txt"
OWNER_ID =  5692270516
  # ضع أيديك لو حابب صلاحيات خاصة لك

bot = telebot.TeleBot(TOKEN)

# ------------------ DEFAULTS / STATE ------------------
default_data = {
    "chats": {},   # chat_id -> config dict
    "users": {},   # user_id -> global stats
}

data_lock = threading.Lock()

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return default_data.copy()

def save_data():
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DATA, f, ensure_ascii=False, indent=2)

DATA = load_data()

def ensure_chat(chat_id):
    key = str(chat_id)
    if key not in DATA["chats"]:
        DATA["chats"][key] = {
            "protection": {
                "photos": False, "videos": False, "links": False, "stickers": False,
                "documents": False, "voice": False, "gifs": False, "forwards": False,
                "anti_raid": True, "anti_link_except_admins": False
            },
            "welcome": {"enabled": True, "text": "👋 أهلاً وسهلاً {first_name}!"},
            "rules": {"enabled": True, "text": "📌 قوانين: الاحترام، ممنوع السب، ممنوع الروابط."},
            "warnings": {"limit": 3, "action": "kick"},  # action: kick / mute
            "bad_words": ["كلب","حمار","fuck","bitch"],
            "slow_mode": 0,
            "flood_control": {"enabled": True, "messages": 6, "seconds": 4},
            "auto_replies": {},  # keyword -> reply
            "custom_cmds": {},   # name -> text
            "scheduled": [],     # list of {time_iso, text}
            "maintenance": False,
            "mention_all_allowed": True,
            "silent_hours": None,  # [start_hour,end_hour]
        }
        save_data()

def log(text):
    ts = datetime.utcnow().isoformat()
    line = f"[{ts}] {text}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

# runtime (not persisted)
recent_messages = {}   # chat_id -> {user_id: [timestamps]}
recent_joins = {}      # chat_id -> [timestamps]
giveaways = {}         # chat_id -> giveaway dict

# ------------------ MENUS ------------------
def main_menu_markup(chat_id):
    ensure_chat(chat_id)
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("🛡️ حماية", callback_data="menu_protection"),
        InlineKeyboardButton("⚙️ إدارة", callback_data="menu_admin"),
        InlineKeyboardButton("📊 نقاط/إحصائيات", callback_data="menu_stats"),
        InlineKeyboardButton("📢 إعلانات", callback_data="menu_schedule"),
        InlineKeyboardButton("🎲 تسلية", callback_data="menu_fun"),
        InlineKeyboardButton("ℹ️ أدوات", callback_data="menu_tools")
    )
    return mk

def protection_menu_markup(chat_id):
    ensure_chat(chat_id)
    cfg = DATA["chats"].get(str(chat_id), {})["protection"]
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton(f"📷 صور [{'ق' if cfg.get('photos') else 'ف'}]", callback_data="toggle_photos"),
        InlineKeyboardButton(f"🎞 فيديو [{'ق' if cfg.get('videos') else 'ف'}]", callback_data="toggle_videos"),
        InlineKeyboardButton(f"🔗 روابط [{'ق' if cfg.get('links') else 'ف'}]", callback_data="toggle_links"),
        InlineKeyboardButton(f"🖼 ملصقات [{'ق' if cfg.get('stickers') else 'ف'}]", callback_data="toggle_stickers"),
        InlineKeyboardButton(f"🎧 أصوات [{'ق' if cfg.get('voice') else 'ف'}]", callback_data="toggle_voice"),
        InlineKeyboardButton(f"📎 مستندات [{'ق' if cfg.get('documents') else 'ف'}]", callback_data="toggle_documents"),
        InlineKeyboardButton(f"🔁 تحويلات [{'ق' if cfg.get('forwards') else 'ف'}]", callback_data="toggle_forwards"),
        InlineKeyboardButton(f"🤖 منع بوتات [{'ق' if cfg.get('anti_raid') else 'ف'}]", callback_data="toggle_anti_raid"),
        InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")
    )
    return mk

def admin_menu_markup(chat_id):
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(
        InlineKeyboardButton("⚠️ تحذيرات/كتم/طرد", callback_data="menu_warn"),
        InlineKeyboardButton("🔒 صيانة (اغلاق الأوامر)", callback_data="toggle_maintenance"),
        InlineKeyboardButton("📋 لوج", callback_data="menu_logs"),
        InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")
    )
    return mk

def fun_menu_markup():
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("😂 نكت", callback_data="fun_joke"),
        InlineKeyboardButton("🎲 نرد", callback_data="fun_dice"),
        InlineKeyboardButton("🧩 لغز", callback_data="fun_riddle"),
        InlineKeyboardButton("🎯 استفتاء", callback_data="fun_poll"),
        InlineKeyboardButton("🎁 سحب", callback_data="menu_giveaway"),
        InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")
    )
    return mk

# ------------------ BASIC COMMANDS ------------------
@bot.message_handler(commands=['start'])
def cmd_start(m):
    ensure_chat(m.chat.id)
    bot.reply_to(m, "أهلاً! اضغط الأزرار لتصفح مميزات البوت:", reply_markup=main_menu_markup(m.chat.id))

@bot.message_handler(commands=['help','مساعدة'])
def cmd_help(m):
    bot.reply_to(m, "قائمة الأوامر متاحة بالأزرار أو استخدم /commands", reply_markup=main_menu_markup(m.chat.id))

@bot.message_handler(commands=['commands'])
def cmd_commands(m):
    txt = (
        "أوامر سريعة:\n"
        "/rules - عرض القوانين\n"
        "/set_rules <text> - تعديل القوانين (ادمن)\n"
        "/set_welcome <text> - تعديل رسالة الترحيب (ادمن)\n"
        "/warn - تحذير (ادمن، رد)\n"
        "/mute <time> - كتم (ادمن، رد)\n"
        "/ban - طرد/حظر (ادمن، رد)\n"
        "/points - نقاطك\n"
        "/top10 - أفضل 10\n"
        "/schedule - جدولة إعلان (ادمن)\n"
        "المزيد بالأزرار..."
    )
    bot.reply_to(m, txt)

# ---------- Admin utilities ----------
def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator","administrator"]
    except:
        return False

@bot.message_handler(commands=['set_rules'])
def cmd_set_rules(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m, "🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "✍️ اكتب نص القوانين بعد الأمر"); return
    ensure_chat(m.chat.id)
    DATA["chats"][str(m.chat.id)]["rules"]["text"] = parts[1]
    save_data()
    bot.reply_to(m, "✅ تم تحديث القوانين")
    log(f"set_rules by {m.from_user.id} in {m.chat.id}")

@bot.message_handler(commands=['rules'])
def cmd_rules(m):
    ensure_chat(m.chat.id)
    cfg = DATA["chats"][str(m.chat.id)]["rules"]
    if not cfg.get("enabled", True):
        bot.reply_to(m, "🚫 القوانين مغلقة"); return
    bot.reply_to(m, cfg.get("text","لا توجد قوانين."))

@bot.message_handler(commands=['set_welcome'])
def cmd_set_welcome(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m, "🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(m, "✍️ اكتب نص الترحيب بعد الأمر (استخدم {first_name})"); return
    ensure_chat(m.chat.id)
    DATA["chats"][str(m.chat.id)]["welcome"]["text"] = parts[1]
    save_data()
    bot.reply_to(m, "✅ تم تحديث رسالة الترحيب")
    log(f"set_welcome by {m.from_user.id} in {m.chat.id}")

# ------------- WELCOME & ANTI-BOT -------------
@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(m):
    ensure_chat(m.chat.id)
    cfg = DATA["chats"][str(m.chat.id)]
    recent_joins.setdefault(m.chat.id, [])
    recent_joins[m.chat.id].append(time.time())
    recent_joins[m.chat.id] = [t for t in recent_joins[m.chat.id] if time.time()-t < 10]
    if cfg["protection"].get("anti_raid") and len(recent_joins[m.chat.id]) > 6:
        bot.send_message(m.chat.id, "🚨 تحذير: انضمامات كثيرة خلال 10 ثواني!")
        log(f"anti_raid triggered in {m.chat.id}")

    for u in m.new_chat_members:
        if u.is_bot and cfg["protection"].get("anti_raid"):
            try:
                bot.kick_chat_member(m.chat.id, u.id)
                log(f"kicked bot {u.id} in {m.chat.id}")
            except:
                pass
        if cfg["welcome"].get("enabled", True):
            text = cfg["welcome"].get("text","أهلاً!") .replace("{first_name}", u.first_name or "")
            bot.send_message(m.chat.id, text)
# ati_bot_part2.py (الجزء 2 من 2)
# ألصقه مباشرة بعد الجزء الأول في نفس الملف

# ------------- WARN / MUTE / BAN -------------
def add_warning(chat_id, user_id, by_user):
    ensure_chat(chat_id)
    key = str(chat_id)
    warned = DATA["chats"][key].get("warnings_store", {})
    warned.setdefault(str(user_id), 0)
    warned[str(user_id)] += 1
    DATA["chats"][key]["warnings_store"] = warned
    save_data()
    limit = DATA["chats"][key]["warnings"]["limit"]
    bot.send_message(chat_id, f"⚠️ تم تحذير العضو ({warned[str(user_id)]}/{limit})")
    log(f"warn {user_id} in {chat_id} by {by_user}")
    if warned[str(user_id)] >= limit:
        action = DATA["chats"][key]["warnings"].get("action","kick")
        try:
            if action == "kick":
                bot.kick_chat_member(chat_id, user_id)
                bot.send_message(chat_id, f"🚫 تم طرد العضو بعد الوصول لحد التحذيرات")
            elif action == "mute":
                bot.restrict_chat_member(chat_id, user_id, until_date=time.time()+300)
                bot.send_message(chat_id, f"🔇 تم كتم العضو بعد التحذيرات")
        except:
            pass
        warned[str(user_id)] = 0
        DATA["chats"][key]["warnings_store"] = warned
        save_data()

@bot.message_handler(commands=['warn'])
def cmd_warn(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m, "🚫 للأدمن فقط"); return
    if not m.reply_to_message:
        bot.reply_to(m, "↩️ رداً على رسالة العضو الذي تريد تحذيره"); return
    add_warning(m.chat.id, m.reply_to_message.from_user.id, m.from_user.id)

@bot.message_handler(commands=['warnings'])
def cmd_warnings(m):
    ensure_chat(m.chat.id)
    warned = DATA["chats"][str(m.chat.id)].get("warnings_store",{})
    text = "قائمة التحذيرات:\n"
    for uid,c in warned.items():
        text += f"- {uid}: {c}\n"
    bot.reply_to(m, text)

@bot.message_handler(commands=['mute'])
def cmd_mute(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    if not m.reply_to_message:
        bot.reply_to(m,"↩️ رد على رسالة العضو لكتمه"); return
    parts = m.text.split()
    dur = 300
    if len(parts) >= 2:
        t = parts[1]
        if t.endswith("m"):
            try: dur = int(t[:-1])*60
            except: dur = 300
        elif t.endswith("h"):
            try: dur = int(t[:-1])*3600
            except: dur = 3600
        else:
            try: dur = int(t)
            except: dur = 300
    uid = m.reply_to_message.from_user.id
    try:
        bot.restrict_chat_member(m.chat.id, uid, until_date=time.time()+dur)
        bot.reply_to(m, f"🔇 تم كتم العضو لمدة {dur} ثانية")
        log(f"muted {uid} in {m.chat.id} for {dur} by {m.from_user.id}")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=['unmute'])
def cmd_unmute(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    if not m.reply_to_message:
        bot.reply_to(m,"↩️ رد على رسالة العضو لفك الكتم"); return
    uid = m.reply_to_message.from_user.id
    try:
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
                                can_send_other_messages=True, can_add_web_page_previews=True)
        bot.restrict_chat_member(m.chat.id, uid, permissions=perms)
        bot.reply_to(m, "🔊 تم فك الكتم")
        log(f"unmuted {uid} in {m.chat.id} by {m.from_user.id}")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=['ban'])
def cmd_ban(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    if not m.reply_to_message:
        bot.reply_to(m,"↩️ رد على رسالة العضو للحظره"); return
    uid = m.reply_to_message.from_user.id
    try:
        bot.kick_chat_member(m.chat.id, uid)
        bot.reply_to(m, "🚫 تم حظر العضو")
        log(f"banned {uid} in {m.chat.id} by {m.from_user.id}")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=['unban'])
def cmd_unban(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "✍️ اكتب ايدي المستخدم بعد الأمر"); return
    try:
        uid = int(parts[1])
        bot.unban_chat_member(m.chat.id, uid)
        bot.reply_to(m, "✅ تم رفع الحظر")
        log(f"unbanned {uid} in {m.chat.id} by {m.from_user.id}")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=['bannedlist'])
def cmd_bannedlist(m):
    bot.reply_to(m, "🔒 API محدود: استرجاع قائمة المحظورين غير مدعوم بسهولة هنا.")

# ------------- PROTECTION / CALLBACKS -------------
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("toggle_"))
def cb_toggle(call):
    key = call.data.replace("toggle_","")
    chat_id = call.message.chat.id
    if not is_admin(chat_id, call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ للأدمن فقط.", show_alert=True); return
    ensure_chat(chat_id)
    if key in DATA["chats"][str(chat_id)]["protection"]:
        DATA["chats"][str(chat_id)]["protection"][key] = not DATA["chats"][str(chat_id)]["protection"][key]
        save_data()
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=protection_menu_markup(chat_id))
        bot.answer_callback_query(call.id, f"تم تغيير {key}")
        log(f"toggled {key} in {chat_id} by {call.from_user.id}")
        return
    # maintenance toggle handled separately

# ------------- GLOBAL MESSAGE FILTER -------------
@bot.message_handler(content_types=['text','photo','video','sticker','audio','voice','document'])
def global_filter(m):
    ensure_chat(m.chat.id)
    chat_cfg = DATA["chats"][str(m.chat.id)]
    # silent hours
    sh = chat_cfg.get("silent_hours")
    if sh:
        try:
            now_h = datetime.now().hour
            if sh[0] <= now_h <= sh[1] and not is_admin(m.chat.id, m.from_user.id):
                return
        except:
            pass

    # maintenance mode
    if chat_cfg.get("maintenance") and not is_admin(m.chat.id, m.from_user.id):
        return

    # flood control
    if chat_cfg.get("flood_control",{}).get("enabled",True):
        uid = m.from_user.id
        recent_messages.setdefault(m.chat.id, {})
        lst = recent_messages[m.chat.id].setdefault(str(uid), [])
        lst.append(time.time())
        window = chat_cfg.get("flood_control",{}).get("seconds",4)
        limit = chat_cfg.get("flood_control",{}).get("messages",6)
        recent_messages[m.chat.id][str(uid)] = [t for t in lst if time.time()-t <= window]
        if len(recent_messages[m.chat.id][str(uid)]) > limit:
            try:
                bot.restrict_chat_member(m.chat.id, uid, until_date=time.time()+60)
                bot.send_message(m.chat.id, f"⏳ @{m.from_user.username or m.from_user.first_name} كُتِم مؤقتًا (فلود)")
                log(f"auto-muted flood {uid} in {m.chat.id}")
            except:
                pass

    # link protection
    if chat_cfg["protection"].get("links") and m.content_type=="text":
        txt = (m.text or "").lower()
        if ("http://" in txt or "https://" in txt or "t.me/" in txt) and not (chat_cfg["protection"].get("anti_link_except_admins") and is_admin(m.chat.id, m.from_user.id)):
            try:
                bot.delete_message(m.chat.id, m.message_id)
                bot.send_message(m.chat.id, "🔗 الروابط مقفولة هنا.")
                add_warning(m.chat.id, m.from_user.id, 0)
            except:
                pass
            return

    # forwards
    if chat_cfg["protection"].get("forwards") and getattr(m, "forward_from", None):
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass
        return

    # media locks
    if m.content_type == "photo" and chat_cfg["protection"].get("photos"):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass; return
    if m.content_type == "video" and chat_cfg["protection"].get("videos"):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass; return
    if m.content_type == "sticker" and chat_cfg["protection"].get("stickers"):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass; return
    if m.content_type in ("voice","audio") and chat_cfg["protection"].get("voice"):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass; return
    if m.content_type == "document" and chat_cfg["protection"].get("documents"):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass; return

    # bad words
    txt = (m.text or "").lower()
    for w in chat_cfg.get("bad_words",[]):
        if w and w in txt:
            try:
                bot.delete_message(m.chat.id, m.message_id)
                add_warning(m.chat.id, m.from_user.id, m.from_user.id)
            except:
                pass
            return

    # auto replies
    for k,v in chat_cfg.get("auto_replies",{}).items():
        if k and k in (m.text or ""):
            bot.reply_to(m, v)
            return

    # points/activity
    uid = str(m.from_user.id)
    DATA["users"].setdefault(uid, {"name": m.from_user.first_name, "points":0, "messages":0})
    DATA["users"][uid]["points"] += 1
    DATA["users"][uid]["messages"] += 1
    save_data()

# ------------- SLOW MODE -------------
@bot.message_handler(commands=['slow'])
def cmd_slow(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m,"✍️ اكتب عدد الثواني بعد الأمر (0 لإيقاف)"); return
    try:
        sec = int(parts[1])
        DATA["chats"][str(m.chat.id)]["slow_mode"] = sec
        save_data()
        bot.reply_to(m, f"✅ تم ضبط السلو مود على {sec} ثانية")
    except:
        bot.reply_to(m,"⚠️ صيغة غير صحيحة")

@bot.message_handler(commands=['slow_off'])
def cmd_slow_off(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    DATA["chats"][str(m.chat.id)]["slow_mode"] = 0
    save_data()
    bot.reply_to(m, "✅ تم إيقاف السلو مود")

# ------------- STATS / POINTS / TOP10 -------------
@bot.message_handler(commands=['points','نقاطي'])
def cmd_points(m):
    uid = str(m.from_user.id)
    pts = DATA["users"].get(uid,{}).get("points",0)
    bot.reply_to(m, f"⭐ نقاطك: {pts}")

@bot.message_handler(commands=['top10','توب'])
def cmd_top10(m):
    users = DATA.get("users",{})
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("points",0), reverse=True)[:10]
    if not sorted_users:
        bot.reply_to(m, "لا توجد بيانات")
        return
    txt = "🏆 أفضل 10 أعضاء:\n"
    for i,(uid,ud) in enumerate(sorted_users,1):
        txt += f"{i}. {ud.get('name','-')} — {ud.get('points',0)} نقطة\n"
    bot.reply_to(m, txt)

@bot.message_handler(commands=['userinfo','معلومات'])
def cmd_userinfo(m):
    target = None
    if m.reply_to_message:
        target = m.reply_to_message.from_user
    else:
        parts = m.text.split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            try:
                username = parts[1][1:]
                for uid, ud in DATA["users"].items():
                    if ud.get("name","").lower() == username.lower():
                        target = type("u",(object,),{"id":int(uid),"first_name":ud.get("name")})
                        break
            except:
                pass
    if not target:
        target = m.from_user
    uid = str(target.id)
    ud = DATA["users"].get(uid, {"name": target.first_name, "points":0, "messages":0})
    warnings = DATA["chats"].get(str(m.chat.id),{}).get("warnings_store",{}).get(uid,0)
    text = f"ℹ️ معلومات: {ud.get('name')}\n- رسائل: {ud.get('messages',0)}\n- نقاط: {ud.get('points',0)}\n- تحذيرات: {warnings}\n- id: {uid}"
    bot.reply_to(m, text)

# ------------- SCHEDULED ANNOUNCEMENTS -------------
def announce_scheduler():
    while True:
        now = datetime.utcnow()
        changed = False
        for chat_id, cfg in DATA["chats"].items():
            sched = cfg.get("scheduled",[])
            newlist = []
            for item in sched:
                try:
                    t = datetime.fromisoformat(item["time"])
                except:
                    continue
                if t <= now:
                    try:
                        bot.send_message(int(chat_id), item["text"])
                        log(f"scheduled send to {chat_id}: {item['text']}")
                    except:
                        pass
                    changed = True
                else:
                    newlist.append(item)
            cfg["scheduled"] = newlist
        if changed:
            save_data()
        time.sleep(5)

threading.Thread(target=announce_scheduler, daemon=True).start()

@bot.message_handler(commands=['schedule','جدولة'])
def cmd_schedule(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m, "🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(m, "✍️ استخدم: /schedule <ثواني> <النص>"); return
    try:
        sec = int(parts[1])
        when = (datetime.utcnow() + timedelta(seconds=sec)).isoformat()
        ensure_chat(m.chat.id)
        DATA["chats"][str(m.chat.id)]["scheduled"].append({"time": when, "text": parts[2]})
        save_data()
        bot.reply_to(m, "✅ تم جدولة الإعلان")
    except:
        bot.reply_to(m, "⚠️ خطأ في الصيغة")

# ------------- PIN / UNPIN -------------
@bot.message_handler(commands=['pin'])
def cmd_pin(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    if not m.reply_to_message:
        bot.reply_to(m,"↩️ رد على رسالة لتثبيتها"); return
    try:
        bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
        bot.reply_to(m,"📌 تم التثبيت")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=['unpin'])
def cmd_unpin(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    try:
        bot.unpin_chat_message(m.chat.id)
        bot.reply_to(m,"✅ تم إلغاء التثبيت")
    except Exception as e:
        bot.reply_to(m, f"⚠️ خطأ: {e}")

# ------------- POLLS / FUN -------------
@bot.message_handler(commands=['poll','استفتاء'])
def cmd_poll(m):
    parts = m.text.split(maxsplit=1)
    question = parts[1] if len(parts)>1 else "هل توافق؟"
    try:
        bot.send_poll(m.chat.id, question, ["نعم","لا"], is_anonymous=False)
    except:
        bot.reply_to(m, "⚠️ لم أستطع عمل الاستفتاء")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("fun_"))
def cb_fun(c):
    if c.data == "fun_joke":
        bot.send_message(c.message.chat.id, random.choice([
            "😂 نكتة 1", "🤣 نكتة 2", "😅 نكتة 3"
        ]))
    elif c.data == "fun_dice":
        bot.send_dice(c.message.chat.id)
    elif c.data == "fun_riddle":
        bot.send_message(c.message.chat.id, "لغز: ما هو؟ ...")

# ------------- GIVEAWAY -------------
@bot.message_handler(commands=['start_giveaway'])
def cmd_start_giveaway(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=2)
    if len(parts)<3:
        bot.reply_to(m,"✍️ استخدم: /start_giveaway <ثواني> <الجائزة>"); return
    try:
        sec = int(parts[1])
    except:
        bot.reply_to(m,"✍️ رقم ثواني غير صحيح"); return
    prize = parts[2]
    end = time.time()+sec
    giveaways[m.chat.id] = {"end": end, "prize": prize, "participants": set()}
    bot.reply_to(m, f"🎁 سحب بدأ على: {prize}. للانضمام اكتب /join")
    log(f"giveaway started in {m.chat.id} prize:{prize}")

@bot.message_handler(commands=['join'])
def cmd_join_giveaway(m):
    g = giveaways.get(m.chat.id)
    if not g:
        bot.reply_to(m,"🚫 لا يوجد سحب جاري"); return
    g["participants"].add(m.from_user.id)
    bot.reply_to(m,"✅ تم تسجيل مشاركتك")

def giveaway_watcher():
    while True:
        now = time.time()
        for chat_id, g in list(giveaways.items()):
            if now >= g["end"]:
                parts = list(g["participants"])
                if parts:
                    winner = random.choice(parts)
                    try:
                        bot.send_message(chat_id, f"🏆 الفائز: {winner}\nجائزة: {g['prize']}")
                    except:
                        pass
                else:
                    bot.send_message(chat_id, "لا يوجد مشاركين في السحب.")
                giveaways.pop(chat_id, None)
        time.sleep(3)

threading.Thread(target=giveaway_watcher, daemon=True).start()

# ------------- BACKUP / EXPORT -------------
@bot.message_handler(commands=['backup','export'])
def cmd_backup(m):
    if OWNER_ID and m.from_user.id != OWNER_ID:
        bot.reply_to(m,"🚫 للأونر فقط"); return
    if not os.path.exists(DATA_FILE):
        bot.reply_to(m, "لا توجد بيانات بعد.")
        return
    with open(DATA_FILE,"rb") as f:
        bot.send_document(m.chat.id, f)

# ------------- LOGS -------------
@bot.message_handler(commands=['logs'])
def cmd_logs(m):
    if not is_admin(m.chat.id, m.from_user.id):
        bot.reply_to(m,"🚫 للأدمن فقط"); return
    if not os.path.exists(LOG_FILE):
        bot.reply_to(m, "لا توجد لوجات بعد.")
        return
    with open(LOG_FILE,"r",encoding="utf-8") as f:
        lines = f.readlines()[-30:]
    bot.reply_to(m, "🗒️ آخر لوج:\n" + "".join(lines))

# ------------- REPORT / BAD WORDS / AUTO-REPLIES / CUSTOM CMDs -------------
@bot.message_handler(commands=['report'])
def cmd_report(m):
    parts = m.text.split(maxsplit=1)
    text = parts[1] if len(parts)>1 else "(بدون نص)"
    bot.reply_to(m, "✅ تم ارسال البلاغ للأدمنية.")
    log(f"report in {m.chat.id} by {m.from_user.id}: {text}")

@bot.message_handler(commands=['add_bad'])
def cmd_add_bad(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ اكتب كلمة"); return
    ensure_chat(m.chat.id)
    DATA["chats"][str(m.chat.id)].setdefault("bad_words",[]).append(parts[1])
    save_data()
    bot.reply_to(m,"✅ تم إضافة الكلمة")

@bot.message_handler(commands=['del_bad'])
def cmd_del_bad(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ اكتب كلمة"); return
    ensure_chat(m.chat.id)
    try:
        DATA["chats"][str(m.chat.id)]["bad_words"].remove(parts[1])
        save_data()
        bot.reply_to(m,"✅ تم الحذف")
    except:
        bot.reply_to(m,"⚠️ الكلمة مش موجودة")

@bot.message_handler(commands=['add_reply'])
def cmd_add_reply(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ الصيغة: /add_reply key|reply"); return
    try:
        key,reply = parts[1].split("|",1)
        ensure_chat(m.chat.id)
        DATA["chats"][str(m.chat.id)].setdefault("auto_replies",{})[key]=reply
        save_data()
        bot.reply_to(m,"✅ تم إضافة الرد التلقائي")
    except:
        bot.reply_to(m,"⚠️ صيغة خاطئة")

@bot.message_handler(commands=['del_reply'])
def cmd_del_reply(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ اكتب المفتاح"); return
    k = parts[1]
    ensure_chat(m.chat.id)
    if k in DATA["chats"][str(m.chat.id)].get("auto_replies",{}):
        DATA["chats"][str(m.chat.id)]["auto_replies"].pop(k,None)
        save_data()
        bot.reply_to(m,"✅ تم الحذف")
    else:
        bot.reply_to(m,"⚠️ المفتاح غير موجود")

@bot.message_handler(commands=['add_cmd'])
def cmd_add_cmd(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ اكتب الصيغة: /add_cmd name|text"); return
    try:
        name,text = parts[1].split("|",1)
        ensure_chat(m.chat.id)
        DATA["chats"][str(m.chat.id)].setdefault("custom_cmds",{})[name]=text
        save_data()
        bot.reply_to(m,"✅ تم إضافة الأمر المخصص")
    except:
        bot.reply_to(m,"⚠️ صيغة خاطئة")

@bot.message_handler(commands=['run_cmd'])
def cmd_run_cmd(m):
    parts = m.text.split(maxsplit=1)
    if len(parts)<2: bot.reply_to(m,"✍️ اكتب اسم الأمر"); return
    name = parts[1]
    ensure_chat(m.chat.id)
    txt = DATA["chats"][str(m.chat.id)].get("custom_cmds",{}).get(name)
    if txt:
        bot.reply_to(m, txt)
    else:
        bot.reply_to(m,"❌ الأمر غير موجود")

# ------------- CLEAR MESSAGES (limited) -------------
@bot.message_handler(commands=['clear'])
def cmd_clear(m):
    if not is_admin(m.chat.id, m.from_user.id): bot.reply_to(m,"🚫 للأدمن فقط"); return
    parts = m.text.split()
    try:
        n = int(parts[1]) if len(parts)>1 else 10
    except:
        n = 10
    mid = m.message_id
    deleted = 0
    for i in range(mid-1, mid-n-1, -1):
        try:
            bot.delete_message(m.chat.id, i)
            deleted += 1
        except:
            pass
    bot.reply_to(m, f"🗑️ تم حذف {deleted} رسالة (تقريبي)")

# ------------- MAINTENANCE -------------
@bot.callback_query_handler(func=lambda c: c.data == "toggle_maintenance")
def cb_toggle_maintenance(c):
    if not is_admin(c.message.chat.id, c.from_user.id):
        bot.answer_callback_query(c.id, "⚠️ للأدمن فقط", show_alert=True); return
    ensure_chat(c.message.chat.id)
    cur = DATA["chats"][str(c.message.chat.id)].get("maintenance", False)
    DATA["chats"][str(c.message.chat.id)]["maintenance"] = not cur
    save_data()
    bot.answer_callback_query(c.id, f"maintenance -> {not cur}")
    log(f"maintenance toggled in {c.message.chat.id} by {c.from_user.id}")

# ------------- AUTOSAVE -------------
def autosave():
    while True:
        save_data()
        time.sleep(10)
threading.Thread(target=autosave, daemon=True).start()

# ------------- CALLBACK NAVIGATION -------------
@bot.callback_query_handler(func=lambda c: True)
def cb_router(c):
    data = c.data
    cid = c.message.chat.id
    if data == "menu_protection":
        bot.edit_message_text("🛡️ إعدادات الحماية:", cid, c.message.message_id, reply_markup=protection_menu_markup(cid))
    elif data == "menu_admin":
        bot.edit_message_text("⚙️ إدارة الجروب:", cid, c.message.message_id, reply_markup=admin_menu_markup(cid))
    elif data == "menu_stats":
        bot.edit_message_text("📊 نقاط وإحصائيات:", cid, c.message.message_id, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏆 توب 10", callback_data="cb_top10")],[InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]]
        ))
    elif data == "menu_schedule":
        bot.edit_message_text("📢 الإعلانات المجدولة:", cid, c.message.message_id, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ جدولة", callback_data="cb_schedule_add")],[InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]]
        ))
    elif data == "menu_fun":
        bot.edit_message_text("🎲 أوامر التسلية:", cid, c.message.message_id, reply_markup=fun_menu_markup())
    elif data == "menu_tools":
        bot.edit_message_text("🧰 أدوات:", cid, c.message.message_id, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📋 القوانين", callback_data="cb_rules")],[InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")]]
        ))
    elif data == "back_main":
        bot.edit_message_text("القائمة الرئيسية:", cid, c.message.message_id, reply_markup=main_menu_markup(cid))
    elif data == "cb_top10":
        users = DATA.get("users",{})
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("points",0), reverse=True)[:10]
        txt = "🏆 أفضل 10:\n" + "\n".join([f"{i+1}. {u[1].get('name')} — {u[1].get('points',0)}" for i,u in enumerate(sorted_users)]) if sorted_users else "لا بيانات"
        bot.send_message(cid, txt)
    elif data == "cb_rules":
        ensure_chat(cid)
        bot.send_message(cid, DATA["chats"][str(cid)]["rules"]["text"])
    elif data == "cb_schedule_add":
        bot.send_message(cid, "⏳ استخدم الأمر: /schedule <ثواني> <النص>")
    else:
        bot.answer_callback_query(c.id, "تم")

# ------------- START BOT -------------

if __name__ == "__main__":
    print("✅ A.T.I Bot شغال...")

    # --- تأكد أن أي webhook مفعل تم حذفه لمنع Conflict مع polling ---
    try:
        import requests, time
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        time.sleep(0.3)
    except Exception as e:
        print("deleteWebhook error (ignored):", e)

    # --- محاولة لجلب (وتفريغ) أية تحديثات عالقة ---
    try:
        bot.get_updates(timeout=1)
    except Exception:
        pass

    # --- شغّل polling (واحد فقط) ---
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print("Polling stopped with error:", e)
