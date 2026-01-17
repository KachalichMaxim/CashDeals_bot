"""Логика работы с ролями"""
from typing import Optional, List
import logging

from sheets.operations import get_user_role, get_user_deals
from sheets.models import UserRole, Deal
import config

logger = logging.getLogger(__name__)


def validate_role_access(user_role: UserRole, required_role: str) -> bool:
    """Проверка прав доступа пользователя"""
    if required_role == config.ROLE_OWNER:
        # Собственник имеет доступ ко всему
        return user_role.is_owner()
    elif required_role == config.ROLE_ASSISTANT:
        return user_role.is_assistant() or user_role.is_owner()
    elif required_role == config.ROLE_MANAGER:
        return user_role.has_role()  # Любой с ролью может видеть базовую информацию
    
    return False


def can_confirm_stage(user_role: UserRole, stage: str) -> bool:
    """Проверка, может ли пользователь подтвердить этап"""
    if stage == config.STAGE_RECEIVED_BY_MANAGER:
        return user_role.is_manager()
    elif stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
        return user_role.is_manager()
    elif stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
        return user_role.is_assistant()
    elif stage == config.STAGE_TRANSFERRED_TO_OWNER:
        return user_role.is_assistant()
    elif stage == config.STAGE_ACCEPTED_BY_OWNER:
        return user_role.is_owner()
    
    return False


def get_next_stage_for_role(user_role: UserRole, current_stage: Optional[str]) -> Optional[str]:
    """Получение следующего этапа, который пользователь может подтвердить"""
    if user_role.is_manager():
        if current_stage is None:
            return config.STAGE_RECEIVED_BY_MANAGER
        elif current_stage == config.STAGE_RECEIVED_BY_MANAGER:
            return config.STAGE_TRANSFERRED_TO_ASSISTANT
    
    elif user_role.is_assistant():
        if current_stage == config.STAGE_TRANSFERRED_TO_ASSISTANT:
            return config.STAGE_ACCEPTED_BY_ASSISTANT
        elif current_stage == config.STAGE_ACCEPTED_BY_ASSISTANT:
            return config.STAGE_TRANSFERRED_TO_OWNER
    
    elif user_role.is_owner():
        if current_stage == config.STAGE_TRANSFERRED_TO_OWNER:
            return config.STAGE_ACCEPTED_BY_OWNER
    
    return None


def filter_deals_by_role(deals: List[Deal], user_role: UserRole) -> List[Deal]:
    """Фильтрация сделок по роли пользователя"""
    # В реальности нужно фильтровать по менеджеру сделки
    # Пока возвращаем все сделки для собственника, для остальных - только свои
    if user_role.is_owner():
        return deals  # Собственник видит все
    
    # Для менеджера и ассистента - только их сделки (нужно добавить фильтрацию)
    return deals


