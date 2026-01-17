"""Модели данных для работы с Google Sheets"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import config


@dataclass
class UserRole:
    """Модель пользователя и роли"""
    telegram_id: str
    name: Optional[str] = None
    role: str = config.ROLE_NULL
    predstavites: Optional[str] = None  # Значение из колонки "Представьтесь" для сопоставления
    
    def is_manager(self) -> bool:
        return self.role == config.ROLE_MANAGER
    
    def is_assistant(self) -> bool:
        return self.role == config.ROLE_ASSISTANT
    
    def is_owner(self) -> bool:
        return self.role == config.ROLE_OWNER
    
    def has_role(self) -> bool:
        return self.role != config.ROLE_NULL


@dataclass
class CashFlowEvent:
    """Модель события в журнале CashFlow_Log"""
    deal_id: str
    stage: str
    role: str
    user: str  # ФИО или Telegram ID
    amount: float
    timestamp: datetime
    
    def to_row(self) -> list:
        """Преобразование в строку для записи в Google Sheets"""
        return [
            self.deal_id,
            self.stage,
            self.role,
            self.user,
            self.amount,
            self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ]
    
    @classmethod
    def from_row(cls, row: list) -> 'CashFlowEvent':
        """Создание из строки Google Sheets"""
        deal_id, stage, role, user, amount_str, timestamp_str = row[:6]
        amount = float(amount_str) if amount_str else 0.0
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S") if timestamp_str else datetime.now()
        return cls(
            deal_id=str(deal_id),
            stage=str(stage),
            role=str(role),
            user=str(user),
            amount=amount,
            timestamp=timestamp
        )


@dataclass
class Deal:
    """Модель сделки"""
    deal_id: str  # Ключ: <Чей объект>/<Локация>/<№>
    # Статусы этапов (Да/Нет или суммы)
    received_by_manager: Optional[float] = None
    transferred_to_assistant: Optional[float] = None
    accepted_by_assistant: Optional[float] = None
    transferred_to_owner: Optional[float] = None
    accepted_by_owner: Optional[float] = None
    # Флаги подтверждений
    manager_confirmed: bool = False
    assistant_received_confirmed: bool = False
    assistant_transferred_confirmed: bool = False
    owner_confirmed: bool = False
    # Дополнительные поля из формы
    who_received_cash: Optional[str] = None  # "Собственник" / "Ассистент"
    all_cashless: Optional[bool] = False  # "Вся сумма по безналу = Да"
    discrepancy: Optional[float] = None  # Разница
    status: str = config.STATUS_IN_PROGRESS
    row_index: Optional[int] = None  # Индекс строки в таблице для обновления
    
    def get_current_stage(self) -> Optional[str]:
        """Определение текущего этапа"""
        if self.accepted_by_owner is not None:
            return config.STAGE_ACCEPTED_BY_OWNER
        if self.transferred_to_owner is not None and not self.owner_confirmed:
            return config.STAGE_TRANSFERRED_TO_OWNER
        if self.accepted_by_assistant is not None and self.transferred_to_owner is None:
            return config.STAGE_ACCEPTED_BY_ASSISTANT
        if self.transferred_to_assistant is not None and not self.assistant_received_confirmed:
            return config.STAGE_TRANSFERRED_TO_ASSISTANT
        if self.received_by_manager is not None:
            return config.STAGE_RECEIVED_BY_MANAGER
        return None

