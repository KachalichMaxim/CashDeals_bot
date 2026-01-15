"""Кэш для ускорения работы с данными"""
from typing import List, Dict, Optional
from datetime import datetime
import threading
import logging

from sheets.models import Deal, UserRole
from sheets.operations import (
    COL_ALL_CASHLESS, COL_TRANSFERRED_TO_OWNER, COL_OWNER_ACCEPTED,
    COL_WHO_RECEIVED_CASH, COL_NAME, COL_TRANSFERRED_TO_ASSISTANT
)
from sheets.client import get_client
import config

logger = logging.getLogger(__name__)

# Глобальный кэш
_cache_lock = threading.Lock()
_deals_cache: Optional[List[Deal]] = None
_deals_cache_timestamp: Optional[datetime] = None
_debt_summary_cache: Optional[Dict] = None
_debt_summary_cache_timestamp: Optional[datetime] = None
_roles_cache: Dict[str, UserRole] = {}
_roles_cache_timestamp: Optional[datetime] = None

# Время жизни кэша (в секундах)
CACHE_TTL = 30  # 30 секунд


def _build_deal_id(row: List) -> str:
    """Построение DealID из строки таблицы"""
    from sheets.operations import COL_OWNER, COL_LOCATION, COL_NUMBER
    owner = str(row[COL_OWNER]).strip() if len(row) > COL_OWNER else ""
    location = str(row[COL_LOCATION]).strip() if len(row) > COL_LOCATION else ""
    number = str(row[COL_NUMBER]).strip() if len(row) > COL_NUMBER else ""
    return f"{owner}/{location}/{number}"


def _parse_deal_from_row(row: List, row_index: int) -> Optional[Deal]:
    """Парсинг сделки из строки таблицы"""
    from sheets.operations import (
        COL_OWNER, COL_LOCATION, COL_NUMBER, COL_ALL_CASHLESS,
        COL_WHO_RECEIVED_CASH, COL_AMOUNT_RECEIVED, COL_AMOUNT_ACCEPTED,
        COL_TRANSFERRED_TO_ASSISTANT, COL_TRANSFERRED_TO_OWNER,
        COL_OWNER_ACCEPTED, COL_DIFFERENCE
    )
    try:
        if len(row) <= COL_OWNER:
            return None
        
        deal_id = _build_deal_id(row)
        if not deal_id or deal_id == "//":
            return None
        
        all_cashless_str = str(row[COL_ALL_CASHLESS]).strip().lower() if len(row) > COL_ALL_CASHLESS else ""
        all_cashless = all_cashless_str in ["да", "yes", "true", "1"]
        
        who_received_cash = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
        
        amount_received_str = str(row[COL_AMOUNT_RECEIVED]).strip() if len(row) > COL_AMOUNT_RECEIVED else ""
        amount_received = None
        if amount_received_str:
            try:
                amount_received = float(amount_received_str.replace(",", ".").replace(" ", ""))
            except (ValueError, AttributeError):
                pass
        
        amount_accepted_str = str(row[COL_AMOUNT_ACCEPTED]).strip() if len(row) > COL_AMOUNT_ACCEPTED else ""
        amount_accepted = None
        if amount_accepted_str:
            try:
                amount_accepted = float(amount_accepted_str.replace(",", ".").replace(" ", ""))
            except (ValueError, AttributeError):
                pass
        
        transferred_to_assistant_str = str(row[COL_TRANSFERRED_TO_ASSISTANT]).strip().lower() if len(row) > COL_TRANSFERRED_TO_ASSISTANT else ""
        transferred_to_assistant = transferred_to_assistant_str in ["да", "yes", "true", "1"]
        
        transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
        transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
        
        owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
        owner_accepted = owner_accepted_str in ["да", "yes", "true", "1"]
        
        difference_str = str(row[COL_DIFFERENCE]).strip() if len(row) > COL_DIFFERENCE else ""
        difference = None
        if difference_str:
            try:
                difference = float(difference_str.replace(",", ".").replace(" ", ""))
            except (ValueError, AttributeError):
                pass
        
        deal = Deal(
            deal_id=deal_id,
            received_by_manager=amount_received,
            who_received_cash=who_received_cash,
            all_cashless=all_cashless,
            discrepancy=difference
        )
        
        if transferred_to_assistant:
            deal.transferred_to_assistant = amount_received
        if owner_accepted or transferred_to_owner:
            deal.transferred_to_owner = amount_accepted or amount_received
        if owner_accepted:
            deal.accepted_by_owner = amount_accepted
        
        deal.row_index = row_index + 2
        
        return deal
    except Exception as e:
        logger.warning(f"Ошибка при парсинге строки {row_index}: {e}")
        return None


