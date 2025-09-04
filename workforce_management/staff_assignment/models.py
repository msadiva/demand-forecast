"""
Data models for staff assignment system.
"""

from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import pandas as pd


@dataclass
class Staff:
    """Represents a staff member with their holiday information."""
    
    employee_id: int
    name: str
    holiday_dates: List[datetime]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Staff':
        """Create Staff instance from dictionary."""
        return cls(
            employee_id=data['employee_id'],
            name=data['name'],
            holiday_dates=data.get('holiday_dates', [])
        )
    
    def is_available(self, date: datetime) -> bool:
        """Check if staff member is available on given date."""
        return date not in self.holiday_dates
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'employee_id': self.employee_id,
            'name': self.name,
            'holiday_dates': [d.isoformat() for d in self.holiday_dates]
        }


@dataclass 
class Assignment:
    """Represents a daily staff assignment."""
    
    date: datetime
    day_name: str
    people_required: int
    assigned_staff: List[str]
    assigned_count: int
    overtime: bool
    shortage: int
    
    @property
    def is_fully_staffed(self) -> bool:
        """Check if assignment meets full requirement."""
        return self.shortage == 0
        
    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage."""
        if self.people_required == 0:
            return 100.0
        return (self.assigned_count / self.people_required) * 100
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'date': self.date.isoformat(),
            'day_name': self.day_name,
            'people_required': self.people_required,
            'assigned_staff': self.assigned_staff.copy(),
            'assigned_count': self.assigned_count,
            'overtime': self.overtime,
            'shortage': self.shortage,
            'coverage_percentage': self.coverage_percentage
        }


@dataclass
class AssignmentResult:
    """Results of a weekly staff assignment operation."""
    
    assignments: List[Assignment]
    workload_balance: Dict[str, int]
    summary_stats: Dict[str, any]
    
    @property
    def total_overtime_days(self) -> int:
        """Total number of days requiring overtime."""
        return sum(1 for assignment in self.assignments if assignment.overtime)
        
    @property
    def total_shortage(self) -> int:
        """Total person-day shortage across the week."""
        return sum(assignment.shortage for assignment in self.assignments)
        
    @property 
    def average_coverage(self) -> float:
        """Average coverage percentage across all assignments."""
        if not self.assignments:
            return 100.0
        return sum(a.coverage_percentage for a in self.assignments) / len(self.assignments)
        
    def to_dataframe(self) -> pd.DataFrame:
        """Convert assignments to pandas DataFrame."""
        return pd.DataFrame([assignment.to_dict() for assignment in self.assignments])
        
    def get_summary_report(self) -> str:
        """Generate a text summary report."""
        report = []
        report.append("=== WEEKLY ASSIGNMENT SUMMARY ===")
        report.append(f"Total assignments: {len(self.assignments)}")
        report.append(f"Overtime days: {self.total_overtime_days}/{len(self.assignments)}")
        report.append(f"Total shortage: {self.total_shortage} person-days")
        report.append(f"Average coverage: {self.average_coverage:.1f}%")
        report.append("")
        report.append("WORKLOAD BALANCE:")
        for name, days in self.workload_balance.items():
            report.append(f"  {name}: {days} days")
        report.append("")
        report.append("DAILY BREAKDOWN:")
        for assignment in self.assignments:
            status = "⚠️ OVERTIME" if assignment.overtime else "✅ Normal"
            report.append(f"  {assignment.date.strftime('%Y-%m-%d')} ({assignment.day_name}): "
                        f"{assignment.assigned_count}/{assignment.people_required} - {status}")
            if assignment.shortage > 0:
                report.append(f"    ❌ Short by {assignment.shortage} person(s)")
                
        return "\n".join(report)
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'assignments': [assignment.to_dict() for assignment in self.assignments],
            'workload_balance': self.workload_balance,
            'summary_stats': {
                'total_overtime_days': self.total_overtime_days,
                'total_shortage': self.total_shortage,
                'average_coverage': self.average_coverage,
                'total_assignments': len(self.assignments)
            }
        }