"""Логика движения наличных"""
from typing import Optional, Dict, List
from datetime import datetime
import logging

from sheets.operations import get_cashflow_history, create_cashflow_event, calculate_discrepancies
from sheets.models import Deal, CashFlowEvent
import config

logger = logging.getLogger(__name__)


def get_current_stage(deal_id: str) -> Optional[str]:
    """Определение текущего этапа сделки"""
    events = get_cashflow_history(deal_id)
    
    if not events:
        return None
    
    # Находим последний завершенный этап
    stages_order = [
        config.STAGE_RECEIVED_BY_MANAGER,
        config.STAGE_TRANSFERRED_TO_ASSISTANT,
        config.STAGE_ACCEPTED_BY_ASSISTANT,
        config.STAGE_TRANSFERRED_TO_OWNER,
        config.STAGE_ACCEPTED_BY_OWNER,
    ]
    
    last_stage = None
    for event in sorted(events, key=lambda x: x.timestamp):
        if event.stage in stages_order:
            last_stage = event.stage
    
    return last_stage


def should_skip_stages(deal_data: Dict) -> Dict[str, bool]:
    """Определение, нужно ли пропускать этапы
    
    Возвращает словарь с флагами:
    - skip_assistant: пропустить этапы с ассистентом
    - all_cashless: все по безналу
    """
    who_received = deal_data.get("who_received_cash", "").strip().lower()
    all_cashless = deal_data.get("all_cashless", False)
    
    return {
        "skip_assistant": who_received == "собственник",
        "all_cashless": all_cashless or (deal_data.get("all_cashless_str", "").lower() in ["да", "yes", "true"])
    }


def check_all_cashless(deal_data: Dict) -> bool:
    """Проверка, все ли по безналу"""
    result = should_skip_stages(deal_data)
    return result["all_cashless"]


def process_stage_transition(
    deal_id: str,
    from_stage: str,
    to_stage: str,
    amount: float,
    user: str,
    role: str
) -> bool:
    """Обработка перехода между этапами"""
    try:
        from sheets.operations import update_deal_status_with_role
        
        # Обновляем статус в основной таблице и создаем событие с ролью
        success = update_deal_status_with_role(deal_id, to_stage, amount, user, role)
        
        return success
    
    except Exception as e:
        logger.error(f"Ошибка при обработке перехода этапа: {e}")
        return False


def get_next_stage(current_stage: Optional[str], skip_assistant: bool = False) -> Optional[str]:
    """Получение следующего этапа"""
    if current_stage is None:
        return config.STAGE_RECEIVED_BY_MANAGER
    
    stage_sequence = [
        config.STAGE_RECEIVED_BY_MANAGER,
        config.STAGE_TRANSFERRED_TO_ASSISTANT,
        config.STAGE_ACCEPTED_BY_ASSISTANT,
        config.STAGE_TRANSFERRED_TO_OWNER,
        config.STAGE_ACCEPTED_BY_OWNER,
    ]
    
    if skip_assistant:
        # Пропускаем этапы с ассистентом
        stage_sequence = [
            config.STAGE_RECEIVED_BY_MANAGER,
            config.STAGE_TRANSFERRED_TO_OWNER,
            config.STAGE_ACCEPTED_BY_OWNER,
        ]
    
    try:
        current_index = stage_sequence.index(current_stage)
        if current_index < len(stage_sequence) - 1:
            return stage_sequence[current_index + 1]
    except ValueError:
        pass
    
    return None


def get_deal_summary(deal_id: str) -> Dict:
    """Получение сводки по сделке: суммы на каждом этапе и расхождения"""
    events = get_cashflow_history(deal_id)
    
    summary = {
        "deal_id": deal_id,
        "received_by_manager": None,
        "transferred_to_assistant": None,
        "accepted_by_assistant": None,
        "transferred_to_owner": None,
        "accepted_by_owner": None,
        "discrepancies": {},
        "status": config.STATUS_IN_PROGRESS
    }
    
    # Собираем суммы по этапам
    for event in events:
        if event.stage == config.STAGE_RECEIVED_BY_MANAGER:
            summary["received_by_manager"] = event.amount
        elif event.stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
            summary["transferred_to_assistant"] = event.amount
        elif event.stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
            summary["accepted_by_assistant"] = event.amount
        elif event.stage == config.STAGE_TRANSFERRED_TO_OWNER:
            summary["transferred_to_owner"] = event.amount
        elif event.stage == config.STAGE_ACCEPTED_BY_OWNER:
            summary["accepted_by_owner"] = event.amount
    
    # Рассчитываем расхождения
    discrepancies = calculate_discrepancies(deal_id)
    summary["discrepancies"] = discrepancies
    
    # Определяем статус
    if summary["accepted_by_owner"] is not None:
        if discrepancies:
            summary["status"] = config.STATUS_DISCREPANCY
        else:
            summary["status"] = config.STATUS_COMPLETE
    elif discrepancies:
        summary["status"] = config.STATUS_DISCREPANCY
    
    return summary

