"""
Money / Wealth Split — Consumer Engine Sec 7.

Never equate one house with all wealth. Separate:
2nd accumulation, 5th speculation, 6th employment/debt, 8th joint/sudden,
10th profession, 11th gains, 12th expenditure/foreign.
Business adds 3rd/7th/D10/D2.
Financial discipline first; remedies only supportive.
"""

from dataclasses import dataclass
from typing import Dict, List
from ..core.chart import D1Chart

HOUSE_MEANINGS = {
    2: "accumulation / resources / savings pattern",
    5: "intelligence / investment / speculation judgment",
    6: "employment / service / debt / competition",
    8: "joint resources / sudden changes / inheritance / transformation",
    10: "profession / action / status",
    11: "gains / income / network fulfilment",
    12: "expenditure / loss / foreign / withdrawal",
}

BUSINESS_HOUSES = {
    3: "enterprise / initiative / courage",
    7: "commerce / market / partnership",
}


@dataclass
class MoneyBreakdown:
    per_house: Dict[int, str]  # house -> chart-specific note
    business_note: str
    discipline_first_note: str


def analyse_money(d1: D1Chart, for_business: bool = False) -> MoneyBreakdown:
    per: Dict[int, str] = {}
    for h, meaning in HOUSE_MEANINGS.items():
        hs = d1.houses[h]
        lord = hs.lord
        lp = d1.planets[lord]
        occ = ", ".join(hs.occupants) if hs.occupants else "no occupants"
        asp = ", ".join(hs.aspecting_planets) if hs.aspecting_planets else "no major aspects"
        per[h] = (f"{h}H ({meaning}): sign {hs.sign}, lord {lord} in {lp.house}H/{lp.sign} "
                  f"({lp.dignity}); occupants: {occ}; aspects: {asp}.")

    business_note = ""
    if for_business:
        parts = []
        for h, meaning in BUSINESS_HOUSES.items():
            hs = d1.houses[h]
            parts.append(f"{h}H ({meaning}): lord {hs.lord} in {d1.planets[hs.lord].house}H ({d1.planets[hs.lord].dignity}).")
        business_note = ("Business lens — " + " ".join(parts) +
                         " Confirm with D10 professional manifestation and D2 resource pattern; "
                         "never judge business from one house.")
    discipline = ("For financial remedies, practical financial discipline comes first — budgeting, savings, "
                  "risk management, professional advice, legal compliance. Traditional remedies below are "
                  "supportive spiritual/behavioural practices, not substitutes.")
    return MoneyBreakdown(per_house=per, business_note=business_note, discipline_first_note=discipline)
