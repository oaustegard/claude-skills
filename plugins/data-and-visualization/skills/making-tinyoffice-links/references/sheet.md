<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# sheet: a spreadsheet, a chart, a model

One table. Its header row names the columns, each optionally typed (`Sales:money`); the rows under it are rows 1, 2, 3, so `=SUM(B1:B3)` adds the first three. Up to 26 columns (A to Z). A cell starting with `=` is a formula: `+ - * / ^`, comparisons, references (`B2`), ranges (`A1:A5`), and these functions: `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, `SUMIF`, `COUNTIF`, `MEDIAN`, `PRODUCT`, `IF`, `AND`, `OR`, `NOT`, `ROUND`, `ROUNDUP`, `ROUNDDOWN`, `INT`, `ABS`, `SQRT`, `MOD`, `NPV`, `IRR`, `PMT`, `FV`, `PV`, `TODAY`, `DATE`, `DAYS`, `EDATE`, `WORKDAYS`, `YEAR`, `MONTH`, `DAY`, `WEEKDAY`. Dates are written `2027-03-01` in a `date` column. `chart: bar` (or `line`, `pie`) in the head draws the first column's labels against the numbers beside them; `chart: sankey` draws rows of `From | To | Amount` as flows.

A model is a sheet: a column typed `name` names the cell to its right, and formulas use the names (`=visitors*signup_rate/100`; a space is `_`); `lock: C1:C6` in the head marks the model's own formulas, so a reader changes the assumptions and not the model.

Budget:

```
---
title: Budget, October 2026
---
Item | Planned:money | Actual:money | Difference:money
--- | --- | --- | ---
Rent | 1200 | 1200 | =C1-B1
Groceries | 500 | 540 | =C2-B2
Transport | 150 | 120 | =C3-B3
Utilities | 180 | 175 | =C4-B4
Fun | 200 | 260 | =C5-B5
Savings | 400 | 400 | =C6-B6
Total | =SUM(B1:B6) | =SUM(C1:C6) | =SUM(D1:D6)
```

A subscription business:

```
---
title: A subscription business, a month
chart: sankey
lock: C1:C6, E6:E9
---
From | To | Amount:number | Assumption:name | Value:number
--- | --- | --- | --- | ---
Visitors | Signups | =visitors*signup_rate/100 | Visitors | 20000
Visitors | Bounced | =visitors-signups | Signup rate | 6
Signups | Paying | =signups*paid_rate/100 | Paid rate | 25
Signups | Free | =signups-paying | Churn | 8
Paying | Churned | =paying*churn/100 |  |
Paying | Retained | =paying-churned | Signups | =SUMIF(B1:B20, "Signups", C1:C20)
| |  |  | Paying | =SUMIF(B1:B20, "Paying", C1:C20)
| |  |  | Churned | =SUMIF(B1:B20, "Churned", C1:C20)
| |  |  | Retained | =SUMIF(B1:B20, "Retained", C1:C20)
{big=Retained}
```

Templates: Budget, Household budget by month, Expense log, Savings goal, Habit tracker, Reading list, Workout log, Training log, Time sheet, Trip costs split, Project tracker, Schedule with dates, Grade book, Membership roll, Seating count, Poll results, Fundraising thermometer, Invoice ledger, Inventory, Petty cash, Rate card, Mortgages compared, Loans compared, Unit converter, Tournament bracket, Month by month, with a chart, A subscription business, A café, A freelancer, A mutual aid fund. Its own files: `.xlsx`, `.csv`, `.chart.svg`, `.chart.png`.