def _load_all_deals() -> List[Deal]:
    """Загрузка всех сделок из таблицы"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            return []
        
        deals = []
        for idx, row in enumerate(all_values[1:], start=1):
            deal = _parse_deal_from_row(row, idx)
            if deal:
                deals.append(deal)
        
        logger.info(f"Загружено {len(deals)} сделок в кэш")
        return deals
    except Exception as e:
        logger.error(f"Ошибка при загрузке сделок: {e}")
        return []


def _load_all_roles() -> Dict[str, UserRole]:
    """Загрузка всех ролей из таблицы"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_ROLES)
        all_values = worksheet.get_all_values()
        
        if not all_values:
            return {}
        
        headers = all_values[0]
        
        # Ищем колонки
        telegram_id_col = None
        role_col = None
        fio_col = None
        predstavites_col = None
        
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if 'telegram' in header_lower or ('id' in header_lower and 'telegram' in header_lower):
                telegram_id_col = idx
            elif 'роль' in header_lower:
                role_col = idx
            elif 'фио' in header_lower:
                fio_col = idx
            elif 'представьтесь' in header_lower:
                predstavites_col = idx
        
        if telegram_id_col is None:
            return {}
        
        roles = {}
        for row in all_values[1:]:
            if len(row) > telegram_id_col:
                telegram_id = str(row[telegram_id_col])
                role = str(row[role_col]) if role_col is not None and len(row) > role_col else config.ROLE_NULL
                name = str(row[fio_col]) if fio_col is not None and len(row) > fio_col else None
                predstavites = str(row[predstavites_col]) if predstavites_col is not None and len(row) > predstavites_col else None
                roles[telegram_id] = UserRole(telegram_id=telegram_id, name=name, role=role, predstavites=predstavites)
        
        logger.info(f"Загружено {len(roles)} ролей в кэш")
        return roles
    except Exception as e:
        logger.error(f"Ошибка при загрузке ролей: {e}")
        return {}


def get_cached_deals(force_refresh: bool = False) -> List[Deal]:
    """Получение всех сделок из кэша"""
    global _deals_cache, _deals_cache_timestamp
    
    with _cache_lock:
        now = datetime.now()
        
        # Проверяем, нужно ли обновить кэш
        if (_deals_cache is None or 
            _deals_cache_timestamp is None or 
            force_refresh or
            (now - _deals_cache_timestamp).total_seconds() > CACHE_TTL):
            
            _deals_cache = _load_all_deals()
            _deals_cache_timestamp = now
        
        return _deals_cache.copy() if _deals_cache else []


def get_cached_user_role(telegram_id: str, force_refresh: bool = False) -> Optional[UserRole]:
    """Получение роли пользователя из кэша"""
    global _roles_cache, _roles_cache_timestamp
    
    with _cache_lock:
        now = datetime.now()
        
        # Проверяем, нужно ли обновить кэш
        if (_roles_cache is None or 
            _roles_cache_timestamp is None or 
            force_refresh or
            (now - _roles_cache_timestamp).total_seconds() > CACHE_TTL):
            
            _roles_cache = _load_all_roles()
            _roles_cache_timestamp = now
        
        return _roles_cache.get(str(telegram_id), UserRole(telegram_id=str(telegram_id)))


def invalidate_cache():
    """Инвалидация кэша (принудительное обновление при следующем запросе)"""
    global _deals_cache_timestamp, _debt_summary_cache_timestamp, _roles_cache_timestamp
    
    with _cache_lock:
        _deals_cache_timestamp = None
        _debt_summary_cache_timestamp = None
        _roles_cache_timestamp = None
        logger.info("Кэш инвалидирован")


def get_cached_user_deals(telegram_id: str, role: str, force_refresh: bool = False) -> List[Deal]:
    """Получение сделок пользователя с использованием кэша"""
    
    all_deals = get_cached_deals(force_refresh)
    user_role_obj = get_cached_user_role(telegram_id, force_refresh)
    predstavites_name = user_role_obj.predstavites if user_role_obj else None
    
    deals = []
    
    # Получаем данные из таблицы для фильтрации (используем кэш, но нужны дополнительные данные)
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            return []
        
        # Создаем словарь deal_id -> row для быстрого доступа
        deal_id_to_row = {}
        for idx, row in enumerate(all_values[1:], start=1):
            deal_id = _build_deal_id(row)
            if deal_id and deal_id != "//":
                deal_id_to_row[deal_id] = row
        
        # Фильтруем сделки
        for deal in all_deals:
            if deal.all_cashless:
                continue
            
            row = deal_id_to_row.get(deal.deal_id)
            if not row:
                continue
            
            # Фильтрация по роли
            if role == config.ROLE_OWNER:
                transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
                owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
                
                transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
                owner_accepted = owner_accepted_str in ["да", "yes", "true", "1"]
                
                if not transferred_to_owner or not owner_accepted:
                    deals.append(deal)
            
            elif role == config.ROLE_MANAGER:
                who_received = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
                
                if who_received.lower() in ["не получали", ""]:
                    continue
                
                if predstavites_name and predstavites_name.strip():
                    if who_received.lower() == predstavites_name.strip().lower():
                        deals.append(deal)
                else:
                    manager_name = str(row[COL_NAME]).strip() if len(row) > COL_NAME else ""
                    if manager_name and who_received.lower() == manager_name.lower():
                        deals.append(deal)
            
            elif role == config.ROLE_ASSISTANT:
                transferred_to_assistant_str = str(row[COL_TRANSFERRED_TO_ASSISTANT]).strip().lower() if len(row) > COL_TRANSFERRED_TO_ASSISTANT else ""
                transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
                
                transferred_to_assistant = transferred_to_assistant_str in ["да", "yes", "true", "1"]
                transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
                
                if transferred_to_assistant and not transferred_to_owner:
                    deals.append(deal)
    
    except Exception as e:
        logger.error(f"Ошибка при получении сделок пользователя из кэша: {e}")
        return []
    
    return deals

