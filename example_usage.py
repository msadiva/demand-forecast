#!/usr/bin/env python3
"""
Example usage of the Workforce Management System.

This script demonstrates how to use the forecasting and staff assignment
components together to generate weekly forecasts and staff schedules.
"""

import pandas as pd
from datetime import datetime
from workforce_management import ForecastingEngine, StaffAssignmentManager
from workforce_management.staff_assignment.models import Staff


def parse_holidays(holiday_str):
    """Parse comma-separated holiday string into datetime list."""
    if pd.isna(holiday_str):
        return []
    dates = [d.strip() for d in str(holiday_str).split(',')]
    return [pd.to_datetime(d, format='%Y-%m-%d') for d in dates if d.strip()]


def main():
    print("=== Workforce Management System Demo ===\n")
    
    # 1. Load historical load data
    print("1. Loading historical load data...")
    try:
        load_data = pd.read_csv('data/Historical_Load_Data.csv')
        load_data['date'] = pd.to_datetime(load_data['date'], format='%d-%m-%Y')
        print(f"Loaded {len(load_data)} historical records")
        print(f"   Date range: {load_data['date'].min().strftime('%Y-%m-%d')} to {load_data['date'].max().strftime('%Y-%m-%d')}")
    except FileNotFoundError:
        print("Error: data/Historical_Load_Data.csv not found")
        return
        
    # 2. Load staff holiday data  
    print("\n2. Loading staff holiday data...")
    try:
        staff_data = pd.read_csv('data/Staff_List_with_Holidays.csv')
        staff_data['holiday_dates'] = staff_data['holidays'].apply(parse_holidays)
        
        staff_list = []
        for _, row in staff_data.iterrows():
            staff = Staff(
                employee_id=row['employee_id'],
                name=row['name'],
                holiday_dates=row['holiday_dates']
            )
            staff_list.append(staff)
            
        print(f"Loaded {len(staff_list)} staff members")
        for staff in staff_list:
            print(f"     - {staff.name}: {len(staff.holiday_dates)} holidays")
            
    except FileNotFoundError:
        print("Error: data/Staff_List_with_Holidays.csv not found")
        return
        
    # 3. Initialize forecasting engine
    print("\n3. Initializing forecasting engine...")
    forecaster = ForecastingEngine(default_method='last_week_pattern')
    forecaster.load_historical_data(load_data)
    
    model_info = forecaster.get_model_info()
    print(f"Engine initialized with {model_info['data_points']} data points")
    print(f"   Available methods: {', '.join(model_info['supported_methods'])}")
    print(f"   Default method: {model_info['default_method']}")
    
    # 4. Generate forecast
    print("\n4. Generating demand forecast...")
    forecast_result = forecaster.forecast(days=7)
    forecast_df = forecast_result.to_dataframe()
    
    print("   ✓ Forecast generated:")
    for _, row in forecast_df.iterrows():
        print(f"     {row['date'].strftime('%Y-%m-%d')} ({row['day_name']}): {row['people_required']} people")
    
    # 5. Initialize assignment manager
    print("\n5. Initializing staff assignment manager...")
    assignment_manager = StaffAssignmentManager(staff_list)
    
    staff_info = assignment_manager.get_staff_info()
    print(f"Manager initialized with {staff_info['total_staff']} staff members")
    
    # 6. Generate staff assignments
    print("\n6. Generating staff assignments...")
    print("   (Using detailed output to show assignment logic)")
    assignment_result = assignment_manager.assign_week(forecast_df, verbose=True)
    
    # 7. Display summary
    print("\n7. Weekly Summary:")
    print(assignment_result.get_summary_report())
    
    # 8. Demonstrate state management
    print("\n8. Demonstrating state management...")
    print("   Current state after assignments:")
    for name, days in assignment_result.workload_balance.items():
        print(f"     {name}: {days} days worked")
    
    print("\n   Resetting state for new week...")
    assignment_manager.reset_state()
    
    new_state = assignment_manager.get_staff_info()
    print("   State after reset:")
    for name, days in new_state['current_workload'].items():
        print(f"     {name}: {days} days worked")
    
    # 9. Export results
    print("\n9. Exporting results...")
    
    # Save forecast
    forecast_df.to_csv('forecast_output.csv', index=False)
    print("   ✓ Forecast saved to forecast_output.csv")
    
    # Save assignments
    assignments_df = assignment_result.to_dataframe()
    assignments_df.to_csv('assignments_output.csv', index=False)
    print("   ✓ Assignments saved to assignments_output.csv")
    
    print("\n=== Demo Complete ===")
    print("Check forecast_output.csv and assignments_output.csv for results")


if __name__ == "__main__":
    main()