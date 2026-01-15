"""Система уведомлений"""
import logging
from typing import Optional
from telegram import Bot
from sheets.operations import get_user_role, get_cashflow_history
from business.cashflow import get_next_stage
from bot.keyboards import get_deal_detail_keyboard
from bot.messages import format_currency
import config

logger = logging.getLogger(__name__)


async def send_notification(
    bot: Bot,
    telegram_id: str,
    deal_id: str,
    stage: str,
    amount: float,
    from_user: str
) -> bool:
    """Отправка уведомления пользователю"""
    try:
        from sheets.operations import get_deal_data_from_sheet
        from business.cashflow import get_current_stage
        
        # Формируем сообщение
        stage_text = {
            config.STAGE_TRANSFERRED_TO_ASSISTANT: "переданы ассистенту",
            config.STAGE_TRANSFERRED_TO_OWNER: "переданы собственнику",
            config.STAGE_ACCEPTED_BY_ASSISTANT: "приняты ассистентом",
            config.STAGE_ACCEPTED_BY_OWNER: "приняты собственником"
        }.get(stage, "изменены")
        
        message = f"🔔 Уведомление\n\n"
        message += f"Сделка: {deal_id}\n"
        message += f"Деньги {stage_text}\n"
        message += f"Сумма: {format_currency(amount)}\n"
        message += f"От: {from_user}"
        
        # Получаем данные для клавиатуры
        deal_data = get_deal_data_from_sheet(deal_id)
        who_received_cash = deal_data.get("who_received_cash", "") if deal_data else ""
        amount_received = deal_data.get("amount_received") if deal_data else None
        transferred_to_assistant = deal_data.get("transferred_to_assistant", False) if deal_data else False
        
        current_stage = get_current_stage(deal_id)
        
        # Определяем роль получателя для правильной клавиатуры
        from sheets.operations import get_user_role
        user_role_obj = get_user_role(telegram_id)
        
        keyboard = get_deal_detail_keyboard(deal_id, user_role_obj.role, current_stage, who_received_cash, amount_received, transferred_to_assistant)
        
        await bot.send_message(
            chat_id=int(telegram_id),
            text=message,
            reply_markup=keyboard
        )
        
        logger.info(f"Уведомление отправлено пользователю {telegram_id} о сделке {deal_id}")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")
        return False


async def notify_next_participant(
    bot: Bot,
    deal_id: str,
    stage: str,
    amount: float,
    from_user: str
) -> bool:
    """Уведомление следующего участника цепочки"""
    try:
        # Определяем, кому отправлять уведомление
        next_stage = get_next_stage(stage)
        
        if next_stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
            # Уведомляем ассистента
            # Нужно найти Telegram ID ассистента
            # Упрощенная версия: ищем всех с ролью ассистента
            # В реальности нужно найти конкретного ассистента для сделки
            return True
        
        elif next_stage == config.STAGE_TRANSFERRED_TO_OWNER or next_stage == config.STAGE_ACCEPTED_BY_OWNER:
            # Уведомляем собственника
            # Нужно найти Telegram ID собственника
            # Упрощенная версия: ищем всех с ролью собственника
            # В реальности должен быть один собственник
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Ошибка при уведомлении следующего участника: {e}")
        return False


def get_telegram_ids_by_role(role: str) -> list:
    """Получение списка Telegram ID пользователей с указанной ролью"""
    try:
        from sheets.client import get_client
        from sheets.operations import get_user_role
        import config
        
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_ROLES)
        all_values = worksheet.get_all_values()
        
        if not all_values:
            return []
        
        headers = all_values[0]
        
        # Ищем колонки
        telegram_id_col = None
        role_col = None
        
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if 'telegram' in header_lower or ('id' in header_lower and 'telegram' in header_lower):
                telegram_id_col = idx
            elif 'роль' in header_lower:
                role_col = idx
        
        if telegram_id_col is None or role_col is None:
            return []
        
        telegram_ids = []
        for row in all_values[1:]:
            if len(row) > max(telegram_id_col, role_col):
                row_role = str(row[role_col]).strip() if len(row) > role_col else ""
                if row_role.lower() == role.lower():
                    telegram_id = str(row[telegram_id_col]).strip() if len(row) > telegram_id_col else ""
                    if telegram_id:
                        telegram_ids.append(telegram_id)
        
        return telegram_ids
    
    except Exception as e:
        logger.error(f"Ошибка при получении Telegram ID по роли {role}: {e}")
        return []

