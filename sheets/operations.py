"""Операции чтения/записи в Google Sheets"""
from typing import List, Optional, Dict
import gspread
from datetime import datetime
import logging

from sheets.client import get_client
from sheets.models import Deal, CashFlowEvent, UserRole
import config

logger = logging.getLogger(__name__)

# Индексы колонок в листе "Ответы на форму (1)"
COL_TIMESTAMP = 0  # Отметка времени
COL_NAME = 1  # Представьтесь (имя менеджера)
COL_CHANNEL = 2  # Канал с которого пришел клиент
COL_OWNER = 3  # чей объект
COL_LOCATION = 4  # Локация
COL_CONTRACT = 5  # Договор купли-продажи
COL_NUMBER = 6  # № ММ/квартиры/участка
COL_DATE_DS = 7  # Дата поступления ДС
COL_REAL_PRICE = 8  # Реальная цена продажи
COL_PRICE_DKP = 9  # Цена продажи в ДКП
COL_ALL_CASHLESS = 10  # Вся сумма по безналу?
COL_WHO_RECEIVED_CASH = 11  # Кто получил нал?
COL_AMOUNT_RECEIVED = 12  # В какой сумме получен нал
COL_TRANSFERRED_TO_ASSISTANT = 13  # Передано ассистенту? (Да/Нет)
COL_TRANSFERRED_TO_OWNER = 14  # Передано собственнику? (Да/Нет)
COL_OWNER_ACCEPTED = 15  # Собственник принял? (Да/Нет)
COL_AMOUNT_ACCEPTED = 16  # Сумма принято наличных
COL_DIFFERENCE = 17  # Разница получено-принято


