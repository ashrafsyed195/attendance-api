# Employee Attendance & Analytics API - Candidate Kit

## Project Overview
This project implements a backend HR attendance system using **FastAPI** and **MongoDB**.  
Employees punch in/out, managers correct records, and analytics endpoints summarize attendance trends.



---

## Local Setup

```bash
# Navigate into project folder
cd C:\Users\arafa\Desktop\ashraf\sdt_candidate_kit\candidate_kit

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start MongoDB (in a separate PowerShell window)
cd "C:\Program Files\MongoDB\Server\9.0\bin"
.\mongod.exe --dbpath C:\data\db

# Seed sample data
python sample_seed.py

# Run FastAPI
uvicorn app.main:app --reload --port 8000

### screenshots/
![Punch-In](screenshots/punch_in.png)
![Punch-Out](screenshots/punch_out.png)
![Regularize](screenshots/regularize.png)
![Analytics](screenshots/analytics.png)
