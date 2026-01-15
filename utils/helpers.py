"""Вспомогательные функции"""
from datetime import datetime
from typing import Optional


def format_datetime(dt: datetime) -> str:
    """Форматирование даты и времени"""
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def parse_deal_id_from_form_data(row_data: dict) -> Optional[str]:
    """Извлечение DealID из данных формы
    
    Формат DealID: <Чей объект>/<Локация>/<№>
    """
    # Предполагаем, что колонки могут называться по-разному
    # Это упрощенная версия, нужно адаптировать под реальную структуру формы
    
    owner = row_data.get("Чей объект", "") or row_data.get("чей объект", "")
    location = row_data.get("Локация", "") or row_data.get("локация", "")
    number = row_data.get("№ ММ/квартиры/участка", "") or row_data.get("№", "") or row_data.get("номер", "")
    
    if owner and location and number:
        return f"{owner}/{location}/{number}"
    
    return None