def add_user_to_roles(telegram_id: str, name: str) -> bool:
    """Добавление пользователя в таблицу ролей (если его там нет)"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_ROLES)
        all_values = worksheet.get_all_values()
        
        if not all_values:
            # Лист пустой, добавляем заголовки и пользователя
            headers = ["ФИО", "Представьтесь", "Telegram ID", "Роль"]
            worksheet.insert_row(headers, 1)
            worksheet.insert_row([name, "", telegram_id, config.ROLE_NULL], 2)
            logger.info(f"Пользователь {telegram_id} добавлен в таблицу ролей")
            return True
        
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
            logger.warning("Колонка Telegram ID не найдена в таблице ролей")
            return False
        
        # Проверяем, есть ли уже пользователь
        for row_idx, row in enumerate(all_values[1:], start=2):
            if len(row) > telegram_id_col and str(row[telegram_id_col]) == str(telegram_id):
                # Пользователь уже есть, обновляем ФИО если нужно
                if fio_col is not None and len(row) > fio_col and not row[fio_col]:
                    worksheet.update_cell(row_idx, fio_col + 1, name)
                return True
        
        # Пользователя нет, добавляем
        new_row = [""] * len(headers)
        if fio_col is not None:
            new_row[fio_col] = name
        if predstavites_col is not None:
            new_row[predstavites_col] = ""  # Будет заполнено вручную для сопоставления
        new_row[telegram_id_col] = telegram_id
        if role_col is not None:
            new_row[role_col] = config.ROLE_NULL
        
        worksheet.append_row(new_row)
        logger.info(f"Пользователь {telegram_id} добавлен в таблицу ролей")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя {telegram_id} в таблицу ролей: {e}")
        return False


def get_user_role(telegram_id: str) -> Optional[UserRole]:
    """Получение роли пользователя"""
    try:
        client = get_client()
        # Пытаемся найти лист ролей
        try:
            worksheet = client.get_worksheet(config.SHEET_ROLES)
            all_values = worksheet.get_all_values()
            
            if not all_values:
                return UserRole(telegram_id=str(telegram_id))
            
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
                logger.warning("Колонка Telegram ID не найдена в таблице ролей")
                return UserRole(telegram_id=str(telegram_id))
            
            # Ищем пользователя
            for row in all_values[1:]:
                if len(row) > telegram_id_col and str(row[telegram_id_col]) == str(telegram_id):
                    role = str(row[role_col]) if role_col is not None and len(row) > role_col else config.ROLE_NULL
                    name = str(row[fio_col]) if fio_col is not None and len(row) > fio_col else None
                    predstavites = str(row[predstavites_col]) if predstavites_col is not None and len(row) > predstavites_col else None
                    return UserRole(telegram_id=str(telegram_id), name=name, role=role, predstavites=predstavites)
        except gspread.WorksheetNotFound:
            logger.warning(f"Лист '{config.SHEET_ROLES}' не найден. Роли не настроены.")
        
        return UserRole(telegram_id=str(telegram_id))
    
    except Exception as e:
        logger.error(f"Ошибка при получении роли пользователя {telegram_id}: {e}")
        return UserRole(telegram_id=str(telegram_id))


def _build_deal_id(row: List) -> str:
    """Построение DealID из строки таблицы"""
    owner = str(row[COL_OWNER]).strip() if len(row) > COL_OWNER else ""
    location = str(row[COL_LOCATION]).strip() if len(row) > COL_LOCATION else ""
    number = str(row[COL_NUMBER]).strip() if len(row) > COL_NUMBER else ""
    
    return f"{owner}/{location}/{number}"


def _parse_deal_from_row(row: List, row_index: int) -> Optional[Deal]:
    """Парсинг сделки из строки таблицы"""
    try:
        if len(row) <= COL_OWNER:
            return None
        
        deal_id = _build_deal_id(row)
        if not deal_id or deal_id == "//":
            return None
        
        # Читаем данные о наличных
        all_cashless_str = str(row[COL_ALL_CASHLESS]).strip().lower() if len(row) > COL_ALL_CASHLESS else ""
        all_cashless = all_cashless_str in ["да", "yes", "true", "1"]
        
        who_received_cash = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
        
        # Читаем суммы
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
        
        # Читаем флаги передач
        transferred_to_assistant_str = str(row[COL_TRANSFERRED_TO_ASSISTANT]).strip().lower() if len(row) > COL_TRANSFERRED_TO_ASSISTANT else ""
        transferred_to_assistant = transferred_to_assistant_str in ["да", "yes", "true", "1"]
        
        transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
        transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
        
        owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
        owner_accepted = owner_accepted_str in ["да", "yes", "true", "1"]
        
        # Читаем разницу
        difference_str = str(row[COL_DIFFERENCE]).strip() if len(row) > COL_DIFFERENCE else ""
        difference = None
        if difference_str:
            try:
                difference = float(difference_str.replace(",", ".").replace(" ", ""))
            except (ValueError, AttributeError):
                pass
        
        # Создаем объект Deal
        deal = Deal(
            deal_id=deal_id,
            received_by_manager=amount_received,
            who_received_cash=who_received_cash,
            all_cashless=all_cashless,
            discrepancy=difference
        )
        
        # Заполняем статусы на основе флагов в таблице
        if transferred_to_assistant:
            deal.transferred_to_assistant = amount_received
        if owner_accepted or transferred_to_owner:
            deal.transferred_to_owner = amount_accepted or amount_received
        if owner_accepted:
            deal.accepted_by_owner = amount_accepted
        
        # Сохраняем индекс строки для обновления
        deal.row_index = row_index + 2  # +2 потому что индексация с 1 и есть заголовок
        
        return deal
    
    except Exception as e:
        logger.warning(f"Ошибка при парсинге строки {row_index}: {e}")
        return None


def get_deal_data_from_sheet(deal_id: str) -> Optional[Dict]:
    """Получение данных сделки из таблицы для определения текущего состояния"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            return None
        
        for row in all_values[1:]:
            if len(row) > COL_OWNER:
                row_deal_id = _build_deal_id(row)
                if row_deal_id == deal_id:
                    who_received = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
                    amount_received_str = str(row[COL_AMOUNT_RECEIVED]).strip() if len(row) > COL_AMOUNT_RECEIVED else ""
                    amount_received = None
                    if amount_received_str:
                        try:
                            amount_received = float(amount_received_str.replace(",", ".").replace(" ", ""))
                        except (ValueError, AttributeError):
                            pass
                    
                    transferred_to_assistant_str = str(row[COL_TRANSFERRED_TO_ASSISTANT]).strip().lower() if len(row) > COL_TRANSFERRED_TO_ASSISTANT else ""
                    transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
                    owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
                    
                    return {
                        "who_received_cash": who_received,
                        "amount_received": amount_received,
                        "transferred_to_assistant": transferred_to_assistant_str in ["да", "yes", "true", "1"],
                        "transferred_to_owner": transferred_to_owner_str in ["да", "yes", "true", "1"],
                        "owner_accepted": owner_accepted_str in ["да", "yes", "true", "1"]
                    }
        
        return None
    
    except Exception as e:
        logger.error(f"Ошибка при получении данных сделки {deal_id}: {e}")
        return None


