"""Конфигурация приложения"""
import os
from pathlib import Path

# Базовый путь проекта
BASE_DIR = Path(__file__).parent

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8103210301:AAEqKjckjhDyeQAB-hVwcjN2tw-tBwXKLhw"

# Google Sheets настройки
GOOGLE_SHEETS_ID = "1FZm3cd_xD09IEPcxXtllYvnfxsoPnCLmvfr83GuADR8"
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "tonal-concord-464913-u3-2024741e839c.json"

# Названия листов
SHEET_MAIN = "Ответы на форму (1)"  # Основной лист со сделками
SHEET_ROLES = "Роли"  # Таблица ролей (может быть на том же листе или отдельном)
SHEET_CASHFLOW_LOG = "CashFlow_Log"  # Журнал операций

# Этапы движения наличных
STAGE_RECEIVED_BY_MANAGER = "Получено менеджером"
STAGE_TRANSFERRED_TO_ASSISTANT = "Передано ассистенту"
STAGE_ACCEPTED_BY_ASSISTANT = "Принято ассистентом"
STAGE_TRANSFERRED_TO_OWNER = "Передано собственнику"
STAGE_ACCEPTED_BY_OWNER = "Принято собственником"

STAGES = [
    STAGE_RECEIVED_BY_MANAGER,
    STAGE_TRANSFERRED_TO_ASSISTANT,
    STAGE_ACCEPTED_BY_ASSISTANT,
    STAGE_TRANSFERRED_TO_OWNER,
    STAGE_ACCEPTED_BY_OWNER,
]

# Роли
ROLE_MANAGER = "Менеджер"
ROLE_ASSISTANT = "Ассистент"
ROLE_OWNER = "Собственник"
ROLE_NULL = "NULL"

ROLES = [ROLE_NULL, ROLE_MANAGER, ROLE_ASSISTANT, ROLE_OWNER]

# Статусы
STATUS_DISCREPANCY = "Расхождение"
STATUS_COMPLETE = "Завершено"
STATUS_IN_PROGRESS = "В процессе"

