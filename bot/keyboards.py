"""Клавиатуры для Telegram бота"""
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config


def get_main_menu_keyboard(has_rental_objects: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("Мои сделки", callback_data="my_deals")],
    ]
    if has_rental_objects:
        keyboard.append([InlineKeyboardButton("🏠 Аренда", callback_data="rental_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_deals_list_keyboard(deals: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Список сделок с пагинацией"""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_deals = deals[start_idx:end_idx]
    
    for idx, deal in enumerate(page_deals):
        deal_id = deal.deal_id if hasattr(deal, 'deal_id') else str(deal)
        # Ограничиваем длину текста кнопки
        button_text = deal_id[:40] + "..." if len(deal_id) > 40 else deal_id
        
        # Используем индекс вместо полного deal_id для callback_data (лимит 64 байта)
        # Создаем короткий идентификатор
        deal_hash = hash(deal_id) % 1000000  # Хеш для короткого ID
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"deal_{deal_hash}_{page}_{idx}")])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀ Назад", callback_data=f"deals_page_{page - 1}"))
    if end_idx < len(deals):
        nav_buttons.append(InlineKeyboardButton("Вперед ▶", callback_data=f"deals_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("↩ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_deal_detail_keyboard(deal_id: str, user_role: str, current_stage: str = None, who_received_cash: str = None, amount_received: float = None, transferred_to_assistant: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для детального просмотра сделки"""
    keyboard = []
    
    # Используем хеш для короткого идентификатора (лимит callback_data 64 байта)
    deal_hash = hash(deal_id) % 1000000
    
    # Определяем доступные действия в зависимости от роли и этапа
    if user_role == config.ROLE_MANAGER:
        # Менеджер может передать деньги ассистенту или собственнику
        # Показываем кнопку "Передать ДС" только если деньги получены менеджером
        if who_received_cash and who_received_cash.lower() not in ["не получали", ""] and amount_received:
            # Менеджер получил деньги, может передать
            keyboard.append([InlineKeyboardButton("💰 Передать ДС", callback_data=f"transfer_{deal_hash}")])
    
    elif user_role == config.ROLE_ASSISTANT:
        # Ассистент может принять от менеджера или передать собственнику
        if current_stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
            # Нужно принять от менеджера
            stage_hash = hash(config.STAGE_ACCEPTED_BY_ASSISTANT) % 10000
            keyboard.append([InlineKeyboardButton("✅ Принять от менеджера", callback_data=f"conf_{deal_hash}_{stage_hash}")])
        elif current_stage == config.STAGE_ACCEPTED_BY_ASSISTANT or transferred_to_assistant:
            # Может передать собственнику (если принял деньги)
            stage_hash = hash(config.STAGE_TRANSFERRED_TO_OWNER) % 10000
            keyboard.append([InlineKeyboardButton("💰 Передать собственнику", callback_data=f"conf_{deal_hash}_{stage_hash}")])
    
    elif user_role == config.ROLE_OWNER:
        # Собственник может только принять
        if current_stage == config.STAGE_TRANSFERRED_TO_OWNER:
            stage_hash = hash(config.STAGE_ACCEPTED_BY_OWNER) % 10000
            keyboard.append([InlineKeyboardButton("✅ Принять", callback_data=f"conf_{deal_hash}_{stage_hash}")])
    
    keyboard.append([InlineKeyboardButton("📋 История", callback_data=f"hist_{deal_hash}")])
    keyboard.append([InlineKeyboardButton("↩ К списку сделок", callback_data="my_deals")])
    
    return InlineKeyboardMarkup(keyboard)


def get_transfer_recipient_keyboard(deal_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для выбора получателя при передаче ДС"""
    deal_hash = hash(deal_id) % 1000000
    
    stage_hash_assistant = hash(config.STAGE_TRANSFERRED_TO_ASSISTANT) % 10000
    stage_hash_owner = hash(config.STAGE_TRANSFERRED_TO_OWNER) % 10000
    
    keyboard = [
        [
            InlineKeyboardButton("👤 Ассистент", callback_data=f"conf_{deal_hash}_{stage_hash_assistant}"),
            InlineKeyboardButton("👤 Собственник", callback_data=f"conf_{deal_hash}_{stage_hash_owner}")
        ],
        [InlineKeyboardButton("↩ Назад", callback_data=f"deal_{deal_hash}_0_0")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отмены действия"""
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(deal_id: str, stage: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения действия"""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_final_{deal_id}_{stage}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_amount_confirmation_keyboard(amount: float) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения введенной суммы"""
    # Используем хеш суммы для callback_data
    amount_hash = hash(str(amount)) % 1000000
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить сумму", callback_data=f"confirm_amount_{amount_hash}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rental_add_payment_keyboard(addresses: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура для добавления оплаты аренды (выбор адреса)"""
    keyboard = []
    for address in addresses:
        # Используем хеш адреса для callback_data
        address_hash = hash(address) % 1000000
        keyboard.append([InlineKeyboardButton(f"📍 {address}", callback_data=f"rental_address_{address_hash}")])
    keyboard.append([InlineKeyboardButton("↩ Назад", callback_data="rental_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_rental_mm_keyboard(address: str, mm_objects: List) -> InlineKeyboardMarkup:
    """Клавиатура для выбора М/М по адресу"""
    keyboard = []
    address_hash = hash(address) % 1000000
    for mm_obj in mm_objects:
        mm_hash = hash(f"{address}_{mm_obj.mm_number}") % 1000000
        button_text = f"🏠 М/М {mm_obj.mm_number}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"rental_mm_{address_hash}_{mm_hash}")])
    keyboard.append([InlineKeyboardButton("↩ Назад", callback_data="rental_menu")])
    return InlineKeyboardMarkup(keyboard)

