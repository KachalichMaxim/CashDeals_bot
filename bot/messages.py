"""Шаблоны сообщений для Telegram бота"""
from typing import Dict, List
import config
from sheets.models import CashFlowEvent


def format_currency(amount: float) -> str:
    """Форматирование суммы"""
    return f"{amount:,.2f} ₽".replace(",", " ")


def get_welcome_message(user_name: str, role: str) -> str:
    """Приветственное сообщение"""
    role_text = {
        config.ROLE_MANAGER: "менеджер",
        config.ROLE_ASSISTANT: "ассистент",
        config.ROLE_OWNER: "собственник",
    }.get(role, "пользователь")
    
    return f"""👋 Добро пожаловать, {user_name}!

Ваша роль: {role_text}"""


def get_deals_list_message(deals: List, page: int = 0, debt_summary: Dict = None) -> str:
    """Сообщение со списком сделок"""
    if not deals:
        if debt_summary:
            # Показываем сводку по долгам для собственника
            return get_debt_summary_message(debt_summary)
        return "У вас пока нет сделок."
    
    # Только краткое сообщение, список показывается кнопками
    message = "📋 Выберите сделку:"
    
    # Добавляем сводку по долгам для собственника (если есть)
    if debt_summary:
        message += "\n\n" + get_debt_summary_message(debt_summary)
    
    return message


def get_debt_summary_message(debt_summary: Dict[str, Dict]) -> str:
    """Сообщение со сводкой по долгам"""
    if not debt_summary:
        return "Долгов нет."
    
    # Ограничиваем длину сообщения (Telegram лимит ~4096 символов)
    message = "💰 Долги по менеджерам:\n\n"
    total_debt = 0.0
    
    sorted_managers = sorted(debt_summary.items(), key=lambda x: x[1]["total_debt"], reverse=True)
    
    for manager_name, data in sorted_managers:
        total = data["total_debt"]
        count = data["deals_count"]
        total_debt += total
        
        # Сокращаем имя менеджера если слишком длинное
        display_name = manager_name[:30] + "..." if len(manager_name) > 30 else manager_name
        
        manager_info = f"👤 {display_name}:\n   {format_currency(total)} ({count} сделок)\n\n"
        
        # Проверяем, не превысит ли добавление этого менеджера лимит
        if len(message) + len(manager_info) + 50 > 3500:  # Оставляем место для итога
            message += "...\n(показаны не все менеджеры)\n\n"
            break
        
        message += manager_info
    
    message += f"📊 Общий долг: {format_currency(total_debt)}"
    
    return message


def get_deal_detail_message(summary: Dict, amount_received: float = None) -> str:
    """Детальная информация о сделке"""
    deal_id = summary.get("deal_id", "Неизвестно")
    display_deal_id = deal_id[:50] + "..." if len(deal_id) > 50 else deal_id
    message = f"📄 Сделка: {display_deal_id}\n\n"
    
    # Показываем сумму денег в сделке
    received = summary.get("received_by_manager") or amount_received
    if received is not None:
        message += f"💰 Сумма: {format_currency(received)}\n\n"
    else:
        message += "💰 Сумма: не указана\n\n"
    
    # Показываем статус
    status = summary.get("status", config.STATUS_IN_PROGRESS)
    status_emoji = {
        config.STATUS_COMPLETE: "✅",
        config.STATUS_DISCREPANCY: "⚠️",
        config.STATUS_IN_PROGRESS: "⏳"
    }.get(status, "⏳")
    
    message += f"{status_emoji} Статус: {status}"
    
    return message


