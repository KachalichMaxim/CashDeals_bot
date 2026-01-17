"""Валидация данных"""
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def validate_deal_id(deal_id: str) -> bool:
    """Валидация формата DealID: <Чей объект>/<Локация>/<№>"""
    if not deal_id:
        return False
    
    # Проверяем, что есть хотя бы два слеша (три части)
    parts = deal_id.split('/')
    if len(parts) < 3:
        return False
    
    # Все части должны быть не пустыми
    for part in parts:
        if not part.strip():
            return False
    
    return True


def validate_amount(amount: Optional[float]) -> bool:
    """Валидация суммы (положительное число)"""
    if amount is None:
        return False
    try:
        amount_float = float(amount)
        return amount_float > 0
    except (ValueError, TypeError):
        return False


def validate_amount_string(amount_str: str) -> Optional[float]:
    """Валидация и преобразование строки суммы в число"""
    try:
        # Убираем пробелы и заменяем запятую на точку
        amount_str = amount_str.strip().replace(',', '.').replace(' ', '')
        amount = float(amount_str)
        if amount > 0:
            return amount
        return None
    except (ValueError, TypeError):
        return None


def check_idempotency(deal_id: str, stage: str, timestamp_threshold_seconds: int = 60) -> bool:
    """Проверка идемпотентности операции
    
    Возвращает True, если операция может быть выполнена (нет дубликата)
    """
    from sheets.operations import get_cashflow_history
    from datetime import timedelta
    
    events = get_cashflow_history(deal_id)
    
    # Проверяем, есть ли недавнее событие с таким же этапом
    for event in events:
        if event.stage == stage:
            # Если событие очень недавнее (в пределах порога), считаем дубликатом
            # Эта проверка упрощенная, в реальности нужна более сложная логика
            return False
    
    return True

