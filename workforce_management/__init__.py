"""
Workforce Management System

A comprehensive system for demand forecasting and staff assignment.
"""



from .forecasting.models import ForecastingEngine
from .staff_assignment.manager import StaffAssignmentManager
from .staff_assignment.models import Staff, Assignment

__all__ = [
    "ForecastingEngine",
    "StaffAssignmentManager", 
    "Staff",
    "Assignment"
]