def get_cashflow_chain_message(deal_id: str, summary: Dict) -> str:
    """Сообщение с полной цепочкой движения денег"""
    from sheets.operations import get_cashflow_history
    
    display_deal_id = deal_id[:50] + "..." if len(deal_id) > 50 else deal_id
    message = f"📄 Сделка: {display_deal_id}\n\n"
    
    # Получаем историю для определения пользователей
    events = get_cashflow_history(deal_id)
    
    # Находим суммы и пользователей на каждом этапе
    received_by_manager = summary.get("received_by_manager")
    accepted_by_assistant = summary.get("accepted_by_assistant")
    accepted_by_owner = summary.get("accepted_by_owner")
    
    # Находим пользователей и их имена из "Представьтесь"
    from sheets.operations import get_user_role
    
    manager_user = None
    assistant_user = None
    owner_user = None
    
    # Словарь для кэширования имен по Telegram ID
    user_names_cache = {}
    
    def get_display_name(user_identifier: str) -> str:
        """Получает имя из колонки 'Представьтесь' по Telegram ID или имени"""
        if user_identifier in user_names_cache:
            return user_names_cache[user_identifier]
        
        # Пытаемся найти пользователя по Telegram ID
        # user_identifier может быть Telegram ID (число как строка) или именем
        try:
            user_role_obj = get_user_role(user_identifier)
            if user_role_obj and user_role_obj.predstavites and user_role_obj.predstavites.strip():
                name = user_role_obj.predstavites.strip()
                user_names_cache[user_identifier] = name
                return name
        except Exception:
            pass
        
        # Если не нашли по Telegram ID, пытаемся найти по имени в таблице ролей
        # (для старых событий, где сохранено имя из Telegram)
        try:
            from sheets.client import get_client
            client = get_client()
            worksheet = client.get_worksheet(config.SHEET_ROLES)
            all_values = worksheet.get_all_values()
            
            if all_values:
                headers = all_values[0]
                predstavites_col = None
                fio_col = None
                
                for idx, header in enumerate(headers):
                    header_lower = header.lower()
                    if 'представьтесь' in header_lower:
                        predstavites_col = idx
                    elif 'фио' in header_lower:
                        fio_col = idx
                
                # Ищем пользователя по имени в колонке ФИО или Представьтесь
                for row in all_values[1:]:
                    if fio_col is not None and len(row) > fio_col:
                        if str(row[fio_col]).strip().lower() == user_identifier.lower():
                            if predstavites_col is not None and len(row) > predstavites_col:
                                name = str(row[predstavites_col]).strip()
                                if name:
                                    user_names_cache[user_identifier] = name
                                    return name
        except Exception:
            pass
        
        # Если не нашли, используем переданное имя как есть
        user_names_cache[user_identifier] = user_identifier
        return user_identifier
    
    for event in sorted(events, key=lambda x: x.timestamp):
        if event.stage == config.STAGE_RECEIVED_BY_MANAGER and not manager_user:
            manager_user = get_display_name(event.user)
        elif event.stage == config.STAGE_ACCEPTED_BY_ASSISTANT and not assistant_user:
            assistant_user = get_display_name(event.user)
        elif event.stage == config.STAGE_ACCEPTED_BY_OWNER and not owner_user:
            owner_user = get_display_name(event.user)
    
    # Формируем сообщение
    message += "💰 Движение денежных средств:\n\n"
    
    if received_by_manager is not None:
        manager_name = manager_user or "Менеджер"
        message += f"👤 Получил менеджер ({manager_name}): {format_currency(received_by_manager)}\n"
    
    if accepted_by_assistant is not None:
        assistant_name = assistant_user or "Ассистент"
        message += f"👤 Получил ассистент ({assistant_name}): {format_currency(accepted_by_assistant)}\n"
    
    if accepted_by_owner is not None:
        owner_name = owner_user or "Собственник"
        message += f"👤 Принял собственник ({owner_name}): {format_currency(accepted_by_owner)}\n"
    
    # Показываем расхождения если есть
    discrepancies = summary.get("discrepancies", {})
    if discrepancies:
        message += "\n⚠️ Расхождения:\n"
        if "assistant" in discrepancies:
            diff = discrepancies["assistant"]
            message += f"   Менеджер → Ассистент: {format_currency(abs(diff))} "
            message += "(" + ("недополучено" if diff > 0 else "переполучено") + ")\n"
        if "owner" in discrepancies:
            diff = discrepancies["owner"]
            message += f"   Ассистент → Собственник: {format_currency(abs(diff))} "
            message += "(" + ("недополучено" if diff > 0 else "переполучено") + ")\n"
    
    # Статус
    status = summary.get("status", config.STATUS_IN_PROGRESS)
    status_emoji = {
        config.STATUS_COMPLETE: "✅",
        config.STATUS_DISCREPANCY: "⚠️",
        config.STATUS_IN_PROGRESS: "⏳"
    }.get(status, "⏳")
    
    message += f"\n{status_emoji} Статус: {status}"
    
    return message


def get_cashflow_history_message(deal_id: str, events: List[CashFlowEvent]) -> str:
    """Сообщение с историей движения средств"""
    display_deal_id = deal_id[:50] + "..." if len(deal_id) > 50 else deal_id
    message = f"📜 История: {display_deal_id}\n\n"
    
    if not events:
        return message + "История пуста."
    
    for event in events[:20]:  # Ограничиваем 20 событиями
        timestamp = event.timestamp.strftime("%d.%m.%Y %H:%M")
        stage_short = event.stage[:30] + "..." if len(event.stage) > 30 else event.stage
        user_short = event.user[:20] + "..." if len(event.user) > 20 else event.user
        
        event_text = f"🕐 {timestamp}\n   {stage_short}\n   {user_short}: {format_currency(event.amount)}\n\n"
        
        # Проверяем длину
        if len(message) + len(event_text) > 3500:
            message += "...\n(показаны не все события)"
            break
        
        message += event_text
    
    return message


def get_stage_confirmation_message(stage: str, deal_id: str, previous_amount: float = None) -> str:
    """Сообщение для подтверждения этапа"""
    stage_names = {
        config.STAGE_TRANSFERRED_TO_ASSISTANT: "передачи ассистенту",
        config.STAGE_ACCEPTED_BY_ASSISTANT: "получения от менеджера",
        config.STAGE_TRANSFERRED_TO_OWNER: "передачи собственнику",
        config.STAGE_ACCEPTED_BY_OWNER: "получения",
    }
    
    stage_name = stage_names.get(stage, stage)
    message = f"📝 Подтверждение {stage_name}\n\n"
    message += f"Сделка: {deal_id}\n"
    
    if previous_amount is not None:
        message += f"Заявленная сумма: {format_currency(previous_amount)}\n"
        message += "Введите фактическую сумму:\n"
    else:
        message += "Введите сумму:\n"
    
    return message


def get_error_message(error: str) -> str:
    """Сообщение об ошибке"""
    return f"❌ Ошибка: {error}\n\nПожалуйста, попробуйте еще раз или обратитесь к администратору."


def get_success_message(action: str) -> str:
    """Сообщение об успешном действии"""
    return f"✅ {action} выполнено успешно!"


def get_notification_message(deal_id: str, stage: str, amount: float, from_user: str) -> str:
    """Уведомление о передаче денег"""
    stage_names = {
        config.STAGE_TRANSFERRED_TO_ASSISTANT: "передал вам",
        config.STAGE_TRANSFERRED_TO_OWNER: "передал вам",
    }
    
    stage_name = stage_names.get(stage, "передал")
    message = f"🔔 Уведомление\n\n"
    message += f"{from_user} {stage_name} наличные средства.\n\n"
    message += f"Сделка: {deal_id}\n"
    message += f"Сумма: {format_currency(amount)}\n\n"
    message += "Пожалуйста, подтвердите получение."
    
    return message

