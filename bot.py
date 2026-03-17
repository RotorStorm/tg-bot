import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN, ADMIN_IDS, PAYMENT_DETAILS, GROUP_IDS, CHANNEL_IDS, REPOST_INTERVAL_SECONDS, MAX_TEXT_LENGTH

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_AD_TEXT, WAITING_RECEIPT = range(2)
pending_ads = {}
last_button_post = {}
ALL_CHATS = CHANNEL_IDS

# Главное меню пользователя
MAIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("📝 Подать объявление")]],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие 👇"
)


def get_ad_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📝 Подать объявление",
            url=f"https://t.me/{bot_username}",
            api_kwargs={"style": "success"}
        )
    ]])


async def send_button_post(bot):
    me = await bot.get_me()
    keyboard = get_ad_keyboard(me.username)
    for chat_id in ALL_CHATS:
        try:
            if chat_id in last_button_post:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=last_button_post[chat_id],
                        reply_markup=keyboard
                    )
                except Exception:
                    del last_button_post[chat_id]
                    msg = await bot.send_message(
                        chat_id=chat_id,
                        text="📝 Подать объявление через бота",
                        reply_markup=keyboard,
                        disable_notification=True
                    )
                    last_button_post[chat_id] = msg.message_id
            else:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text="📝 Подать объявление через бота",
                    reply_markup=keyboard,
                    disable_notification=True
                )
                last_button_post[chat_id] = msg.message_id
                logger.info(f"Кнопка отправлена в чат {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка кнопки в чате {chat_id}: {e}")
        await asyncio.sleep(0.5)


async def publish_ad_to_all(bot, ad_text: str):
    me = await bot.get_me()
    keyboard = get_ad_keyboard(me.username)
    for chat_id in ALL_CHATS:
        try:
            if chat_id in last_button_post:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=last_button_post[chat_id])
                except Exception:
                    pass
            await bot.send_message(chat_id=chat_id, text=ad_text)
            await asyncio.sleep(0.3)
            msg = await bot.send_message(
                chat_id=chat_id,
                text="📝 Подать объявление через бота",
                reply_markup=keyboard,
                disable_notification=True
            )
            last_button_post[chat_id] = msg.message_id
        except Exception as e:
            logger.error(f"Ошибка публикации в чате {chat_id}: {e}")
        await asyncio.sleep(0.5)


async def auto_repost(bot):
    pass


# ───────────────────────────────────────────────
# ДИАЛОГ С ПОЛЬЗОВАТЕЛЕМ
# ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📝 Отправьте текст объявления с телефоном.\n\nМаксимальная длина: {MAX_TEXT_LENGTH} символов.",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_AD_TEXT


async def begin_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📝 Отправьте текст объявления с телефоном.\n\n"
        f"Максимальная длина: {MAX_TEXT_LENGTH} символов.",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_AD_TEXT


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Как подать объявление:*\n\n"
        "1️⃣ Нажмите кнопку 📝 Подать объявление\n"
        "2️⃣ Напишите текст объявления с телефоном\n"
        "3️⃣ Оплатите и отправьте фото чека\n"
        "4️⃣ Ждите подтверждения от администратора\n\n"
        "📌 *Команды:*\n"
        "/start — главное меню\n"
        "/ad — подать объявление\n"
        "/help — помощь\n"
        "/myid — узнать свой ID\n"
        "/cancel — отменить текущее действие",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END


