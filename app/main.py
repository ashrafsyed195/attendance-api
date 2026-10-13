"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from decimal import Decimal, ROUND_HALF_UP


load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "attendance_db")]
# Ensure indexes are created at startup
db.employees.create_index("emp_code", unique=True)
db.attendance_logs.create_index([("emp_code", 1), ("date", 1)], unique=True)


IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def compute_late_minutes(punch_in: datetime, shift_start: str) -> int:
    h, m = map(int, shift_start.split(":"))
    start = punch_in.replace(hour=h, minute=m, second=0, microsecond=0)
    diff = int((punch_in - start).total_seconds() // 60)
    return diff if diff > 10 else 0  # strictly more than 10


def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    hours = (punch_out - punch_in).total_seconds() / 3600
    return float(Decimal(hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def compute_overtime(punch_out: datetime, shift_end: str, date_str: str) -> int:
    h, m = map(int, shift_end.split(":"))
    end = datetime.fromisoformat(date_str).replace(hour=h, minute=m, tzinfo=IST)
    diff = int((punch_out - end).total_seconds() // 60)
    return diff if diff >= 30 else 0


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    email: str
    department: str
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str


class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None
    status: str = "PRESENT"


# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    try:
        db.command("ping")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="MongoDB not responding")

@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    try:
        doc = body.model_dump()
        doc["created_at"] = int(datetime.now().timestamp() * 1000)  # epoch ms
        db.employees.insert_one(doc)  # unique index on emp_code must exist
        doc.pop("_id", None)
        return doc
    except Exception:
        raise HTTPException(409, "emp_code already exists")


@app.get("/employees")
def list_employees(department: Optional[str] = None, page: int = 1, page_size: int = 20):
    q = {}
    if department:
        q["department"] = department
    skip = (page - 1) * page_size
    total = db.employees.count_documents(q)
    items = list(
        db.employees.find(q, {"_id": 0})
        .sort("emp_code", 1)
        .skip(skip)
        .limit(page_size)
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "unknown employee")

    # Validate punched_at
    if body.punched_at and (body.punched_at < 100000000000 or body.punched_at > 4102444800000):
        raise HTTPException(422, "invalid punched_at")

    ts = datetime.fromtimestamp(body.punched_at / 1000) if body.punched_at else datetime.now()

    # Compute IST date (R1, overnight shifts)
    ist_ts = ts.astimezone(IST).replace(microsecond=0)
    d = ist_ts.date().isoformat()

    if body.status not in ["PRESENT", "WFH", "ON_DUTY"]:
        raise HTTPException(422, "invalid status")

    try:
        doc = {
            "emp_code": body.emp_code,
            "date": d,
            "status": body.status,
            "punch_in": int(ist_ts.timestamp() * 1000),
            "punch_out": None,
            "work_hours": None,
            "late_minutes": compute_late_minutes(ist_ts, emp["shift_start"]),
            "overtime_minutes": 0,
            "half_day": False,
            "history": [],
        }
        db.attendance_logs.insert_one(doc)  # unique index on (emp_code, date)
        doc.pop("_id", None)
        return doc
    except Exception:
        raise HTTPException(409, "already punched in for this date")


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from > date_to")
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status

    skip = (page - 1) * page_size
    total = db.attendance_logs.count_documents(q)
    cursor = db.attendance_logs.find(q).sort([("date", -1), ("emp_code", 1)]).skip(skip).limit(page_size)
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items, "total": total, "page": page, "page_size": page_size}

class PunchOutIn(BaseModel):
    emp_code: str
    date: str
    time: str


from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from pydantic import BaseModel

IST = timezone(timedelta(hours=5, minutes=30))

class PunchOutIn(BaseModel):
    emp_code: str
    date: str
    time: str

@app.post("/attendance/punch-out")
def punch_out(body: PunchOutIn):
    # 1. Validate employee exists
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "unknown employee")

    # 2. Convert date + time → datetime (IST aware)
    try:
        ts = datetime.strptime(f"{body.date} {body.time}", "%Y-%m-%d %H:%M")
        ts = ts.replace(tzinfo=IST)   # attach IST timezone
    except ValueError:
        raise HTTPException(422, "invalid date/time format")

    ist_ts = ts.astimezone(IST).replace(microsecond=0)

    # 3. Find attendance record for that date
    record = db.attendance_logs.find_one({"emp_code": body.emp_code, "date": body.date})
    if not record:
        raise HTTPException(404, "no punch-in found")

    if record.get("punch_out"):
        raise HTTPException(409, "already punched out")

    # 4. Validate punch_out timing
    punch_in_dt = datetime.fromtimestamp(record["punch_in"] / 1000, tz=IST)
    if ist_ts <= punch_in_dt:
        raise HTTPException(422, "punch_out <= punch_in")
    if (ist_ts - punch_in_dt).total_seconds() > 24 * 3600:
        raise HTTPException(422, "punch_out more than 24h after punch_in")

    # 5. Compute derived fields
    try:
        work_hours = compute_work_hours(punch_in_dt, ist_ts)
        overtime_minutes = compute_overtime(ist_ts, emp["shift_end"], record["date"])
    except Exception as e:
        raise HTTPException(500, f"calculation error: {e}")

    half_day = work_hours < 4.50

    # 6. Update record
    db.attendance_logs.update_one(
        {"_id": record["_id"]},
        {"$set": {
            "punch_out": int(ist_ts.timestamp() * 1000),
            "work_hours": work_hours,
            "overtime_minutes": overtime_minutes,
            "half_day": half_day
        }}
    )

    # 7. Return updated record
    record.update({
        "punch_out": int(ist_ts.timestamp() * 1000),
        "work_hours": work_hours,
        "overtime_minutes": overtime_minutes,
        "half_day": half_day
    })
    record["id"] = str(record.pop("_id"))
    return record

class RegularizeIn(BaseModel):
    status: Optional[str] = None
    punch_in: Optional[int] = None
    punch_out: Optional[int] = None
    reason: str
    regularized_by: str



@app.patch("/attendance/{emp_code}/{date}")
def regularize(emp_code: str, date: str, body: RegularizeIn):
    # 1. Find employee
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "unknown employee")

    # 2. Find attendance record
    record = db.attendance_logs.find_one({"emp_code": emp_code, "date": date})
    if not record:
        raise HTTPException(404, "no record for this date")

    changes = {}

    # 3. Apply status rules
    if body.status:
        if body.status not in ["PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"]:
            raise HTTPException(422, "invalid status")
        if body.status in ["ABSENT", "LEAVE"]:
            # must clear punch times
            if body.punch_in or body.punch_out:
                raise HTTPException(422, "ABSENT/LEAVE cannot have punch times")
            changes["status"] = {"from": record["status"], "to": body.status}
            record["status"] = body.status
            record["punch_in"] = None
            record["punch_out"] = None
        else:
            # presence status requires punch_in
            if not (body.punch_in or record.get("punch_in")):
                raise HTTPException(422, "presence status requires punch_in")
            changes["status"] = {"from": record["status"], "to": body.status}
            record["status"] = body.status

    # 4. Apply punch_in
    if body.punch_in:
        if body.punch_in < 100000000000 or body.punch_in > 4102444800000:
            raise HTTPException(422, "invalid punch_in")
        changes["punch_in"] = {"from": record.get("punch_in"), "to": body.punch_in}
        record["punch_in"] = body.punch_in

    # 5. Apply punch_out
    if body.punch_out:
        if body.punch_out < 100000000000 or body.punch_out > 4102444800000:
            raise HTTPException(422, "invalid punch_out")
        if not record.get("punch_in") or body.punch_out <= record["punch_in"]:
            raise HTTPException(422, "punch_out must be after punch_in")
        if body.punch_out - record["punch_in"] > 24 * 3600 * 1000:
            raise HTTPException(422, "punch_out more than 24h after punch_in")
        changes["punch_out"] = {"from": record.get("punch_out"), "to": body.punch_out}
        record["punch_out"] = body.punch_out

    # 6. Recompute derived fields
    if record.get("punch_in") and record.get("punch_out"):
        punch_in_dt = datetime.fromtimestamp(record["punch_in"] / 1000, tz=IST)
        punch_out_dt = datetime.fromtimestamp(record["punch_out"] / 1000, tz=IST)
        record["work_hours"] = compute_work_hours(punch_in_dt, punch_out_dt)
        record["overtime_minutes"] = compute_overtime(punch_out_dt, emp["shift_end"], date)
        record["half_day"] = record["work_hours"] < 4.50
    elif record.get("punch_in"):
        record["late_minutes"] = compute_late_minutes(
            datetime.fromtimestamp(record["punch_in"] / 1000, tz=IST),
            emp["shift_start"]
        )

    # 7. Append history entry
    if not changes:
        raise HTTPException(422, "no changes made")

    history_entry = {
        "at": int(datetime.now().timestamp() * 1000),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes
    }
    record.setdefault("history", []).append(history_entry)

    # 8. Save back to DB
    db.attendance_logs.update_one({"_id": record["_id"]}, {"$set": record})

    record["id"] = str(record.pop("_id"))
    return record

