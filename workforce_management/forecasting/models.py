"""
Forecasting models for demand prediction.

This module contains various forecasting algorithms tested and validated 
in the EDA phase, with the best-performing model (Last Week Pattern) as default.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass
class ForecastResult:
    """Result of a forecasting operation."""
    dates: List[datetime]
    predictions: List[int]
    method: str
    confidence_metrics: Optional[Dict[str, float]] = None
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert forecast result to pandas DataFrame."""
        return pd.DataFrame({
            'date': self.dates,
            'people_required': self.predictions,
            'day_name': [d.strftime('%A') for d in self.dates]
        })


class ForecastingEngine:
    """
    Main forecasting engine supporting multiple algorithms.
    
    Based on EDA validation, Last Week Pattern performs best with:
    - MAE: 1.63
    - MAPE: 19.7%
    """
    
    SUPPORTED_METHODS = [
        'last_week_pattern',
        'moving_average', 
        'seasonal_moving_average',
        'day_of_week_average',
        'simple_average'
    ]
    
    def __init__(self, default_method: str = 'last_week_pattern'):
        """
        Initialize forecasting engine.
        
        Args:
            default_method: Default forecasting method to use
        """
        if default_method not in self.SUPPORTED_METHODS:
            raise ValueError(f"Method must be one of {self.SUPPORTED_METHODS}")
        
        self.default_method = default_method
        self._historical_data = None
        
    def load_historical_data(self, data: pd.DataFrame) -> None:
        """
        Load historical load data for forecasting.
        
        Args:
            data: DataFrame with columns ['date', 'load_units']
        """
        required_columns = ['date', 'load_units']
        missing_cols = [col for col in required_columns if col not in data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
            
        # Ensure date column is datetime
        data = data.copy()
        if not pd.api.types.is_datetime64_any_dtype(data['date']):
            # Handle DD-MM-YYYY format from your CSV files
            data['date'] = pd.to_datetime(data['date'], format='%d-%m-%Y', errors='coerce')
            
            # If that fails, try auto-detection
            if data['date'].isna().any():
                data['date'] = pd.to_datetime(data['date'], dayfirst=True)
            
        # Sort by date and add time features
        data = data.sort_values('date').reset_index(drop=True)
        data['day_of_week'] = data['date'].dt.dayofweek
        
        self._historical_data = data
        
    def forecast(self, 
                 days: int = 7, 
                 method: Optional[str] = None) -> ForecastResult:
        """
        Generate forecast for specified number of days.
        
        Args:
            days: Number of days to forecast (default: 7)
            method: Forecasting method to use (default: instance default)
            
        Returns:
            ForecastResult with predictions and metadata
        """
        if self._historical_data is None:
            raise ValueError("Historical data not loaded. Call load_historical_data() first.")
            
        method = method or self.default_method
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"Method must be one of {self.SUPPORTED_METHODS}")
            
        # Generate future dates
        last_date = self._historical_data['date'].max()
        future_dates = [last_date + timedelta(days=i+1) for i in range(days)]
        
        # Get predictions based on method
        predictions = self._get_predictions(method, future_dates)
        
        return ForecastResult(
            dates=future_dates,
            predictions=predictions,
            method=method
        )
        
    def _get_predictions(self, method: str, future_dates: List[datetime]) -> List[int]:
        """Get predictions using specified method."""
        
        if method == 'last_week_pattern':
            return self._last_week_pattern_forecast(future_dates)
        elif method == 'moving_average':
            return self._moving_average_forecast(future_dates)
        elif method == 'seasonal_moving_average':
            return self._seasonal_moving_average_forecast(future_dates)
        elif method == 'day_of_week_average':
            return self._day_of_week_average_forecast(future_dates)
        elif method == 'simple_average':
            return self._simple_average_forecast(future_dates)
        else:
            raise ValueError(f"Unknown method: {method}")
            
    def _last_week_pattern_forecast(self, future_dates: List[datetime]) -> List[int]:
        """Use last week's pattern (best performing method)."""
        last_week = self._historical_data.tail(7)['load_units'].tolist()
        return [last_week[i % 7] for i in range(len(future_dates))]
        
    def _moving_average_forecast(self, future_dates: List[datetime], window: int = 7) -> List[int]:
        """Simple moving average forecast."""
        ma = self._historical_data['load_units'].rolling(window=window, min_periods=1).mean().iloc[-1]
        return [max(1, round(ma)) for _ in future_dates]
        
    def _seasonal_moving_average_forecast(self, future_dates: List[datetime], window: int = 7) -> List[int]:
        """Moving average with day-of-week seasonality."""
        base_ma = self._historical_data['load_units'].rolling(window=window, min_periods=1).mean().iloc[-1]
        
        # Get day-of-week patterns
        daily_patterns = self._historical_data.groupby('day_of_week')['load_units'].mean()
        overall_mean = self._historical_data['load_units'].mean()
        daily_multipliers = daily_patterns / overall_mean
        
        predictions = []
        for date in future_dates:
            day_of_week = date.weekday()
            adjusted_forecast = base_ma * daily_multipliers.iloc[day_of_week]
            predictions.append(max(1, round(adjusted_forecast)))
            
        return predictions
        
    def _day_of_week_average_forecast(self, future_dates: List[datetime]) -> List[int]:
        """Historical day-of-week averages."""
        daily_averages = self._historical_data.groupby('day_of_week')['load_units'].mean()
        
        predictions = []
        for date in future_dates:
            day_of_week = date.weekday()
            predictions.append(max(1, round(daily_averages.iloc[day_of_week])))
            
        return predictions
        
    def _simple_average_forecast(self, future_dates: List[datetime]) -> List[int]:
        """Simple overall average."""
        avg = self._historical_data['load_units'].mean()
        return [max(1, round(avg)) for _ in future_dates]
        
    def evaluate_model(self, 
                      test_data: pd.DataFrame, 
                      method: Optional[str] = None) -> Dict[str, float]:
        """
        Evaluate forecasting model on test data.
        
        Args:
            test_data: Test dataset with actual values
            method: Method to evaluate (default: instance default)
            
        Returns:
            Dictionary with evaluation metrics (MAE, RMSE, MAPE)
        """
        method = method or self.default_method
        
        # Generate predictions for test period
        test_dates = test_data['date'].tolist()
        predictions = self._get_predictions(method, test_dates)
        actual_values = test_data['load_units'].tolist()
        
        # Calculate metrics
        mae = mean_absolute_error(actual_values, predictions)
        rmse = np.sqrt(mean_squared_error(actual_values, predictions))
        mape = np.mean(np.abs((np.array(actual_values) - np.array(predictions)) / np.array(actual_values))) * 100
        
        return {
            'method': method,
            'mae': mae,
            'rmse': rmse,
            'mape': mape
        }
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available models and current configuration."""
        return {
            'supported_methods': self.SUPPORTED_METHODS,
            'default_method': self.default_method,
            'data_loaded': self._historical_data is not None,
            'data_points': len(self._historical_data) if self._historical_data is not None else 0,
            'date_range': {
                'start': self._historical_data['date'].min().isoformat() if self._historical_data is not None else None,
                'end': self._historical_data['date'].max().isoformat() if self._historical_data is not None else None
            } if self._historical_data is not None else None
        }