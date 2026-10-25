"""Small domain dictionary for the intelligent search. Keys and values are single normalised words
(lower case, singular for English; Arabic without the article). Edit freely: a query word also matches its synonyms,
ranked a little lower than the word itself."""

SYN = {
    # --- Arabic -> English words found in the catalogue
    "كونتاكتور": ["contactor"], "كونتكتور": ["contactor"], "كونتاكتر": ["contactor"],
    "قاطع": ["breaker", "mccb", "mcb"], "بريكر": ["breaker", "mccb", "mcb"], "فاصل": ["breaker", "mcb"], "فواصل": ["breaker", "mcb"],
    "ريليه": ["relay"], "ريلاي": ["relay"], "مرحل": ["relay"], "رليه": ["relay"],
    "زر": ["push", "button"], "ازرار": ["push", "button"], "ضاغط": ["push", "button"],
    "لمبه": ["lamp", "signal", "pilot"], "لمبات": ["lamp", "signal"], "مصباح": ["lamp", "signal"], "كشاف": ["lamp"],
    "محول": ["transformer", "trafo"], "ترانس": ["transformer", "trafo"], "ترانسفورمر": ["transformer"],
    "مؤقت": ["timer"], "تايمر": ["timer"], "مفتاح": ["switch", "selector"], "سويتش": ["switch"],
    "صندوق": ["box", "enclosure", "cabinet"], "علبه": ["box", "enclosure"], "لوحه": ["panel", "board", "cabinet"], "دولاب": ["cabinet"],
    "حمايه": ["protection"], "حامي": ["protection"], "محرك": ["motor"], "موتور": ["motor"],
    "انفرتر": ["drive", "altivar", "inverter"], "درايف": ["drive", "altivar"], "فريكونسي": ["drive", "altivar"],
    "ارضي": ["earthing"], "تاريض": ["earthing"], "قضبان": ["busbar", "bar"], "بسبار": ["busbar"], "نحاس": ["copper"],
    "مصهر": ["fuse"], "فيوز": ["fuse"], "كابل": ["cable", "wire"], "سلك": ["wire", "cable"], "عداد": ["meter"],
    "تيار": ["current"], "تفاضلي": ["residual", "rcd", "rcbo", "vigi"], "تسرب": ["residual", "rcd", "vigi"], "صاعقه": ["surge"],
    "بدايه": ["start", "starter"], "ناعم": ["soft"], "سكه": ["rail", "din"], "مكثف": ["capacitor"], "مكثفات": ["capacitor"],
    "طارئ": ["emergency"], "ايقاف": ["stop", "emergency"], "تحويل": ["changeover", "transfer"], "مصدر": ["supply", "power"],
    # --- English shop talk
    "breaker": ["mcb", "mccb", "cb", "circuit"], "mcb": ["breaker", "miniature"], "mccb": ["breaker", "molded", "compact"],
    "cb": ["breaker", "circuit"], "inverter": ["drive", "altivar"], "vfd": ["drive", "altivar"], "drive": ["altivar", "inverter"],
    "rcd": ["residual", "rcbo", "rcb", "vigi"], "elcb": ["residual", "rcd", "vigi"], "gfci": ["residual", "rcd"],
    "softstarter": ["soft", "start"], "starter": ["start", "soft"], "plc": ["zelio", "smart", "relay"],
    "pushbutton": ["push", "button"], "pilot": ["lamp", "signal"], "led": ["lamp", "signal"], "ups": ["supply", "power"],
    "psu": ["supply", "power"], "trafo": ["transformer"], "ct": ["current", "transformer"], "spd": ["surge", "protection"],
    "ats": ["transfer", "atcbs"], "mts": ["transfer", "manual"], "contacteur": ["contactor"], "disjoncteur": ["breaker", "mcb"],
}