@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(emp_code: str, month: str):
    # 1. Validate employee exists
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "unknown employee")

    # 2. Compute month boundaries
    year, mon = map(int, month.split("-"))
    start_date = datetime(year, mon, 1).date()
    if mon == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, mon + 1, 1).date() - timedelta(days=1)

    # 3. Filter attendance records for this employee and month
    records = list(db.attendance_logs.find({
        "emp_code": emp_code,
        "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
    }))

    # 4. Compute working_days (Mon–Fri, from joined_on)
    joined_on = datetime.fromisoformat(emp["joined_on"]).date()
    working_days = sum(
        1 for d in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1))
        if d.weekday() < 5 and d >= joined_on
    )

    # 5. Compute present_days, leave_days, late_count
    present_days = 0
    leave_days = 0
    late_count = 0
    for rec in records:
        if rec["status"] in ["PRESENT", "WFH", "ON_DUTY"]:
            if rec.get("half_day"):
                present_days += 0.5
            else:
                present_days += 1
        elif rec["status"] == "LEAVE":
            leave_days += 1
        if rec.get("late_minutes", 0) > 0:
            late_count += 1

    # 6. Compute attendance_pct
    attendance_pct = None
    if working_days > 0:
        pct = (present_days / working_days) * 100
        attendance_pct = float(Decimal(pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    # 7. Return summary
    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": leave_days,
        "late_count": late_count,
        "attendance_pct": attendance_pct
    }

@app.get("/analytics/departments/summary")
def department_summary(month: str, department: Optional[str] = None):
    # 1. Compute month boundaries
    year, mon = map(int, month.split("-"))
    start_date = datetime(year, mon, 1).date()
    if mon == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, mon + 1, 1).date() - timedelta(days=1)

    # 2. Filter employees by joined_on <= end_date
    emp_query = {"joined_on": {"$lte": end_date.isoformat()}}
    if department:
        emp_query["department"] = department
    employees = list(db.employees.find(emp_query, {"_id": 0}))

    # 3. For each department, aggregate attendance records
    dept_summary = {}
    for emp in employees:
        dept = emp["department"]
        if dept not in dept_summary:
            dept_summary[dept] = {
                "headcount": 0,
                "present_days": 0,
                "avg_work_hours": [],
                "late_count": 0,
                "total_late_minutes": 0,
                "leave_count": 0,
                "on_duty_count": 0,
            }
        dept_summary[dept]["headcount"] += 1

        # Attendance records for this employee in the month
        records = list(db.attendance_logs.find({
            "emp_code": emp["emp_code"],
            "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }))

        for rec in records:
            if rec["status"] in ["PRESENT", "WFH", "ON_DUTY"]:
                if rec.get("half_day"):
                    dept_summary[dept]["present_days"] += 0.5
                else:
                    dept_summary[dept]["present_days"] += 1
                if rec.get("work_hours") is not None:
                    dept_summary[dept]["avg_work_hours"].append(rec["work_hours"])
            if rec["status"] == "LEAVE":
                dept_summary[dept]["leave_count"] += 1
            if rec["status"] == "ON_DUTY":
                dept_summary[dept]["on_duty_count"] += 1
            if rec.get("late_minutes", 0) > 0:
                dept_summary[dept]["late_count"] += 1
                dept_summary[dept]["total_late_minutes"] += rec["late_minutes"]

    # 4. Finalize avg_work_hours
    results = []
    for dept, vals in sorted(dept_summary.items()):
        avg_hours = None
        if vals["avg_work_hours"]:
            avg = sum(vals["avg_work_hours"]) / len(vals["avg_work_hours"])
            avg_hours = float(Decimal(avg).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        results.append({
            "department": dept,
            "headcount": vals["headcount"],
            "present_days": vals["present_days"],
            "avg_work_hours": avg_hours,
            "late_count": vals["late_count"],
            "total_late_minutes": vals["total_late_minutes"],
            "leave_count": vals["leave_count"],
            "on_duty_count": vals["on_duty_count"],
        })

    return results

@app.get("/analytics/leaderboard/late")
def late_leaderboard(month: str, limit: int = 10, department: Optional[str] = None):
    # 1. Compute month boundaries
    year, mon = map(int, month.split("-"))
    start_date = datetime(year, mon, 1).date()
    if mon == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, mon + 1, 1).date() - timedelta(days=1)

    # 2. Filter employees (optional department)
    emp_query = {}
    if department:
        emp_query["department"] = department
    employees = list(db.employees.find(emp_query, {"_id": 0}))

    # 3. Aggregate late_minutes per employee
    leaderboard = []
    for emp in employees:
        records = list(db.attendance_logs.find({
            "emp_code": emp["emp_code"],
            "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }))
        total_late = sum(rec.get("late_minutes", 0) for rec in records)
        if total_late > 0:
            leaderboard.append({
                "emp_code": emp["emp_code"],
                "name": emp["name"],
                "department": emp["department"],
                "total_late_minutes": total_late
            })

    # 4. Sort by total_late_minutes desc, then emp_code asc
    leaderboard.sort(key=lambda x: (-x["total_late_minutes"], x["emp_code"]))

    # 5. Assign competition ranks
    rank = 1
    prev_total = None
    for i, row in enumerate(leaderboard):
        if prev_total is None or row["total_late_minutes"] < prev_total:
            rank = i + 1
        row["rank"] = rank
        prev_total = row["total_late_minutes"]

    # 6. Apply limit (include ties)
    max_rank = limit
    filtered = [row for row in leaderboard if row["rank"] <= max_rank]

    return filtered

@app.get("/analytics/departments/{department}/trend")
def department_trend(department: str, from_: str, to: str):
    # 1. Validate department exists
    emp_query = {"department": department}
    employees = list(db.employees.find(emp_query, {"_id": 0}))
    if not employees:
        raise HTTPException(404, "unknown department")

    # 2. Validate date range
    start_date = datetime.fromisoformat(from_).date()
    end_date = datetime.fromisoformat(to).date()
    if end_date < start_date:
        raise HTTPException(422, "to < from")
    if (end_date - start_date).days > 92:
        raise HTTPException(422, "range exceeds 92 days")

    # 3. Build list of all days in range
    days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    results = []
    attendance_rates = []

    for day in days:
        # Headcount = employees joined on or before this day
        headcount = sum(1 for e in employees if datetime.fromisoformat(e["joined_on"]).date() <= day)

        # Attendance records for this department on this day
        records = list(db.attendance_logs.find({
            "date": day.isoformat(),
            "emp_code": {"$in": [e["emp_code"] for e in employees]}
        }))

        present_count = 0
        late_count = 0
        for rec in records:
            if rec["status"] in ["PRESENT", "WFH", "ON_DUTY"]:
                present_count += 0.5 if rec.get("half_day") else 1
            if rec.get("late_minutes", 0) > 0:
                late_count += 1

        # Attendance rate
        is_working_day = day.weekday() < 5
        if is_working_day and headcount > 0:
            rate = present_count / headcount
            attendance_rate = float(Decimal(rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        elif is_working_day:
            attendance_rate = None
        else:
            attendance_rate = None

        attendance_rates.append(attendance_rate)

        # Moving average (last 7 days including current)
        window = [r for r in attendance_rates[-7:] if r is not None]
        moving_avg_7d = None
        if window:
            avg = sum(window) / len(window)
            moving_avg_7d = float(Decimal(avg).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

        results.append({
            "date": day.isoformat(),
            "is_working_day": is_working_day,
            "headcount": headcount,
            "present_count": present_count,
            "late_count": late_count,
            "attendance_rate": attendance_rate,
            "moving_avg_7d": moving_avg_7d
        })

    return results

@app.get("/admin/explain/{endpoint}")
def explain_endpoint(endpoint: str, emp_code: Optional[str] = None, department: Optional[str] = None):
    if endpoint == "employees":
        q = {}
        if department:
            q["department"] = department
        explain = db.employees.find(q).explain("executionStats")
        return {"endpoint": "employees", "collection": "employees", "explain": explain}

    elif endpoint == "attendance":
        q = {}
        if emp_code:
            q["emp_code"] = emp_code
        explain = db.attendance_logs.find(q).explain("executionStats")
        return {"endpoint": "attendance", "collection": "attendance_logs", "explain": explain}

    else:
        raise HTTPException(422, "unsupported endpoint for explain")









# --------------------------------------------------------------------------- #
# TODO - the rest of the contract (see openapi.yaml):
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend
#   GET   /admin/explain/{endpoint}
# --------------------------------------------------------------------------- #
