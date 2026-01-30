"""Обработчики для Telegram бота"""
import logging
from typing import Dict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from sheets.operations import (
    get_user_role, get_cashflow_history, add_user_to_roles,
    update_deal_status_with_role
)
from utils.cache import (
    get_cached_user_deals, get_cached_user_role, invalidate_cache,
    get_cached_deals
)
from business.cashflow import (
    get_current_stage, get_deal_summary, process_stage_transition
)
from business.validators import validate_amount_string
from bot.notifications import send_notification, get_telegram_ids_by_role
from bot.keyboards import (
    get_main_menu_keyboard,
    get_deals_list_keyboard,
    get_deal_detail_keyboard,
    get_cancel_keyboard,
    get_transfer_recipient_keyboard,
    get_amount_confirmation_keyboard
)
from bot.messages import (
    get_welcome_message,
    get_deals_list_message,
    get_deal_detail_message,
    get_cashflow_history_message,
    get_stage_confirmation_message,
    get_error_message,
    get_success_message,
    get_debt_summary_message
)
import config

logger = logging.getLogger(__name__)

# Хранилище временных данных (в продакшене лучше использовать Redis или БД)
user_context: Dict[int, Dict] = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    telegram_id = str(user.id)
    
    try:
        user_name = user.full_name or user.username or "Пользователь"
        
        # Автоматически добавляем пользователя в таблицу ролей (если его там нет)
        add_user_to_roles(telegram_id, user_name)
        
        # Получаем роль пользователя (используем кэш)
        user_role_obj = get_cached_user_role(telegram_id)
        role = user_role_obj.role if user_role_obj else config.ROLE_NULL
        
        message = get_welcome_message(user_name, role)
        keyboard = get_main_menu_keyboard()
        
        await update.message.reply_text(message, reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Ошибка в start_command: {e}")
        error_msg = get_error_message(str(e))
        if len(error_msg) > 4000:
            error_msg = "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        keyboard = get_main_menu_keyboard()
        await update.message.reply_text(error_msg, reply_markup=keyboard)


async def my_deals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /my_deals"""
    user = update.effective_user
    telegram_id = str(user.id)
    
    try:
        from sheets.operations import get_debt_summary
        
        user_role_obj = get_cached_user_role(telegram_id)
        if not user_role_obj:
            user_role_obj = get_user_role(telegram_id)  # Fallback
        
        # Получаем сделки (используем кэш)
        deals = get_cached_user_deals(telegram_id, user_role_obj.role if user_role_obj else config.ROLE_NULL)
        
        # Для собственника получаем сводку по долгам
        debt_summary = None
        if user_role_obj.is_owner():
            debt_summary = get_debt_summary()
        
        if not deals:
            if debt_summary:
                message = get_debt_summary_message(debt_summary)
                keyboard = get_main_menu_keyboard()
                await update.message.reply_text(message, reply_markup=keyboard)
                return
            message = "У вас пока нет сделок."
            keyboard = get_main_menu_keyboard()
            await update.message.reply_text(message, reply_markup=keyboard)
            return
        
        message = get_deals_list_message(deals, page=0, debt_summary=debt_summary)
        keyboard = get_deals_list_keyboard(deals, page=0)
        
        await update.message.reply_text(message, reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Ошибка в my_deals_command: {e}")
        error_msg = get_error_message(str(e))
        if len(error_msg) > 4000:
            error_msg = "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        keyboard = get_main_menu_keyboard()
        await update.message.reply_text(error_msg, reply_markup=keyboard)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback query (нажатия на кнопки)"""
    query = update.callback_query
    
    # Пытаемся ответить на callback, но не блокируем выполнение при ошибке
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback query: {e}")
        # Продолжаем выполнение даже если не удалось ответить
    
    user = update.effective_user
    telegram_id = str(user.id)
    data = query.data
    
    try:
        user_role_obj = get_cached_user_role(telegram_id)
        if not user_role_obj:
            user_role_obj = get_user_role(telegram_id)  # Fallback если кэш не работает
        
        if data == "main_menu":
            user_name = user.full_name or user.username or "Пользователь"
            message = get_welcome_message(user_name, user_role_obj.role)
            keyboard = get_main_menu_keyboard()
            await query.edit_message_text(message, reply_markup=keyboard)
        
        elif data == "my_deals":
            from sheets.operations import get_debt_summary
            
            # Используем кэш для быстрого получения сделок
            deals = get_cached_user_deals(telegram_id, user_role_obj.role if user_role_obj else config.ROLE_NULL)
            
            # Для собственника получаем сводку по долгам
            debt_summary = None
            if user_role_obj.is_owner():
                debt_summary = get_debt_summary()
            
            if not deals:
                if debt_summary:
                    message = get_debt_summary_message(debt_summary)
                    keyboard = get_main_menu_keyboard()
                    await query.edit_message_text(message, reply_markup=keyboard)
                    return
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text("У вас пока нет сделок.", reply_markup=keyboard)
                except Exception:
                    await query.message.reply_text("У вас пока нет сделок.", reply_markup=keyboard)
                return
            
            message = get_deals_list_message(deals, page=0, debt_summary=debt_summary)
            # Проверяем длину сообщения
            if len(message) > 4000:
                message = "📋 Список сделок\n\n(Список слишком длинный, используйте кнопки для навигации)"
            keyboard = get_deals_list_keyboard(deals, page=0)
            try:
                await query.edit_message_text(message, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Ошибка при показе списка сделок: {e}")
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text("Ошибка при загрузке списка.", reply_markup=keyboard)
                except Exception:
                    await query.message.reply_text("Ошибка при загрузке списка.", reply_markup=keyboard)
        
        elif data.startswith("deals_page_"):
            page = int(data.split("_")[-1])
            deals = get_cached_user_deals(telegram_id, user_role_obj.role if user_role_obj else config.ROLE_NULL)
            message = get_deals_list_message(deals, page=page)
            # Проверяем длину сообщения
            if len(message) > 4000:
                message = f"📋 Список сделок (страница {page + 1})\n\n(Список слишком длинный, используйте кнопки для навигации)"
            keyboard = get_deals_list_keyboard(deals, page=page)
            try:
                await query.edit_message_text(message, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Ошибка при показе списка сделок: {e}")
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text("Ошибка при загрузке списка.", reply_markup=keyboard)
                except Exception:
                    await query.message.reply_text("Ошибка при загрузке списка.", reply_markup=keyboard)
        
        elif data.startswith("deal_"):
            # Формат: deal_{hash}_{page}_{idx}
            parts = data.split("_")
            if len(parts) >= 4:
                deal_hash = int(parts[1])
                page = int(parts[2])
                idx = int(parts[3])
                
                # Ищем deal_id по хешу во всех сделках
                all_deals = get_cached_deals()
                deal_id = None
                
                for deal in all_deals:
                    if hash(deal.deal_id) % 1000000 == deal_hash:
                        deal_id = deal.deal_id
                        break
                
                # Если не нашли, пробуем в отфильтрованных сделках пользователя
                if not deal_id:
                    deals = get_cached_user_deals(
                        telegram_id,
                        user_role_obj.role if user_role_obj else config.ROLE_NULL
                    )
                    start_idx = page * 10
                    if start_idx + idx < len(deals):
                        deal = deals[start_idx + idx]
                        deal_id = deal.deal_id if hasattr(deal, 'deal_id') else str(deal)
                
                if deal_id:
                    await show_deal_detail(query, deal_id, user_role_obj, telegram_id)
                else:
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text(
                            "Сделка не найдена.",
                            reply_markup=keyboard
                        )
                    except Exception:
                        await query.message.reply_text(
                            "Сделка не найдена.",
                            reply_markup=keyboard
                        )
            else:
                # Старый формат для обратной совместимости
                deal_id = data[5:]
                await show_deal_detail(query, deal_id, user_role_obj, telegram_id)
        
        elif data.startswith("hist_") or data.startswith("history_"):
            # Новый формат: hist_{hash} или старый: history_{deal_id}
            if data.startswith("hist_"):
                deal_hash = int(data[5:])
                # Находим deal_id по хешу из списка сделок (используем кэш)
                deals = get_cached_user_deals(telegram_id, user_role_obj.role if user_role_obj else config.ROLE_NULL)
                deal_id = None
                for deal in deals:
                    if hash(deal.deal_id) % 1000000 == deal_hash:
                        deal_id = deal.deal_id
                        break
            else:
                # Старый формат для обратной совместимости
                deal_id = data[8:]  # Убираем префикс "history_"
            
            if deal_id:
                from sheets.operations import get_deal_data_from_sheet
                from business.cashflow import get_current_stage
                
                events = get_cashflow_history(deal_id)
                message = get_cashflow_history_message(deal_id, events)
                # Проверяем длину сообщения
                if len(message) > 4000:
                    message = "📜 История сделки\n\n(Слишком много событий, показаны последние 20)"
                
                deal_data = get_deal_data_from_sheet(deal_id)
                who_received_cash = deal_data.get("who_received_cash", "") if deal_data else ""
                amount_received = deal_data.get("amount_received") if deal_data else None
                current_stage = get_current_stage(deal_id)
                
                keyboard = get_deal_detail_keyboard(deal_id, user_role_obj.role, current_stage, who_received_cash, amount_received)
                try:
                    await query.edit_message_text(message, reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Ошибка при показе истории: {e}")
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text("Ошибка при загрузке истории.", reply_markup=keyboard)
                    except Exception:
                        await query.message.reply_text("Ошибка при загрузке истории.", reply_markup=keyboard)
            else:
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text("Сделка не найдена.", reply_markup=keyboard)
                except Exception:
                    await query.message.reply_text("Сделка не найдена.", reply_markup=keyboard)
        
        elif data.startswith("conf_") or data.startswith("confirm_"):
            # Новый формат: conf_{deal_hash}_{stage_hash} или старый: confirm_{deal_id}_{stage}
            if data.startswith("conf_"):
                parts = data.split("_")
                if len(parts) >= 3:
                    deal_hash = int(parts[1])
                    stage_hash = int(parts[2])
                    
                    # Находим deal_id и stage по хешам
                    # Используем ВСЕ сделки из кэша, а не только отфильтрованные
                    logger.info(
                        f"Обработка conf_ с deal_hash={deal_hash}, "
                        f"stage_hash={stage_hash}"
                    )
                    all_deals = get_cached_deals()
                    deal_id = None
                    stage = None
                    
                    # Ищем deal_id по хешу во всех сделках
                    for deal in all_deals:
                        if hash(deal.deal_id) % 1000000 == deal_hash:
                            deal_id = deal.deal_id
                            logger.info(f"Найдена сделка: {deal_id}")
                            break
                    
                    # Если не нашли в кэше, пробуем в отфильтрованных сделках пользователя
                    if not deal_id:
                        user_deals = get_cached_user_deals(
                            telegram_id,
                            user_role_obj.role if user_role_obj else config.ROLE_NULL
                        )
                        for deal in user_deals:
                            if hash(deal.deal_id) % 1000000 == deal_hash:
                                deal_id = deal.deal_id
                                logger.info(
                                    f"Найдена сделка в пользовательских: {deal_id}"
                                )
                                break
                    
                    # Находим stage по хешу
                    if deal_id:
                        for s in [
                            config.STAGE_TRANSFERRED_TO_ASSISTANT,
                            config.STAGE_ACCEPTED_BY_ASSISTANT,
                            config.STAGE_TRANSFERRED_TO_OWNER,
                            config.STAGE_ACCEPTED_BY_OWNER
                        ]:
                            if hash(s) % 10000 == stage_hash:
                                stage = s
                                logger.info(f"Найден этап: {stage}")
                                break
                    
                    if not deal_id or not stage:
                        logger.warning(
                            f"Не найдена сделка или этап: "
                            f"deal_id={deal_id}, stage={stage}"
                        )
                        keyboard = get_main_menu_keyboard()
                        try:
                            await query.edit_message_text(
                                "Ошибка: не найдена сделка или этап.",
                                reply_markup=keyboard
                            )
                        except Exception:
                            await query.message.reply_text(
                                "Ошибка: не найдена сделка или этап.",
                                reply_markup=keyboard
                            )
                        return
                    
                    # Получаем предыдущую сумму (если есть)
                    events = get_cashflow_history(deal_id)
                    previous_amount = None
                    
                    # Ищем сумму на предыдущем этапе
                    for event in reversed(events):
                        if event.stage != stage:
                            previous_amount = event.amount
                            break
                    
                    message = get_stage_confirmation_message(
                        stage, deal_id, previous_amount
                    )
                    # Проверяем длину сообщения
                    if len(message) > 4000:
                        message = (
                            f"📝 Подтверждение этапа\n\n"
                            f"Сделка: {deal_id[:50]}\nВведите сумму:"
                        )
                    keyboard = get_cancel_keyboard()
                    
                    # Получаем имя из колонки "Представьтесь" или используем Telegram имя как fallback
                    display_name = user_role_obj.predstavites if user_role_obj and user_role_obj.predstavites else (user.full_name or user.username or "Пользователь")
                    
                    # Сохраняем контекст
                    user_context[query.from_user.id] = {
                        "deal_id": deal_id,
                        "stage": stage,
                        "user_role": user_role_obj,
                        "telegram_id": telegram_id,
                        "user_name": display_name
                    }
                    
                    try:
                        await query.edit_message_text(
                            message, reply_markup=keyboard
                        )
                    except Exception as e:
                        logger.error(
                            f"Ошибка при редактировании сообщения "
                            f"подтверждения: {e}"
                        )
                        keyboard = get_main_menu_keyboard()
                        try:
                            await query.edit_message_text(
                                "Ошибка. Попробуйте еще раз.",
                                reply_markup=keyboard
                            )
                        except Exception:
                            await query.message.reply_text(
                                "Ошибка. Попробуйте еще раз.",
                                reply_markup=keyboard
                            )
                    return
                else:
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text("Ошибка формата данных.", reply_markup=keyboard)
                    except Exception:
                        await query.message.reply_text("Ошибка формата данных.", reply_markup=keyboard)
                    return
            else:
                # Старый формат для обратной совместимости
                parts = data.split("_", 2)
                if len(parts) >= 3:
                    deal_id = parts[1]
                    stage = parts[2]
                else:
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text("Ошибка формата данных.", reply_markup=keyboard)
                    except Exception:
                        await query.message.reply_text("Ошибка формата данных.", reply_markup=keyboard)
                    return
                # Получаем предыдущую сумму (если есть)
                events = get_cashflow_history(deal_id)
                previous_amount = None
                
                # Ищем сумму на предыдущем этапе
                for event in reversed(events):
                    if event.stage != stage:
                        previous_amount = event.amount
                        break
                
                message = get_stage_confirmation_message(stage, deal_id, previous_amount)
                # Проверяем длину сообщения
                if len(message) > 4000:
                    message = f"📝 Подтверждение этапа\n\nСделка: {deal_id[:50]}\nВведите сумму:"
                keyboard = get_cancel_keyboard()
                
                # Получаем имя из колонки "Представьтесь" или используем Telegram имя как fallback
                display_name = user_role_obj.predstavites if user_role_obj and user_role_obj.predstavites else (user.full_name or user.username or "Пользователь")
                
                # Сохраняем контекст
                user_context[query.from_user.id] = {
                    "deal_id": deal_id,
                    "stage": stage,
                    "user_role": user_role_obj,
                    "telegram_id": telegram_id,
                    "user_name": display_name
                }
                
                try:
                    await query.edit_message_text(message, reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения подтверждения: {e}")
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text("Ошибка. Попробуйте еще раз.", reply_markup=keyboard)
                    except Exception:
                        await query.message.reply_text("Ошибка. Попробуйте еще раз.", reply_markup=keyboard)
        
        elif data.startswith("transfer_"):
            # Обработчик кнопки "Передать ДС"
            deal_hash = int(data.split("_")[1])
            logger.info(f"Обработка transfer_ с deal_hash={deal_hash}")
            
            # Находим deal_id по хешу из всех сделок (используем кэш)
            all_deals = get_cached_deals()
            deal_id = None
            
            # Сначала ищем во всех сделках
            for deal in all_deals:
                if hash(deal.deal_id) % 1000000 == deal_hash:
                    deal_id = deal.deal_id
                    logger.info(f"Найдена сделка: {deal_id}")
                    break
            
            # Если не нашли, пробуем в отфильтрованных сделках пользователя
            if not deal_id:
                deals = get_cached_user_deals(
                    telegram_id,
                    user_role_obj.role if user_role_obj else config.ROLE_NULL
                )
                for deal in deals:
                    if hash(deal.deal_id) % 1000000 == deal_hash:
                        deal_id = deal.deal_id
                        logger.info(f"Найдена сделка в пользовательских: {deal_id}")
                        break
            
            if deal_id:
                # Показываем меню выбора получателя
                message = (
                    f"💰 Передача денежных средств\n\n"
                    f"Сделка: {deal_id}\n\nВыберите получателя:"
                )
                keyboard = get_transfer_recipient_keyboard(deal_id)
                try:
                    await query.edit_message_text(message, reply_markup=keyboard)
                    logger.info(f"Показано меню выбора получателя для {deal_id}")
                except Exception as e:
                    logger.error(f"Ошибка при показе меню передачи: {e}")
                    keyboard = get_main_menu_keyboard()
                    try:
                        await query.edit_message_text(
                            "Ошибка. Попробуйте еще раз.",
                            reply_markup=keyboard
                        )
                    except Exception:
                        await query.message.reply_text(
                            "Ошибка. Попробуйте еще раз.",
                            reply_markup=keyboard
                        )
            else:
                logger.warning(f"Сделка не найдена для deal_hash={deal_hash}")
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text(
                        "Сделка не найдена.",
                        reply_markup=keyboard
                    )
                except Exception:
                    await query.message.reply_text(
                        "Сделка не найдена.",
                        reply_markup=keyboard
                    )
        
        elif data.startswith("confirm_amount_"):
            # Подтверждение введенной суммы
            amount_hash = int(data.split("_")[2])
            
            user_id = query.from_user.id
            if user_id not in user_context:
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text(
                        "Сессия истекла. Начните заново.",
                        reply_markup=keyboard
                    )
                except Exception:
                    await query.message.reply_text(
                        "Сессия истекла. Начните заново.",
                        reply_markup=keyboard
                    )
                return
            
            context_data = user_context[user_id]
            deal_id = context_data["deal_id"]
            stage = context_data["stage"]
            user_role_obj = context_data["user_role"]
            telegram_id = context_data["telegram_id"]
            user_name = context_data["user_name"]
            amount = context_data.get("amount")
            
            # Проверяем, что сумма совпадает с хешем
            if amount is None or hash(str(amount)) % 1000000 != amount_hash:
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text(
                        "Ошибка: сумма не найдена. Начните заново.",
                        reply_markup=keyboard
                    )
                except Exception:
                    await query.message.reply_text(
                        "Ошибка: сумма не найдена. Начните заново.",
                        reply_markup=keyboard
                    )
                if user_id in user_context:
                    del user_context[user_id]
                return
            
            # Сохраняем событие
            success = process_stage_transition(
                deal_id=deal_id,
                from_stage=get_current_stage(deal_id),
                to_stage=stage,
                amount=amount,
                user=user_name,
                role=user_role_obj.role
            )
            
            if success:
                # Инвалидируем кэш после успешного обновления
                invalidate_cache()
                
                # Отправляем уведомления
                if stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
                    assistant_ids = get_telegram_ids_by_role(config.ROLE_ASSISTANT)
                    for assistant_id in assistant_ids:
                        try:
                            await send_notification(
                                bot=context.bot,
                                telegram_id=assistant_id,
                                deal_id=deal_id,
                                stage=config.STAGE_TRANSFERRED_TO_ASSISTANT,
                                amount=amount,
                                from_user=user_name
                            )
                        except Exception as e:
                            logger.error(
                                f"Ошибка при отправке уведомления "
                                f"ассистенту {assistant_id}: {e}"
                            )
                
                elif stage == config.STAGE_TRANSFERRED_TO_OWNER:
                    owner_ids = get_telegram_ids_by_role(config.ROLE_OWNER)
                    for owner_id in owner_ids:
                        try:
                            await send_notification(
                                bot=context.bot,
                                telegram_id=owner_id,
                                deal_id=deal_id,
                                stage=config.STAGE_TRANSFERRED_TO_OWNER,
                                amount=amount,
                                from_user=user_name
                            )
                        except Exception as e:
                            logger.error(
                                f"Ошибка при отправке уведомления "
                                f"собственнику {owner_id}: {e}"
                            )
                
                # Получаем обновленную сводку по сделке
                summary = get_deal_summary(deal_id)
                
                # Показываем полную цепочку движения денег
                from bot.messages import get_cashflow_chain_message
                
                message = get_cashflow_chain_message(deal_id, summary)
                
                # Добавляем кнопку "Главное меню"
                keyboard = get_main_menu_keyboard()
                
                try:
                    await query.edit_message_text(
                        message,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Ошибка при показе цепочки: {e}")
                    # Если сообщение слишком длинное, показываем краткую версию
                    from bot.messages import format_currency
                    short_message = (
                        f"✅ Успешно!\n\n"
                        f"Сделка: {deal_id}\n"
                        f"Сумма {format_currency(amount)} сохранена.\n\n"
                        f"Используйте кнопку 'Мои сделки' для просмотра деталей."
                    )
                    try:
                        await query.edit_message_text(
                            short_message,
                            reply_markup=keyboard
                        )
                    except Exception:
                        await query.message.reply_text(
                            short_message,
                            reply_markup=keyboard
                        )
            else:
                keyboard = get_main_menu_keyboard()
                try:
                    await query.edit_message_text(
                        get_error_message("Не удалось сохранить данные"),
                        reply_markup=keyboard
                    )
                except Exception:
                    await query.message.reply_text(
                        get_error_message("Не удалось сохранить данные"),
                        reply_markup=keyboard
                    )
            
            # Очищаем контекст
            if user_id in user_context:
                del user_context[user_id]
        
        elif data == "cancel":
            user_id = query.from_user.id
            if user_id in user_context:
                del user_context[user_id]
            
            keyboard = get_main_menu_keyboard()
            try:
                await query.edit_message_text(
                    "Действие отменено.",
                    reply_markup=keyboard
                )
            except Exception:
                await query.message.reply_text(
                    "Действие отменено.",
                    reply_markup=keyboard
                )
    
    except Exception as e:
        logger.error(f"Ошибка в callback_handler: {e}")
        error_msg = get_error_message(str(e))
        # Если сообщение слишком длинное, сокращаем его
        if len(error_msg) > 4000:
            error_msg = "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        keyboard = get_main_menu_keyboard()
        try:
            await query.edit_message_text(error_msg, reply_markup=keyboard)
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое сообщение
            logger.error(f"Ошибка при редактировании сообщения: {edit_error}")
            await query.message.reply_text(error_msg, reply_markup=keyboard)


async def show_deal_detail(query, deal_id: str, user_role_obj, telegram_id: str):
    """Показать детали сделки"""
    try:
        from sheets.operations import get_deal_data_from_sheet
        
        summary = get_deal_summary(deal_id)
        
        # Получаем данные сделки из таблицы для определения who_received_cash и amount_received
        deal_data = get_deal_data_from_sheet(deal_id)
        who_received_cash = deal_data.get("who_received_cash", "") if deal_data else ""
        amount_received = deal_data.get("amount_received") if deal_data else None
        transferred_to_assistant = deal_data.get("transferred_to_assistant", False) if deal_data else False
        
        message = get_deal_detail_message(summary, amount_received)
        
        current_stage = get_current_stage(deal_id)
        
        keyboard = get_deal_detail_keyboard(deal_id, user_role_obj.role, current_stage, who_received_cash, amount_received, transferred_to_assistant)
        
        try:
            await query.edit_message_text(message, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            # Если сообщение слишком длинное, сокращаем
            if len(message) > 4000:
                message = f"📄 Сделка: {deal_id[:50]}\n\n(Детали слишком длинные, используйте кнопки)"
            await query.edit_message_text(message, reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Ошибка при показе деталей сделки: {e}")
        error_msg = get_error_message(str(e))
        if len(error_msg) > 4000:
            error_msg = "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        keyboard = get_main_menu_keyboard()
        try:
            await query.edit_message_text(error_msg, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(error_msg, reply_markup=keyboard)




async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода суммы - показываем подтверждение"""
    user_id = update.effective_user.id
    
    if user_id not in user_context:
        await update.message.reply_text("Сессия истекла. Начните заново.")
        return
    
    context_data = user_context[user_id]
    deal_id = context_data["deal_id"]
    stage = context_data["stage"]
    user_role_obj = context_data["user_role"]
    
    # Проверяем, не введена ли уже сумма (чтобы избежать бесконечного цикла)
    if "amount" in context_data and context_data["amount"] is not None:
        # Сумма уже введена, показываем клавиатуру подтверждения снова
        from bot.messages import format_currency
        amount = context_data["amount"]
        stage_names = {
            config.STAGE_TRANSFERRED_TO_ASSISTANT: "передачи ассистенту",
            config.STAGE_ACCEPTED_BY_ASSISTANT: "получения от менеджера",
            config.STAGE_TRANSFERRED_TO_OWNER: "передачи собственнику",
            config.STAGE_ACCEPTED_BY_OWNER: "получения",
        }
        stage_name = stage_names.get(stage, stage)
        message = (
            f"📝 Подтверждение {stage_name}\n\n"
            f"Сделка: {deal_id}\n"
            f"Введенная сумма: {format_currency(amount)}\n\n"
            f"Используйте кнопку подтверждения ниже:"
        )
        keyboard = get_amount_confirmation_keyboard(amount)
        await update.message.reply_text(message, reply_markup=keyboard)
        return
    
    try:
        amount_str = update.message.text
        amount = validate_amount_string(amount_str)
        
        if amount is None:
            await update.message.reply_text(
                "Некорректная сумма. Введите положительное число:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Сохраняем сумму в контекст для подтверждения
        context_data["amount"] = amount
        
        # Показываем подтверждение суммы
        from bot.messages import format_currency
        
        stage_names = {
            config.STAGE_TRANSFERRED_TO_ASSISTANT: "передачи ассистенту",
            config.STAGE_ACCEPTED_BY_ASSISTANT: "получения от менеджера",
            config.STAGE_TRANSFERRED_TO_OWNER: "передачи собственнику",
            config.STAGE_ACCEPTED_BY_OWNER: "получения",
        }
        stage_name = stage_names.get(stage, stage)
        
        message = (
            f"📝 Подтверждение {stage_name}\n\n"
            f"Сделка: {deal_id}\n"
            f"Введенная сумма: {format_currency(amount)}\n\n"
            f"Подтвердите введенную сумму:"
        )
        
        keyboard = get_amount_confirmation_keyboard(amount)
        await update.message.reply_text(message, reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Ошибка при обработке суммы: {e}")
        error_msg = get_error_message(str(e))
        if len(error_msg) > 4000:
            error_msg = "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        keyboard = get_main_menu_keyboard()
        await update.message.reply_text(error_msg, reply_markup=keyboard)
        if user_id in user_context:
            del user_context[user_id]


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Если это ошибка таймаута, просто логируем
    if isinstance(context.error, Exception) and "TimedOut" in str(type(context.error)):
        logger.warning("Timeout error occurred, continuing...")
        return
    
    # Для других ошибок можно отправить сообщение пользователю
    if update and hasattr(update, 'effective_chat'):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Произошла ошибка. Пожалуйста, попробуйте еще раз."
            )
        except Exception:
            pass


def setup_handlers(application: Application):
    """Настройка обработчиков"""
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("my_deals", my_deals_command))
    
    # Callback query handler (для кнопок)
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handler для ввода суммы (должен быть после callback handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_input))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

