"""
FastAPI application for workforce management system.

Provides REST API endpoints for:
- Uploading historical data
- Getting forecasts  
- Managing staff assignments
- Retrieving schedules
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import io

from ..forecasting.models import ForecastingEngine
from ..staff_assignment.manager import StaffAssignmentManager
from ..staff_assignment.models import Staff


# Pydantic models for API
class StaffCreate(BaseModel):
    employee_id: int
    name: str
    holidays: List[str]  # ISO date strings
    

class ForecastRequest(BaseModel):
    days: int = 7
    method: Optional[str] = None


class ForecastResponse(BaseModel):
    dates: List[str]
    predictions: List[int]
    method: str
    

class AssignmentResponse(BaseModel):
    assignments: List[Dict[str, Any]]
    workload_balance: Dict[str, int]
    summary_stats: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    version: str
    engines_loaded: Dict[str, bool]


# Initialize FastAPI app
app = FastAPI(
    title="Workforce Management API",
    description="API for demand forecasting and staff assignment",
    version="0.1.0"
)

# Global state (in production, use proper state management/database)
forecasting_engine: Optional[ForecastingEngine] = None
assignment_manager: Optional[StaffAssignmentManager] = None
current_staff: List[Staff] = []


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        engines_loaded={
            "forecasting": forecasting_engine is not None and forecasting_engine._historical_data is not None,
            "assignment": assignment_manager is not None
        }
    )


@app.post("/data/load-historical")
async def load_historical_data(file: UploadFile = File(...)):
    """
    Load historical load data from CSV file.
    
    Expected CSV columns: date, load_units
    """
    global forecasting_engine
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV format")
    
    try:
        # Read CSV file
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # Validate columns
        required_columns = ['date', 'load_units']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise HTTPException(status_code=400, detail=f"Missing columns: {missing_cols}")
        
        # Initialize and load data into forecasting engine
        forecasting_engine = ForecastingEngine()
        forecasting_engine.load_historical_data(df)
        
        return {
            "status": "success",
            "message": f"Loaded {len(df)} historical records",
            "data_range": {
                "start": df['date'].min(),
                "end": df['date'].max()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.post("/staff/load")
async def load_staff_data(file: UploadFile = File(...)):
    """
    Load staff data from CSV file.
    
    Expected CSV columns: employee_id, name, holidays
    """
    global assignment_manager, current_staff
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV format")
    
    try:
        # Read CSV file
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # Validate columns
        required_columns = ['employee_id', 'name', 'holidays']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise HTTPException(status_code=400, detail=f"Missing columns: {missing_cols}")
        
        # Parse holiday data
        def parse_holidays(holiday_str):
            if pd.isna(holiday_str):
                return []
            dates = [d.strip() for d in str(holiday_str).split(',')]
            return [datetime.strptime(d, '%Y-%m-%d') for d in dates if d.strip()]
        
        # Convert to Staff objects
        staff_objects = []
        for _, row in df.iterrows():
            holiday_dates = parse_holidays(row['holidays'])
            staff = Staff(
                employee_id=row['employee_id'],
                name=row['name'],
                holiday_dates=holiday_dates
            )
            staff_objects.append(staff)
        
        # Initialize assignment manager
        current_staff = staff_objects
        assignment_manager = StaffAssignmentManager(staff_objects)
        
        return {
            "status": "success",
            "message": f"Loaded {len(staff_objects)} staff members from CSV",
            "staff_names": [s.name for s in staff_objects],
            "total_holidays": sum(len(s.holiday_dates) for s in staff_objects)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing staff CSV: {str(e)}")


@app.post("/forecast", response_model=ForecastResponse)
async def create_forecast(request: ForecastRequest):
    """
    Generate demand forecast.
    """
    if forecasting_engine is None:
        raise HTTPException(status_code=400, detail="Historical data not loaded. Use /data/load-historical first.")
    
    try:
        forecast_result = forecasting_engine.forecast(
            days=request.days,
            method=request.method
        )
        
        return ForecastResponse(
            dates=[d.isoformat() for d in forecast_result.dates],
            predictions=forecast_result.predictions,
            method=forecast_result.method
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error generating forecast: {str(e)}")


@app.post("/assignments/generate", response_model=AssignmentResponse) 
async def generate_assignments(forecast_request: ForecastRequest):
    """
    Generate staff assignments based on forecast.
    """
    if forecasting_engine is None:
        raise HTTPException(status_code=400, detail="Historical data not loaded")
    if assignment_manager is None:
        raise HTTPException(status_code=400, detail="Staff data not loaded")
        
    try:
        # Generate forecast
        forecast_result = forecasting_engine.forecast(
            days=forecast_request.days,
            method=forecast_request.method
        )
        
        # Convert to DataFrame for assignment manager
        forecast_df = forecast_result.to_dataframe()
        
        # Generate assignments
        assignment_result = assignment_manager.assign_week(forecast_df)
        
        return AssignmentResponse(
            assignments=[a.to_dict() for a in assignment_result.assignments],
            workload_balance=assignment_result.workload_balance,
            summary_stats=assignment_result.summary_stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error generating assignments: {str(e)}")


@app.get("/assignments/summary")
async def get_assignment_summary():
    """
    Get summary of current assignment state.
    """
    if assignment_manager is None:
        raise HTTPException(status_code=400, detail="Staff data not loaded")
        
    return assignment_manager.get_staff_info()


@app.post("/assignments/reset-state")
async def reset_assignment_state():
    """
    Reset assignment state (start new week).
    """
    if assignment_manager is None:
        raise HTTPException(status_code=400, detail="Staff data not loaded")
        
    assignment_manager.reset_state()
    return {"status": "success", "message": "Assignment state reset"}


@app.get("/models/info") 
async def get_model_info():
    """
    Get information about available forecasting models.
    """
    if forecasting_engine is None:
        return {"forecasting_models": ForecastingEngine.SUPPORTED_METHODS}
    
    return forecasting_engine.get_model_info()


@app.get("/staff/holidays/{date}")
async def get_holiday_conflicts(date: str):
    """
    Get staff on holiday for specific date.
    """
    if assignment_manager is None:
        raise HTTPException(status_code=400, detail="Staff data not loaded")
        
    try:
        target_date = datetime.fromisoformat(date)
        conflicts = assignment_manager.get_holiday_conflicts([target_date])
        
        return {
            "date": date,
            "staff_on_holiday": conflicts.get(target_date, [])
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)