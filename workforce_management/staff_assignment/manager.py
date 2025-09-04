"""
Staff Assignment Manager for roster management.

Implements the core staffing rules:
1. Available staff = not on holiday and didn't work yesterday (unless overtime)
2. Sort by fewest days worked first (workload balancing)  
3. If load > available staff, flag "overtime" and allow reusing yesterday's workers
"""

from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from .models import Staff, Assignment, AssignmentResult


class StaffAssignmentManager:
    """
    Manages staff assignments with state tracking and workload balancing.
    
    This class maintains persistent state about who worked when, enabling
    fair workload distribution and proper rest period enforcement.
    """
    
    def __init__(self, staff_list: List[Staff]):
        """
        Initialize manager with staff list.
        
        Args:
            staff_list: List of Staff objects
        """
        self.staff_list = staff_list
        self.staff_names = [staff.name for staff in staff_list]
        self._create_staff_lookup()
        
        # State management
        self.reset_state()
        
    def _create_staff_lookup(self) -> None:
        """Create lookup dictionary for staff by name."""
        self.staff_lookup = {staff.name: staff for staff in self.staff_list}
        
    def reset_state(self) -> None:
        """Reset all state counters (call at start of new week)."""
        self.staff_workdays = {name: 0 for name in self.staff_names}
        self.staff_worked_yesterday = {name: False for name in self.staff_names}
        self.assignment_history = []
        
    def load_state(self, state: Dict) -> None:
        """
        Load existing state (for continuing from previous week).
        
        Args:
            state: Dictionary containing workdays and yesterday status
        """
        if 'staff_workdays' in state:
            self.staff_workdays.update(state['staff_workdays'])
        if 'staff_worked_yesterday' in state:
            self.staff_worked_yesterday.update(state['staff_worked_yesterday'])
            
    def get_state(self) -> Dict:
        """Get current state for persistence."""
        return {
            'staff_workdays': self.staff_workdays.copy(),
            'staff_worked_yesterday': self.staff_worked_yesterday.copy()
        }
        
    def get_available_staff(self, date: datetime) -> List[str]:
        """
        Get staff members available on given date (not on holiday).
        
        Args:
            date: Date to check availability for
            
        Returns:
            List of available staff names
        """
        available = []
        for staff in self.staff_list:
            if staff.is_available(date):
                available.append(staff.name)
        return available
        
    def get_eligible_staff(self, available_staff: List[str]) -> List[str]:
        """
        Get staff who didn't work yesterday (for normal operations).
        
        Args:
            available_staff: List of staff available today
            
        Returns:
            List of eligible staff names (didn't work yesterday)
        """
        return [name for name in available_staff if not self.staff_worked_yesterday[name]]
        
    def assign_staff_for_day(self, 
                           date: datetime, 
                           people_required: int,
                           day_name: Optional[str] = None,
                           verbose: bool = False) -> Assignment:
        """
        Assign staff for a single day following the assignment rules.
        
        Args:
            date: Date for assignment
            people_required: Number of people needed
            day_name: Name of the day (auto-generated if not provided)
            verbose: Whether to print assignment details
            
        Returns:
            Assignment object with assignment details
        """
        if day_name is None:
            day_name = date.strftime('%A')
            
        if verbose:
            print(f"\n--- {date.strftime('%Y-%m-%d')} ({day_name}) ---")
            print(f"People required: {people_required}")
            
        # Step 1: Get available staff (not on holiday)
        available_staff = self.get_available_staff(date)
        
        # Step 2: Get eligible staff (didn't work yesterday)
        eligible_staff = self.get_eligible_staff(available_staff)
        
        # Step 3: Sort by workload (fairest distribution)
        eligible_staff.sort(key=lambda name: self.staff_workdays[name])
        
        if verbose:
            print(f"Available staff: {available_staff}")
            print(f"Eligible (didn't work yesterday): {eligible_staff}")
            print(f"Current workdays: {[(name, self.staff_workdays[name]) for name in self.staff_names]}")
            
        # Step 4: Assignment logic
        if people_required <= len(eligible_staff):
            # Normal operations - use eligible staff only
            assigned_staff = eligible_staff[:people_required]
            overtime_flag = False
            if verbose:
                print("Normal operations")
                
        else:
            # Overtime needed - use all available staff, sorted by workdays
            available_staff.sort(key=lambda name: self.staff_workdays[name])
            assigned_staff = available_staff[:people_required]
            overtime_flag = True
            shortage = max(0, people_required - len(available_staff))
            
            if verbose:
                print("OVERTIME required")
                if shortage > 0:
                    print(f"Still short by {shortage} people")
                    
        if verbose:
            print(f"Assigned: {assigned_staff}")
            
        # Step 5: Create assignment object
        assignment = Assignment(
            date=date,
            day_name=day_name,
            people_required=people_required,
            assigned_staff=assigned_staff.copy(),
            assigned_count=len(assigned_staff),
            overtime=overtime_flag,
            shortage=max(0, people_required - len(available_staff))
        )
        
        # Step 6: Update state
        self._update_state(assigned_staff)
        
        # Step 7: Record in history
        self.assignment_history.append(assignment)
        
        return assignment
        
    def _update_state(self, assigned_staff: List[str]) -> None:
        """
        Update internal state after assignment.
        
        Args:
            assigned_staff: List of staff names assigned today
        """
        # Reset yesterday's work status for all staff
        for name in self.staff_names:
            self.staff_worked_yesterday[name] = name in assigned_staff
            
        # Increment workday counter for assigned staff
        for name in assigned_staff:
            if name in self.staff_workdays:
                self.staff_workdays[name] += 1
                
    def assign_week(self, 
                   forecast_df: pd.DataFrame,
                   verbose: bool = False) -> AssignmentResult:
        """
        Assign staff for entire week based on forecast.
        
        Args:
            forecast_df: DataFrame with columns ['date', 'people_required', 'day_name']
            verbose: Whether to print detailed assignment process
            
        Returns:
            AssignmentResult with all assignments and summary statistics
        """
        if verbose:
            print("=== STAFF ASSIGNMENT FOR WEEK ===")
            
        # Validate forecast dataframe
        required_cols = ['date', 'people_required']
        missing_cols = [col for col in required_cols if col not in forecast_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in forecast: {missing_cols}")
            
        week_assignments = []
        
        for _, day_forecast in forecast_df.iterrows():
            day_name = day_forecast.get('day_name', day_forecast['date'].strftime('%A'))
            
            assignment = self.assign_staff_for_day(
                date=day_forecast['date'],
                people_required=day_forecast['people_required'],
                day_name=day_name,
                verbose=verbose
            )
            week_assignments.append(assignment)
            
        # Generate summary statistics
        summary_stats = self._generate_summary_stats(week_assignments)
        
        return AssignmentResult(
            assignments=week_assignments,
            workload_balance=self.staff_workdays.copy(),
            summary_stats=summary_stats
        )
        
    def _generate_summary_stats(self, assignments: List[Assignment]) -> Dict:
        """Generate summary statistics for assignments."""
        total_demand = sum(a.people_required for a in assignments)
        total_assigned = sum(a.assigned_count for a in assignments)
        
        return {
            'total_assignments': len(assignments),
            'total_demand': total_demand,
            'total_assigned': total_assigned,
            'assignment_rate': (total_assigned / total_demand * 100) if total_demand > 0 else 100.0,
            'overtime_days': sum(1 for a in assignments if a.overtime),
            'total_shortage': sum(a.shortage for a in assignments),
            'average_coverage': sum(a.coverage_percentage for a in assignments) / len(assignments) if assignments else 100.0
        }
        
    def get_staff_info(self) -> Dict:
        """Get information about managed staff."""
        return {
            'total_staff': len(self.staff_list),
            'staff_names': self.staff_names,
            'current_workload': self.staff_workdays,
            'worked_yesterday': self.staff_worked_yesterday,
            'total_assignments_made': len(self.assignment_history)
        }
        
    def get_holiday_conflicts(self, date_range: List[datetime]) -> Dict[datetime, List[str]]:
        """
        Get holiday conflicts for a date range.
        
        Args:
            date_range: List of dates to check
            
        Returns:
            Dictionary mapping dates to list of staff on holiday
        """
        conflicts = {}
        for date in date_range:
            on_holiday = []
            for staff in self.staff_list:
                if not staff.is_available(date):
                    on_holiday.append(staff.name)
            if on_holiday:
                conflicts[date] = on_holiday
        return conflicts