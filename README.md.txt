# AI-Powered Emergency Response Intelligence Platform

## Milestone 2

This project implements a Flood Disaster Resource Prediction and
Emergency Response Backend.

## Features

- Feature Engineering
- Flood Resource Demand Prediction using Random Forest
- Food Resource Prediction
- Water Requirement Prediction
- Medical Kit Prediction
- Shelter Requirement Prediction
- Resource Shortage Calculation
- Resource Allocation Priority
- Disaster Distance Calculation
- Emergency Response ETA
- FastAPI Backend

## Additional Engineered Features

1. affected_population_ratio
2. demographic_vulnerability_index
3. infrastructure_damage_index
4. logistics_difficulty_index
5. vulnerability_load
6. flood_intensity_index
7. rainfall_pressure_index
8. response_access_index
9. average_emergency_distance_km
10. month

## ML Model

Random Forest Regressor

Outputs:

- Food Demand
- Water Demand
- Medical Kit Demand
- Shelter Demand

## Backend

Run the backend using:

```bash
python -m uvicorn backend.main:app --reload