async def receive_ad_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ad_text = update.message.text

    if len(ad_text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ Текст слишком длинный!\n\n"
            f"Максимум {MAX_TEXT_LENGTH} символов, у вас {len(ad_text)}.\n\n"
            f"Сократите текст и отправьте снова."
        )
        return WAITING_AD_TEXT

    pending_ads[user.id] = {
        "text": ad_text,
        "username": user.username,
        "first_name": user.first_name,
        "user_id": user.id
    }

    await update.message.reply_text(
        f"💰 Стоимость публикации:\n{PAYMENT_DETAILS}\n\n"
        f"Для публикации отправьте фото чека об оплате."
    )
    return WAITING_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id not in pending_ads:
        await update.message.reply_text(
            "⚠️ Сначала отправьте текст объявления.",
            reply_markup=MAIN_MENU
        )
        return ConversationHandler.END

    receipt_file_id = None
    if update.message.photo:
        receipt_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        receipt_file_id = update.message.document.file_id
    else:
        await update.message.reply_text("📎 Отправьте фото чека об оплате.")
        return WAITING_RECEIPT

    pending_ads[user.id]["receipt_file_id"] = receipt_file_id

    await update.message.reply_text(
        "✅ Ваша заявка отправлена на модерацию.\n\n"
        "Мы свяжемся с вами после проверки.",
        reply_markup=MAIN_MENU
    )

    ad_data = pending_ads[user.id]
    username_display = f"@{ad_data['username']}" if ad_data['username'] else "Нет"

    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ В работу", callback_data=f"approve_{user.id}")],
        [
            InlineKeyboardButton("❌ Оплаты нет", callback_data=f"reject_{user.id}"),
            InlineKeyboardButton("⚠️ Проблема", callback_data=f"problem_{user.id}")
        ]
    ])

    admin_text = (
        f"🎉 Новая заявка\n\n"
        f"👤 Имя: {ad_data['first_name']}\n"
        f"💬 Юзернейм: {username_display}\n"
        f"🔗 Личка: <a href='tg://user?id={user.id}'>Перейти в личку</a>\n\n"
        f"📋 Текст объявления:\n{ad_data['text']}"
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
        if update.message.photo:
            await context.bot.send_photo(chat_id=admin_id, photo=receipt_file_id, caption="💰 Подтверждение оплаты")
        else:
            await context.bot.send_document(chat_id=admin_id, document=receipt_file_id, caption="💰 Подтверждение оплаты")

    return ConversationHandler.END


# ───────────────────────────────────────────────
# КНОПКИ АДМИНА
# ───────────────────────────────────────────────

async def approve_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Нет прав.", show_alert=True)
        return

    user_id = int(query.data.split("_")[1])

    if user_id not in pending_ads:
        await query.edit_message_text("⚠️ Заявка не найдена или уже обработана.")
        return

    ad_data = pending_ads[user_id]
    username_display = f"@{ad_data['username']}" if ad_data['username'] else "Нет"

    await query.edit_message_text(f"⏳ Публикую в {len(ALL_CHATS)} чатах...")

    try:
        await publish_ad_to_all(context.bot, ad_data['text'])

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Ваша заявка одобрена!\n\nОна будет опубликована в ближайшее время.",
            reply_markup=MAIN_MENU
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Ваше объявление опубликовано!\n\nСпасибо за использование нашего сервиса.",
            reply_markup=MAIN_MENU
        )
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ Объявление от {ad_data['first_name']} ({username_display}) опубликовано в {len(ALL_CHATS)} чатах."
            )

    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=f"❌ Ошибка: {e}")
    finally:
        pending_ads.pop(user_id, None)


async def reject_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Нет прав.", show_alert=True)
        return

    user_id = int(query.data.split("_")[1])
    ad_data = pending_ads.get(user_id, {})
    username_display = f"@{ad_data.get('username')}" if ad_data.get('username') else "Нет"

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Оплата не подтверждена.\n\nПожалуйста, повторите попытку — отправьте корректный чек.\n\nЕсли считаете что это ошибка — свяжитесь с поддержкой.",
            reply_markup=MAIN_MENU
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")

    await query.edit_message_text(
        f"❌ Оплаты нет. Пользователь {ad_data.get('first_name', '')} ({username_display}) уведомлён."
    )
    pending_ads.pop(user_id, None)


async def problem_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Нет прав.", show_alert=True)
        return

    user_id = int(query.data.split("_")[1])
    ad_data = pending_ads.get(user_id, {})
    username_display = f"@{ad_data.get('username')}" if ad_data.get('username') else "Нет"

    new_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Всё же одобрить", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")]
    ])

    new_text = (
        f"🎉 Новая заявка\n\n"
        f"👤 Имя: {ad_data.get('first_name', '')}\n"
        f"💬 Юзернейм: {username_display}\n"
        f"🔗 Личка: <a href='tg://user?id={user_id}'>Перейти в личку</a>\n\n"
        f"📋 Текст объявления:\n{ad_data.get('text', '')}\n\n"
        f"⚠️ Заявка помечена как проблемная."
    )

    await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=new_keyboard)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ По вашей заявке возник вопрос.\n\nАдминистратор свяжется с вами в ближайшее время.",
            reply_markup=MAIN_MENU
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 Действие отменено.\n\nНажмите кнопку чтобы начать заново.",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END


async def post_ad_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Нет прав.")
        return
    await update.message.reply_text(f"⏳ Обновляю кнопку в {len(ALL_CHATS)} чатах...")
    await send_button_post(context.bot)
    await update.message.reply_text("✅ Готово!")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"👤 Ваш Telegram ID: `{user.id}`", parse_mode="Markdown")


async def on_startup(app: Application):
    # Устанавливаем команды в меню бота
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
    ])
    await send_button_post(app.bot)
    asyncio.create_task(auto_repost(app.bot))
    logger.info(f"Бот запущен. Чатов: {len(ALL_CHATS)}.")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("ad", begin_ad),
            MessageHandler(filters.Regex("^📝 Подать объявление$"), begin_ad),
        ],
        states={
            WAITING_AD_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ad_text)
            ],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text(
                    "📎 Отправьте фото чека об оплате."
                ))
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("post", post_ad_button))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(approve_ad, pattern=r"^approve_\d+$"))
    app.add_handler(CallbackQueryHandler(reject_ad, pattern=r"^reject_\d+$"))
    app.add_handler(CallbackQueryHandler(problem_ad, pattern=r"^problem_\d+$"))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
