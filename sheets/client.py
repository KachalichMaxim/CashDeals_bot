"""Клиент Google Sheets API"""
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional
import config
import logging

logger = logging.getLogger(__name__)


class SheetsClient:
    """Клиент для работы с Google Sheets"""
    
    def __init__(self):
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        self._connect()
    
    def _connect(self):
        """Подключение к Google Sheets"""
        try:
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file"
            ]
            credentials = Credentials.from_service_account_file(
                config.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=scope
            )
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(config.GOOGLE_SHEETS_ID)
            logger.info(f"Подключено к Google Sheets: {config.GOOGLE_SHEETS_ID}")
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets: {e}")
            raise
    
    def get_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Получение листа по имени"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logger.warning(f"Лист '{sheet_name}' не найден, создаю...")
            worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            return worksheet
    
    def ensure_sheet_exists(self, sheet_name: str, headers: list = None) -> gspread.Worksheet:
        """Обеспечение существования листа с заголовками"""
        try:
            worksheet = self.get_worksheet(sheet_name)
            
            if headers:
                # Проверяем, есть ли заголовки
                try:
                    existing_headers = worksheet.row_values(1)
                    if existing_headers:
                        # Заголовки уже есть, проверяем соответствие
                        if existing_headers[:len(headers)] == headers:
                            # Заголовки правильные, ничего не делаем
                            logger.debug(f"Лист '{sheet_name}' уже имеет правильные заголовки")
                        else:
                            # Заголовки не совпадают, но не перезаписываем (может быть пользовательские данные)
                            logger.warning(f"Лист '{sheet_name}' имеет другие заголовки, но оставляем как есть")
                    else:
                        # Лист пустой, добавляем заголовки
                        worksheet.insert_row(headers, 1)
                        logger.info(f"Заголовки добавлены в лист '{sheet_name}'")
                except Exception as e:
                    # Если не удалось прочитать заголовки (пустой лист), добавляем
                    try:
                        worksheet.insert_row(headers, 1)
                        logger.info(f"Заголовки добавлены в лист '{sheet_name}'")
                    except Exception as insert_error:
                        logger.warning(f"Не удалось добавить заголовки в '{sheet_name}': {insert_error}")
            
            return worksheet
        except Exception as e:
            logger.error(f"Ошибка при создании/проверке листа '{sheet_name}': {e}")
            raise
    
    def ensure_cashflow_log_exists(self):
        """Обеспечение существования листа CashFlow_Log с заголовками"""
        headers = ["DealID", "Этап", "Роль", "Пользователь", "Сумма", "Timestamp"]
        self.ensure_sheet_exists(config.SHEET_CASHFLOW_LOG, headers)
    
    def ensure_roles_sheet_exists(self):
        """Обеспечение существования листа Роли с заголовками"""
        headers = ["ФИО", "Представьтесь", "Telegram ID", "Роль"]
        self.ensure_sheet_exists(config.SHEET_ROLES, headers)
    
    def initialize_sheets(self):
        """Инициализация всех необходимых листов при первом запуске"""
        logger.info("Инициализация листов...")
        try:
            # Создаем лист CashFlow_Log
            self.ensure_cashflow_log_exists()
            logger.info(f"Лист '{config.SHEET_CASHFLOW_LOG}' готов")
            
            # Создаем лист Роли
            self.ensure_roles_sheet_exists()
            logger.info(f"Лист '{config.SHEET_ROLES}' готов")
            
            # Проверяем основной лист (должен существовать, но проверим)
            try:
                self.get_worksheet(config.SHEET_MAIN)
                logger.info(f"Лист '{config.SHEET_MAIN}' найден")
            except Exception as e:
                logger.warning(f"Лист '{config.SHEET_MAIN}' не найден: {e}")
            
            logger.info("Инициализация листов завершена")
        except Exception as e:
            logger.error(f"Ошибка при инициализации листов: {e}")
            raise
    
    def retry_operation(self, func, max_retries=3, delay=1):
        """Повторная попытка операции при ошибке"""
        import time
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Попытка {attempt + 1} не удалась: {e}, повтор через {delay} сек...")
                time.sleep(delay)


# Глобальный экземпляр клиента
_sheets_client: Optional[SheetsClient] = None


def get_client() -> SheetsClient:
    """Получение глобального экземпляра клиента"""
    global _sheets_client
    if _sheets_client is None:
        _sheets_client = SheetsClient()
    return _sheets_client

