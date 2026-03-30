---
name: db-diagnostics
description: "Troubleshoot database issues. Use when queries fail or performance degrades."
---

# /db-diagnostics — Database Diagnostics

Investigate database performance issues, slow queries, locks, and connection exhaustion.

## Connection Check

```sql
-- How many connections are open?
SELECT count(*), state, wait_event_type, wait_event
FROM pg_stat_activity
GROUP BY state, wait_event_type, wait_event
ORDER BY count DESC;

-- Are we near the connection limit?
SELECT current_setting('max_connections')::int AS max,
       count(*) AS current,
       current_setting('max_connections')::int - count(*) AS available
FROM pg_stat_activity;
```

## Active Queries

```sql
-- What queries are running right now?
SELECT pid, now() - query_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start < now() - interval '5 seconds'
ORDER BY duration DESC;

-- Kill a runaway query (use pid from above)
-- SELECT pg_terminate_backend([pid]);
```

## Slow Query Analysis

```sql
-- EXPLAIN ANALYZE a suspect query (replace with actual query)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM events WHERE session_id = 'xyz' ORDER BY timestamp DESC LIMIT 100;

-- Look for: Seq Scan on large tables, high actual rows vs estimated rows
```

## Lock Investigation

```sql
-- Are there blocking locks?
SELECT bl.pid AS blocked_pid,
       a.query AS blocked_query,
       kl.pid AS blocking_pid,
       ka.query AS blocking_query
FROM pg_catalog.pg_locks bl
JOIN pg_catalog.pg_stat_activity a ON a.pid = bl.pid
JOIN pg_catalog.pg_locks kl ON kl.transactionid = bl.transactionid AND kl.pid != bl.pid
JOIN pg_catalog.pg_stat_activity ka ON ka.pid = kl.pid
WHERE NOT bl.granted;
```

## Index Check

```sql
-- Tables with sequential scans (candidates for indexing)
SELECT relname, seq_scan, seq_tup_read, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_scan DESC;
```

## Findings Template

```markdown
## DB Diagnostics: [Date]

### Connection Status
- Max: N | Current: N | Available: N

### Slow Queries Found
1. [query digest]: avg [time]ms — root cause: [missing index / N+1 / etc]

### Locks
- Blocking: yes/no — [details]

### Recommendations
1. Add index on [table.column] — will fix [query]
2. [other action]
```
