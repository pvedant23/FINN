"""Pure financial arithmetic. No model is trusted to calculate ratios."""
from datetime import date
import math

def fiscal_period(value: str) -> str:
    d = date.fromisoformat(value[:10])
    return f'Q{((d.month - 4) % 12) // 3 + 1} FY{(d.year + (d.month >= 4)) % 100:02d}'

def previous_period(period: str, quarters: int = 1) -> str:
    q, fy = period.split()
    n = int(fy[2:]) * 4 + int(q[1:]) - 1 - quarters
    return f'Q{n % 4 + 1} FY{n // 4:02d}'

def crore(value: float, unit: str) -> float:
    factors = {'crore': 1, 'lakh': .01, 'million': .1, 'billion': 100, 'rupees': 1e-7}
    if unit not in factors: raise ValueError('Unsupported unit')
    if not math.isfinite(value): raise ValueError('Non-finite number')
    return value * factors[unit]

def change(current, previous):
    # Negative/zero denominators do not support an ordinary growth percentage.
    if current is None or previous is None or previous <= 0: return None
    return round((current / previous - 1) * 100, 2)

def ebitda(row, sector=''):
    if sector.lower() in {'bank', 'nbfc'}: return None
    keys = ('pbt', 'finance_cost', 'da', 'other_income')
    if any(row.get(k) is None for k in keys): return None
    return row['pbt'] + row['finance_cost'] + row['da'] - row['other_income']

def validate_financial(row):
    issues = []
    if row.get('basis') != 'consolidated': issues.append('Non-consolidated: do not mix')
    for keys in [('total_income','revenue','other_income'), ('pbt','total_income','expenses')]:
        if all(row.get(k) is not None for k in keys):
            expected = row[keys[1]] + row[keys[2]] if keys[0]=='total_income' else row[keys[1]]-row[keys[2]]
            if abs(row[keys[0]]-expected)>2: issues.append(f'{keys[0]} reconciliation failed')
    if all(row.get(k) is not None for k in ['pbt','tax','pat']):
        if abs(row['pbt']-row['tax']-row['pat'])>2: issues.append('PAT reconciliation failed')
    return issues

def compare(rows, period, sector=''):
    by_period={r['period']:r for r in rows if r.get('basis')=='consolidated'}
    current=by_period.get(period)
    if not current: return []
    prev=by_period.get(previous_period(period),{}); year=by_period.get(previous_period(period,4),{})
    metrics=['nii','ppop','pat','gnpa','nnpa','casa'] if sector.lower() in {'bank','nbfc'} else ['revenue','ebitda','pbt','pat']
    def val(r,k): return ebitda(r,sector) if k=='ebitda' else r.get(k)
    return [dict(metric=k,current=val(current,k),previous=val(prev,k),year_ago=val(year,k),qoq=change(val(current,k),val(prev,k)),yoy=change(val(current,k),val(year,k)),margin=(round(val(current,k)/current['revenue']*100,2) if k in ['ebitda','pbt','pat'] and val(current,k) is not None and current.get('revenue') else None),derived=k=='ebitda') for k in metrics]

def promise_verdict(promise, actual, as_of):
    if as_of < promise['due']: return 'Too early'
    if promise.get('withdrawn'): return 'Walked back'
    if not actual or any(actual.get(k)!=promise.get(k) for k in ('metric','horizon','basis','unit')): return 'Not disclosed'
    value=actual.get('value')
    if value is None: return 'Not disclosed'
    low, high=promise.get('low'),promise.get('high')
    if low is None: return 'Not disclosed'
    if value>=low and (high is None or value<=high or promise.get('higher_is_better',True)): return 'Delivered'
    # "Partly" requires explicit component targets, never an arbitrary near-miss tolerance.
    return 'Missed'
