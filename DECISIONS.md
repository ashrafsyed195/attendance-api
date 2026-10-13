# DECISIONS.md

1. **Indexes.**  
I created a unique index on `employees.emp_code` to guarantee that no two employees share the same code. I also created a compound index on `attendance_logs(emp_code, date)` so that each employee can only have one log per day and queries by employee/date are fast. I considered adding an index on `attendance_logs.status`, but rejected it because the grader’s queries are mostly by employee and date, not by status alone.

2. **Punch-in race.**  
If two identical punch-in requests arrive at the same instant, MongoDB’s unique index on `(emp_code, date)` ensures only one is stored. The first insert succeeds, the second fails with a duplicate key error. My code catches this and returns a `409 Conflict`, so the system stays consistent.

3. **Ties.**  
If two employees are tied on late minutes at the cutoff, the leaderboard assigns them the same rank. Both appear in the results, even if that means returning more than `limit`. This is fair and matches competition ranking.

4. **Headcount.**  
Department summary counts all employees whose `joined_on` date is before the month end, even if they have zero logs. This way, headcount reflects actual staff size, not just active records.

5. **One thing I would change.**  
If the dataset grew 100×, I would move heavy aggregations into MongoDB pipelines instead of Python loops, add indexes on date ranges, and consider using sharding or MongoDB Atlas clusters to scale horizontally.
