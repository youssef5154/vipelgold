import os
import json
import telebot
import threading

# =========================
# BOT CONFIGURATION
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing!")

bot = telebot.TeleBot(TOKEN)

DATA_FILE = os.getenv("DATA_FILE", "channels.json")
lock = threading.Lock()

data = {
    "source": None,
    "destinations": []
}


# =========================
# LOAD AND SAVE DATA
# =========================

def load_data():
    global data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)

        data["source"] = saved.get("source")
        data["destinations"] = saved.get("destinations", [])

    except FileNotFoundError:
        save_data()

    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load data: {error}")


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


load_data()


# =========================
# ADMIN CHECK
# =========================

def is_admin(message):
    return (
        message.chat.type == "private"
        and message.from_user is not None
        and message.from_user.id == ADMIN_ID
    )


def admin_only(message):
    if not is_admin(message):
        bot.reply_to(message, "❌ الأمر ده متاح للمدير فقط.")
        return False

    return True


# =========================
# CHANNEL RESOLUTION
# =========================

def resolve_channel(value):
    value = value.strip()

    if value.startswith("https://t.me/"):
        value = "@" + value.split("/")[-1]

    elif value.startswith("t.me/"):
        value = "@" + value.split("/")[-1]

    chat = bot.get_chat(value)

    if chat.type != "channel":
        raise ValueError("المعرف ده مش قناة تيليجرام.")

    return chat.id, chat.title


# =========================
# START COMMAND
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    if not admin_only(message):
        return

    bot.reply_to(
        message,
        "أهلاً بيك في بوت نسخ القنوات 🚀\n\n"
        "الأوامر المتاحة:\n\n"
        "/setsource - تحديد قناة المصدر\n"
        "/add - إضافة قناة مستهدفة\n"
        "/remove - حذف قناة مستهدفة\n"
        "/list - عرض القنوات المستهدفة\n"
        "/channels - عرض ملخص القنوات\n"
        "/help - المساعدة"
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    start(message)


# =========================
# SET SOURCE CHANNEL
# =========================

@bot.message_handler(commands=["setsource"])
def set_source(message):
    if not admin_only(message):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(
            message,
            "استخدم الأمر بالشكل ده:\n"
            "/setsource @SourceChannel"
        )
        return

    try:
        channel_id, title = resolve_channel(parts[1])

        with lock:
            data["source"] = channel_id
            data["destinations"] = [
                item for item in data["destinations"]
                if item["id"] != channel_id
            ]
            save_data()

        bot.reply_to(
            message,
            f"✅ تم تحديد قناة المصدر:\n{title}\n"
            f"ID: {channel_id}"
        )

    except Exception as error:
        bot.reply_to(
            message,
            f"❌ مقدرتش أحدد القناة.\n"
            f"تأكد إن البوت أدمن فيها.\n"
            f"التفاصيل: {error}"
        )


# =========================
# ADD DESTINATION CHANNEL
# =========================

@bot.message_handler(commands=["add"])
def add_channel(message):
    if not admin_only(message):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(
            message,
            "استخدم الأمر بالشكل ده:\n"
            "/add @DestinationChannel"
        )
        return

    try:
        channel_id, title = resolve_channel(parts[1])

        with lock:
            if channel_id == data["source"]:
                bot.reply_to(
                    message,
                    "❌ مينفعش تضيف قناة المصدر كقناة مستهدفة."
                )
                return

            if any(
                item["id"] == channel_id
                for item in data["destinations"]
            ):
                bot.reply_to(
                    message,
                    "⚠️ القناة دي موجودة بالفعل."
                )
                return

            data["destinations"].append({
                "id": channel_id,
                "title": title
            })

            save_data()

            total = len(data["destinations"])

        bot.reply_to(
            message,
            f"✅ تمت إضافة القناة:\n{title}\n\n"
            f"عدد القنوات المستهدفة: {total}"
        )

    except Exception as error:
        bot.reply_to(
            message,
            f"❌ فشلت إضافة القناة.\n"
            f"تأكد من معرف القناة وصلاحيات البوت.\n"
            f"التفاصيل: {error}"
        )


# =========================
# REMOVE DESTINATION CHANNEL
# =========================

@bot.message_handler(commands=["remove"])
def remove_channel(message):
    if not admin_only(message):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(
            message,
            "استخدم الأمر بالشكل ده:\n"
            "/remove @DestinationChannel"
        )
        return

    try:
        channel_id, title = resolve_channel(parts[1])

        with lock:
            old_count = len(data["destinations"])

            data["destinations"] = [
                item for item in data["destinations"]
                if item["id"] != channel_id
            ]

            if len(data["destinations"]) == old_count:
                bot.reply_to(
                    message,
                    "⚠️ القناة دي مش موجودة في القائمة."
                )
                return

            save_data()

            total = len(data["destinations"])

        bot.reply_to(
            message,
            f"✅ تم حذف القناة:\n{title}\n\n"
            f"القنوات المتبقية: {total}"
        )

    except Exception as error:
        bot.reply_to(
            message,
            f"❌ حصل خطأ أثناء حذف القناة.\n{error}"
        )


# =========================
# LIST DESTINATIONS
# =========================

@bot.message_handler(commands=["list"])
def list_channels(message):
    if not admin_only(message):
        return

    with lock:
        destinations = list(data["destinations"])

    if not destinations:
        bot.reply_to(message, "📭 مفيش قنوات مستهدفة لسه.")
        return

    lines = ["📋 القنوات المستهدفة:\n"]

    for number, channel in enumerate(destinations, start=1):
        lines.append(
            f"{number}. {channel['title']}\n"
            f"ID: {channel['id']}"
        )

    bot.reply_to(message, "\n\n".join(lines))


# =========================
# CHANNEL SUMMARY
# =========================

@bot.message_handler(commands=["channels"])
def channels_summary(message):
    if not admin_only(message):
        return

    with lock:
        source = data["source"]
        destinations = list(data["destinations"])

    source_text = (
        str(source) if source is not None
        else "لم يتم تحديدها"
    )

    bot.reply_to(
        message,
        "📊 ملخص القنوات\n\n"
