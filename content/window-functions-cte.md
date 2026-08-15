I spent longer than I want to admit on a query that refused to run:

```sql
SELECT
    d.name AS department,
    e.name AS employee,
    DENSE_RANK() OVER (PARTITION BY d.name ORDER BY e.salary DESC) AS rnk
FROM employee e
JOIN department d ON e.department_id = d.id
WHERE rnk < 4;
```

The error says `rnk` does not exist. It does exist — it is right there, four
lines up. The problem is *when*.

## Order of operations

A query is not evaluated top to bottom. It goes `FROM` → `WHERE` → `GROUP BY` →
`HAVING` → window functions → `SELECT`. By the time `WHERE` runs, no window
function has been evaluated yet, so `rnk` genuinely does not exist at that
moment.

This is the same reason you cannot filter an aggregate in `WHERE` and need
`HAVING` instead. The difference is that window functions have no `HAVING`
equivalent. There is no clause that runs after them.

## The fix

Materialise the result first, filter it second:

```sql
WITH ranked AS (
    SELECT
        d.name AS department,
        e.name AS employee,
        DENSE_RANK() OVER (PARTITION BY d.name ORDER BY e.salary DESC) AS rnk
    FROM employee e
    JOIN department d ON e.department_id = d.id
)
SELECT department, employee
FROM ranked
WHERE rnk < 4;
```

The CTE is not a readability choice here. It is the only way to get a second
pass over a column that did not exist during the first one.

`DENSE_RANK` rather than `RANK`, incidentally, because ties should not consume
positions — with `RANK`, two people sharing second place would push the query
to skip third entirely.