def get_debt_summary() -> Dict[str, Dict]:
    """Получение сводки по долгам: сколько денег у каждого менеджера"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            return {}
        
        # Словарь: имя менеджера -> {total_debt, deals_count, deals}
        debt_by_manager: Dict[str, Dict] = {}
        
        for idx, row in enumerate(all_values[1:], start=1):
            # Пропускаем если все по безналу
            all_cashless_str = str(row[COL_ALL_CASHLESS]).strip().lower() if len(row) > COL_ALL_CASHLESS else ""
            if all_cashless_str in ["да", "yes", "true", "1"]:
                continue
            
            # Получаем имя менеджера из колонки "Представьтесь"
            manager_name = str(row[COL_NAME]).strip() if len(row) > COL_NAME else "Неизвестно"
            
            # Проверяем, получили ли деньги
            who_received = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
            if who_received.lower() in ["не получали", "не получали", ""]:
                continue  # Деньги еще не получены, не считаем в долг
            
            # Проверяем, переданы ли деньги собственнику
            transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
            owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
            
            transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
            owner_accepted = owner_accepted_str in ["да", "yes", "true", "1"]
            
            # Если деньги уже переданы и приняты собственником - не считаем в долг
            if transferred_to_owner and owner_accepted:
                continue
            
            # Получаем сумму
            amount_str = str(row[COL_AMOUNT_RECEIVED]).strip() if len(row) > COL_AMOUNT_RECEIVED else ""
            amount = 0.0
            if amount_str:
                try:
                    amount = float(amount_str.replace(",", ".").replace(" ", ""))
                except (ValueError, AttributeError):
                    pass
            
            if amount > 0:
                if manager_name not in debt_by_manager:
                    debt_by_manager[manager_name] = {
                        "total_debt": 0.0,
                        "deals_count": 0,
                        "deals": []
                    }
                
                debt_by_manager[manager_name]["total_debt"] += amount
                debt_by_manager[manager_name]["deals_count"] += 1
                
                # Добавляем информацию о сделке
                deal_id = _build_deal_id(row)
                debt_by_manager[manager_name]["deals"].append({
                    "deal_id": deal_id,
                    "amount": amount,
                    "who_received": who_received
                })
        
        return debt_by_manager
    
    except Exception as e:
        logger.error(f"Ошибка при расчете долгов: {e}")
        return {}


def get_user_deals(telegram_id: str, role: str) -> List[Deal]:
    """Получение сделок пользователя в зависимости от роли"""
    try:
        # Получаем информацию о пользователе для фильтрации
        user_role_obj = get_user_role(telegram_id)
        predstavites_name = user_role_obj.predstavites  # Имя из колонки "Представьтесь"
        
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:  # Нет данных (только заголовки)
            return []
        
        deals = []
        
        # Парсим все строки (пропускаем заголовок)
        for idx, row in enumerate(all_values[1:], start=1):
            deal = _parse_deal_from_row(row, idx)
            if deal:
                # Если все по безналу, пропускаем
                if deal.all_cashless:
                    continue
                
                # Фильтрация по роли
                if role == config.ROLE_OWNER:
                    # Собственник видит только сделки, где деньги еще не переданы ему
                    # Проверяем статус в таблице
                    transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
                    owner_accepted_str = str(row[COL_OWNER_ACCEPTED]).strip().lower() if len(row) > COL_OWNER_ACCEPTED else ""
                    
                    transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
                    owner_accepted = owner_accepted_str in ["да", "yes", "true", "1"]
                    
                    # Если деньги еще не переданы собственнику или не приняты - показываем
                    if not transferred_to_owner or not owner_accepted:
                        deals.append(deal)
                elif role == config.ROLE_MANAGER:
                    # Менеджер видит сделки где в колонке "Кто получил нал?" указано его имя
                    # Сопоставляем по колонке "Кто получил нал?" с именем из "Представьтесь" в ролях
                    who_received = str(row[COL_WHO_RECEIVED_CASH]).strip() if len(row) > COL_WHO_RECEIVED_CASH else ""
                    
                    # Проверяем, получил ли менеджер деньги
                    if who_received.lower() in ["не получали", ""]:
                        continue  # Деньги еще не получены
                    
                    # Сопоставляем имя из "Кто получил нал?" с именем менеджера из таблицы ролей
                    if predstavites_name and predstavites_name.strip():
                        # Если в ролях указано имя для сопоставления
                        if who_received.lower() == predstavites_name.strip().lower():
                            deals.append(deal)
                    else:
                        # Если имя не указано в ролях, используем имя из формы "Представьтесь"
                        manager_name = str(row[COL_NAME]).strip() if len(row) > COL_NAME else ""
                        if manager_name and who_received.lower() == manager_name.lower():
                            deals.append(deal)
                elif role == config.ROLE_ASSISTANT:
                    # Ассистент видит сделки где деньги переданы ему (но еще не переданы собственнику)
                    transferred_to_assistant_str = str(row[COL_TRANSFERRED_TO_ASSISTANT]).strip().lower() if len(row) > COL_TRANSFERRED_TO_ASSISTANT else ""
                    transferred_to_owner_str = str(row[COL_TRANSFERRED_TO_OWNER]).strip().lower() if len(row) > COL_TRANSFERRED_TO_OWNER else ""
                    
                    transferred_to_assistant = transferred_to_assistant_str in ["да", "yes", "true", "1"]
                    transferred_to_owner = transferred_to_owner_str in ["да", "yes", "true", "1"]
                    
                    # Ассистент видит если деньги переданы ему, но еще не переданы собственнику
                    if transferred_to_assistant and not transferred_to_owner:
                        deals.append(deal)
                elif role == config.ROLE_NULL:
                    # Пользователь без роли не видит сделок
                    pass
        
        return deals
    
    except Exception as e:
        logger.error(f"Ошибка при получении сделок пользователя {telegram_id}: {e}")
        return []


def create_cashflow_event(event: CashFlowEvent) -> bool:
    """Запись события в журнал CashFlow_Log (append-only) с проверкой идемпотентности"""
    try:
        client = get_client()
        client.ensure_cashflow_log_exists()
        worksheet = client.get_worksheet(config.SHEET_CASHFLOW_LOG)
        
        # Проверка идемпотентности: ищем дубликаты
        from datetime import timedelta
        all_values = worksheet.get_all_values()
        
        if len(all_values) > 1:  # Есть заголовки и данные
            headers = all_values[0]
            try:
                deal_id_col = headers.index("DealID")
                stage_col = headers.index("Этап")
                timestamp_col = headers.index("Timestamp")
                
                threshold_time = event.timestamp - timedelta(minutes=5)
                
                for row in all_values[1:]:
                    if len(row) > max(deal_id_col, stage_col, timestamp_col):
                        row_deal_id = str(row[deal_id_col])
                        row_stage = str(row[stage_col])
                        row_timestamp_str = str(row[timestamp_col])
                        
                        # Проверяем, совпадают ли DealID и этап
                        if row_deal_id == event.deal_id and row_stage == event.stage:
                            try:
                                row_timestamp = datetime.strptime(row_timestamp_str, "%Y-%m-%d %H:%M:%S")
                                # Если событие было создано недавно (в пределах 5 минут), считаем дубликатом
                                if row_timestamp >= threshold_time:
                                    logger.warning(f"Дубликат события обнаружен: {event.deal_id} - {event.stage}")
                                    return False  # Идемпотентность: не создаем дубликат
                            except ValueError:
                                pass  # Игнорируем ошибки парсинга даты
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка при проверке идемпотентности: {e}, продолжаем...")
        
        # Используем retry механизм для записи
        def write_event():
            worksheet.append_row(event.to_row())
        
        client.retry_operation(write_event)
        
        logger.info(f"Создано событие в журнале: {event.deal_id} - {event.stage} - {event.amount}")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при создании события в журнале: {e}")
        return False


def get_cashflow_history(deal_id: str) -> List[CashFlowEvent]:
    """Получение истории событий по сделке"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_CASHFLOW_LOG)
        all_values = worksheet.get_all_values()
        
        if not all_values:
            return []
        
        # Первая строка - заголовки
        headers = all_values[0]
        deal_id_col = headers.index("DealID") if "DealID" in headers else 0
        
        events = []
        for row in all_values[1:]:
            if len(row) > deal_id_col and row[deal_id_col] == deal_id:
                try:
                    event = CashFlowEvent.from_row(row)
                    events.append(event)
                except Exception as e:
                    logger.warning(f"Ошибка при разборе события: {e}")
                    continue
        
        # Сортируем по времени
        events.sort(key=lambda x: x.timestamp)
        return events
    
    except Exception as e:
        logger.error(f"Ошибка при получении истории событий для {deal_id}: {e}")
        return []


