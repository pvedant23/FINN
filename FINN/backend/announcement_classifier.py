"""Announcement-only refinements; the scoring engine remains unchanged."""
import re
from .engine import classify as original

RULES = [
 ('capex',r'expansion of.*(center|centre|plant|capacity)'),
 ('press_release',r'strategic collaboration|innovation awards|branch modernization|successfully delivers|livelihood program'),
 ('routine_compliance',r'loss of share|duplicate.*certificate|dematerial|demat|regulation 74|reconciliation of share|trading window|compliance certificate|certificate under|confirmation.*demat|grant of.*options|annual securities report'),
 ('insider_trading',r'disclosure.*(29\(|31\(|7\(2)|insider|acquisition.*shares.*voting'),
 ('fund_raise',r'allotment.*(securities|equity|shares)|issue of securities|qualified institutional placement|commercial paper|non.convertible|redemption|esop|employee stock'),
 ('earnings_call',r'transcript|recording|earnings call|call with.*(media|analyst)'),
 ('results',r'financial results|financial statements|financial result'),
 ('earnings_call',r'earnings.*call|audio.*record|video.*record|transcript|link of recording'),
 ('investor_meetings',r'analyst|investor.*meet|investor conference|presentation|schedule of meet'),
 ('management_change',r'change in.*(director|management)|appointment|resign|cessation|retirement|continuation.*chairperson'),
 ('agm_egm',r'voting results|scrutiniz|general meeting|proceedings'),
 ('press_release',r'press release|newspaper|media release'),
]
def classify(subject):
    result=original(subject)
    for category,pattern in RULES:
        if re.search(pattern,subject,re.I):
            return dict(category=category,confidence='high',candidates=[category])
    return result
