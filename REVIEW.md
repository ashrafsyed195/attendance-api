# REVIEW.md

| # | Where (function / line) | What was wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|--------------------------|----------------|-----------------------------------------------|------------------|
| 1 | compute_late_minutes | Grace period logic wrong (did not handle seconds properly) | Punch-in at 09:40:01 gave 0 late minutes instead of 10 | Truncated to seconds and applied strict >10 rule |
| 2 | compute_overtime | Used `datetime.fromisoformat(date_str)` without handling overnight shifts | Punch-out after midnight was misclassified | Adjusted to IST and handled overnight shift correctly |
| 3 | compute_work_hours | Used raw float rounding, banker’s rounding | Work hours like 4.245 rounded incorrectly | Switched to Decimal with ROUND_HALF_UP |
| 4 | punch_in | Allowed invalid status values | Sending `"status":"XYZ"` was accepted | Restricted to PRESENT, WFH, ON_DUTY |
| 5 | punch_in | Did not validate duplicate punch-ins properly | Two punch-ins same day inserted duplicates | Added unique index `(emp_code,date)` and handled 409 Conflict |
| 6 | list_employees | Wrong skip calculation | Page 1 skipped first records | Changed skip to `(page-1)*page_size` |
| 7 | list_employees | Did not enforce max page_size | Allowed huge page_size values | Added validation: page_size ≤ 100 |
| 8 | list_attendance | Did not validate date_from > date_to | Query with date_from later than date_to still returned results | Added check: raise 422 if date_from > date_to |
| 9 | punch_out | Did not enforce punch_out > punch_in and ≤24h | Punch-out before punch-in or >24h was accepted | Added validation checks |
| 10 | regularize | Allowed ABSENT/LEAVE with punch times | Could send punch_in with LEAVE | Added rule: ABSENT/LEAVE must clear punch times |
| 11 | regularize | Did not recompute derived fields after changes | Work hours/late minutes stale after regularization | Added recomputation logic |
| 12 | employee_monthly | Did not count half-days correctly | Half-day attendance counted as full | Adjusted to add 0.5 for half-day |
| 13 | department_summary | Averaged work hours incorrectly (raw float) | Avg work hours had floating errors | Used Decimal with ROUND_HALF_UP |
| 14 | late_leaderboard | Did not handle ties correctly | Two employees with same late minutes got different ranks | Implemented competition ranking with ties |
| 15 | department_trend | Did not enforce max 92-day range | Large queries returned unlimited data | Added validation: reject >92 days |

---

## Not Defects
- **Health endpoint**: Already checked MongoDB with `db.command("ping")`. Correct.  
- **Employee creation**: Unique index on `emp_code` enforced. Correct.  
- **Basic FastAPI setup**: Title and version matched contract. Correct.