def update_deal_status_with_role(deal_id: str, stage: str, amount: float, user: str, role: str) -> bool:
    """Обновление статуса сделки в основном листе и создание события в журнале"""
    try:
        client = get_client()
        worksheet = client.get_worksheet(config.SHEET_MAIN)
        all_values = worksheet.get_all_values()
        
        # Ищем строку с нужным DealID
        for idx, row in enumerate(all_values[1:], start=2):  # start=2 потому что индексация с 1 и есть заголовок
            if len(row) > COL_OWNER:
                row_deal_id = _build_deal_id(row)
                if row_deal_id == deal_id:
                    # Обновляем соответствующие колонки в зависимости от этапа
                    if stage == config.STAGE_RECEIVED_BY_MANAGER:
                        worksheet.update_cell(idx, COL_AMOUNT_RECEIVED + 1, amount)  # +1 потому что индексация с 1
                    elif stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
                        # Колонка N: Передано ассистенту? (Да/Нет)
                        worksheet.update_cell(idx, COL_TRANSFERRED_TO_ASSISTANT + 1, "Да")
                    elif stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
                        # Если принял ассистент, автоматически ставим "Да" в "Передано ассистенту?"
                        # Колонка N: Передано ассистенту? (Да/Нет) - автоматически ставим Да
                        worksheet.update_cell(idx, COL_TRANSFERRED_TO_ASSISTANT + 1, "Да")
                    elif stage == config.STAGE_TRANSFERRED_TO_OWNER:
                        # Колонка O: Передано собственнику? (Да/Нет)
                        worksheet.update_cell(idx, COL_TRANSFERRED_TO_OWNER + 1, "Да")
                    elif stage == config.STAGE_ACCEPTED_BY_OWNER:
                        # Если принял собственник, автоматически ставим "Да" в "Передано собственнику?"
                        # Колонка O: Передано собственнику? (Да/Нет) - автоматически ставим Да
                        # Колонка P: Собственник принял? (Да/Нет)
                        # Колонка Q: Сумма принято наличных
                        worksheet.update_cell(idx, COL_TRANSFERRED_TO_OWNER + 1, "Да")
                        worksheet.update_cell(idx, COL_OWNER_ACCEPTED + 1, "Да")
                        worksheet.update_cell(idx, COL_AMOUNT_ACCEPTED + 1, amount)
                        
                        # Рассчитываем разницу (колонка R)
                        amount_received_str = str(row[COL_AMOUNT_RECEIVED]).strip() if len(row) > COL_AMOUNT_RECEIVED else ""
                        amount_received = None
                        if amount_received_str:
                            try:
                                amount_received = float(amount_received_str.replace(",", ".").replace(" ", ""))
                            except (ValueError, AttributeError):
                                pass
                        
                        if amount_received is not None:
                            difference = amount_received - amount
                            worksheet.update_cell(idx, COL_DIFFERENCE + 1, difference)
                    
                    # Создаем событие в журнале
                    event = CashFlowEvent(
                        deal_id=deal_id,
                        stage=stage,
                        role=role,
                        user=user,
                        amount=amount,
                        timestamp=datetime.now()
                    )
                    create_cashflow_event(event)
                    
                    return True
        
        logger.warning(f"Сделка {deal_id} не найдена в таблице")
        return False
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса сделки {deal_id}: {e}")
        return False


def calculate_discrepancies(deal_id: str) -> Dict[str, float]:
    """Расчет расхождений по сделке"""
    events = get_cashflow_history(deal_id)
    
    discrepancies = {}
    
    # Находим суммы на каждом этапе
    transferred_to_assistant = None
    accepted_by_assistant = None
    transferred_to_owner = None
    accepted_by_owner = None
    
    for event in events:
        if event.stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
            transferred_to_assistant = event.amount
        elif event.stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
            accepted_by_assistant = event.amount
        elif event.stage == config.STAGE_TRANSFERRED_TO_OWNER:
            transferred_to_owner = event.amount
        elif event.stage == config.STAGE_ACCEPTED_BY_OWNER:
            accepted_by_owner = event.amount
    
    # Рассчитываем расхождения
    if transferred_to_assistant is not None and accepted_by_assistant is not None:
        diff = transferred_to_assistant - accepted_by_assistant
        if diff != 0:
            discrepancies["assistant"] = diff
    
    if transferred_to_owner is not None and accepted_by_owner is not None:
        diff = transferred_to_owner - accepted_by_owner
        if diff != 0:
            discrepancies["owner"] = diff
    
    return discrepancies
