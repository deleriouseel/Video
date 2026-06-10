from datetime import datetime, timedelta
from typing import List, Tuple
from enum import Enum
from pathlib import Path
import logging
from ..utils.logging import get_logger

logger = get_logger()

class ServiceDay(Enum):
    FRIDAY = 4
    SUNDAY = 6
    MONDAY = 0

class DateService: 
    def __init__(self):
        self.logger = logger
    
    def get_service_dates(self) -> List[datetime]:
        today = datetime.now()
        service_dates = []

        for day in ServiceDay:

            days_since = (today.weekday() - day.value +7) % 7
            service_date = today - timedelta(days=days_since)
            service_date = service_date.replace(hour=0, minute=0, second=0, microsecond=0)
            service_dates.append(service_date)
            self.logger.info(f"Latest {day.name}: {service_date.date()}")

        return service_dates
    
    def is_service_date(self, check_date: datetime) -> bool:
        """Check if a date is one of our service dates"""
        service_dates = self.get_service_dates()
        
        check_date = check_date.replace(
            hour=0, 
            minute=0, 
            second=0, 
            microsecond=0
        )

        is_service = check_date in service_dates

        if is_service:
            self.logger.debug(f"{check_date.date()} is a service date")

        else:
            self.logger.debug(f"{check_date.date()} is NOT a service date")

        return is_service
    
    def validate_file_date(self, file_path: Path) -> bool:
        """Check if a file's creation date is a service date"""
        
        try:
            creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
            return self.is_service_date(creation_time)
        except Exception as e:
            self.logger.error(f"Error checking date for {file_path}: {e}")
            return False