"""Country normalisation: ISO codes, demonyms and spellings to one name."""
import re
import unicodedata

CODES = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AR": "Argentina", "AM": "Armenia",
    "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan", "BH": "Bahrain", "BD": "Bangladesh",
    "BE": "Belgium", "BA": "Bosnia and Herzegovina", "BR": "Brazil", "VG": "British Virgin Islands",
    "BG": "Bulgaria", "CA": "Canada", "CL": "Chile", "CN": "China", "CO": "Colombia", "CR": "Costa Rica",
    "CI": "Cote d'Ivoire", "HR": "Croatia", "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark",
    "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt", "ER": "Eritrea", "EE": "Estonia",
    "ET": "Ethiopia", "FI": "Finland", "FR": "France", "GE": "Georgia", "DE": "Germany", "GH": "Ghana",
    "GR": "Greece", "GT": "Guatemala", "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong",
    "HU": "Hungary", "IS": "Iceland", "IN": "India", "ID": "Indonesia", "IR": "Iran", "IQ": "Iraq",
    "IE": "Ireland", "IL": "Israel", "IT": "Italy", "JM": "Jamaica", "JP": "Japan", "JE": "Jersey",
    "JO": "Jordan", "KZ": "Kazakhstan", "KE": "Kenya", "XK": "Kosovo", "KW": "Kuwait", "LV": "Latvia",
    "LB": "Lebanon", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macao",
    "MY": "Malaysia", "MT": "Malta", "MX": "Mexico", "MD": "Moldova", "MC": "Monaco", "ME": "Montenegro",
    "MA": "Morocco", "NL": "Netherlands", "NZ": "New Zealand", "NI": "Nicaragua", "NG": "Nigeria",
    "KP": "North Korea", "MP": "Northern Mariana Islands", "NO": "Norway", "OM": "Oman", "PK": "Pakistan",
    "PS": "Palestine", "PA": "Panama", "PY": "Paraguay", "PE": "Peru", "PH": "Philippines", "PL": "Poland",
    "PT": "Portugal", "PR": "Puerto Rico", "QA": "Qatar", "RO": "Romania", "RU": "Russia",
    "SA": "Saudi Arabia", "RS": "Serbia", "SL": "Sierra Leone", "SG": "Singapore", "SK": "Slovakia",
    "SI": "Slovenia", "SO": "Somalia", "ZA": "South Africa", "KR": "South Korea", "ES": "Spain",
    "LK": "Sri Lanka", "SD": "Sudan", "SE": "Sweden", "CH": "Switzerland", "SY": "Syria", "TW": "Taiwan",
    "TH": "Thailand", "TT": "Trinidad and Tobago", "TN": "Tunisia", "TR": "Turkey", "UG": "Uganda",
    "UA": "Ukraine", "AE": "United Arab Emirates", "GB": "United Kingdom", "UK": "United Kingdom",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VE": "Venezuela", "VN": "Vietnam",
    "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe", "GG": "Guernsey", "IM": "Isle of Man",
    "GI": "Gibraltar", "CM": "Cameroon", "NP": "Nepal", "BY": "Belarus", "SN": "Senegal", "ML": "Mali", "NE": "Niger", "TD": "Chad", "CD": "DR Congo", "CG": "Congo", "AO": "Angola", "MZ": "Mozambique", "TZ": "Tanzania", "RW": "Rwanda", "LY": "Libya", "KG": "Kyrgyzstan", "TJ": "Tajikistan", "TM": "Turkmenistan", "MN": "Mongolia", "MM": "Myanmar", "KH": "Cambodia", "LA": "Laos", "BT": "Bhutan", "MV": "Maldives", "BO": "Bolivia", "CU": "Cuba", "SV": "El Salvador", "MK": "North Macedonia", "BA": "Bosnia and Herzegovina", "MU": "Mauritius", "KY": "Cayman Islands", "BM": "Bermuda", "BS": "Bahamas", "BB": "Barbados",
}

NAMES = {v for v in CODES.values()}

ALIASES = {
    "usa": "United States", "united states of america": "United States", "u.s.": "United States",
    "u.s.a.": "United States", "america": "United States", "great britain": "United Kingdom",
    "britain": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom",
    "wales": "United Kingdom", "northern ireland": "United Kingdom", "uk": "United Kingdom",
    "the netherlands": "Netherlands", "holland": "Netherlands", "czechia": "Czech Republic",
    "ivory coast": "Cote d'Ivoire", "cote divoire": "Cote d'Ivoire", "palestina": "Palestine",
    "russian federation": "Russia", "korea, republic of": "South Korea", "republic of korea": "South Korea",
    "korea, democratic people's republic of": "North Korea", "dprk": "North Korea",
    "macao special administrative region of china": "Macao", "macau": "Macao",
    "hong kong special administrative region of china": "Hong Kong", "viet nam": "Vietnam",
    "turkiye": "Turkey", "democratic republic of the congo": "DR Congo", "drc": "DR Congo", "burma": "Myanmar", "macedonia": "North Macedonia", "uae": "United Arab Emirates", "republic of ireland": "Ireland",
    "eire": "Ireland", "ceylon": "Sri Lanka", "east pakistan": "Bangladesh",
    "syrian arab republic": "Syria", "iran, islamic republic of": "Iran", "moldova, republic of": "Moldova",
}

DEMONYMS = {
    "afghan": "Afghanistan", "albanian": "Albania", "algerian": "Algeria", "argentine": "Argentina",
    "argentinian": "Argentina", "armenian": "Armenia", "australian": "Australia", "austrian": "Austria",
    "azerbaijani": "Azerbaijan", "bahraini": "Bahrain", "bangladeshi": "Bangladesh", "belgian": "Belgium",
    "bosnian": "Bosnia and Herzegovina", "brazilian": "Brazil", "british": "United Kingdom",
    "bulgarian": "Bulgaria", "canadian": "Canada", "chilean": "Chile", "chinese": "China",
    "colombian": "Colombia", "costa rican": "Costa Rica", "ivorian": "Cote d'Ivoire", "croatian": "Croatia",
    "cypriot": "Cyprus", "czech": "Czech Republic", "danish": "Denmark", "dominican": "Dominican Republic",
    "dutch": "Netherlands", "ecuadorian": "Ecuador", "egyptian": "Egypt", "eritrean": "Eritrea",
    "estonian": "Estonia", "ethiopian": "Ethiopia", "finnish": "Finland", "french": "France",
    "georgian": "Georgia", "german": "Germany", "ghanaian": "Ghana", "greek": "Greece",
    "guatemalan": "Guatemala", "haitian": "Haiti", "honduran": "Honduras", "hungarian": "Hungary",
    "icelandic": "Iceland", "indian": "India", "indonesian": "Indonesia", "iranian": "Iran",
    "iraqi": "Iraq", "irish": "Ireland", "israeli": "Israel", "italian": "Italy", "jamaican": "Jamaica",
    "japanese": "Japan", "jordanian": "Jordan", "kazakh": "Kazakhstan", "kenyan": "Kenya",
    "kosovar": "Kosovo", "kuwaiti": "Kuwait", "latvian": "Latvia", "lebanese": "Lebanon",
    "lithuanian": "Lithuania", "luxembourgish": "Luxembourg", "malaysian": "Malaysia", "maltese": "Malta",
    "mexican": "Mexico", "moldovan": "Moldova", "montenegrin": "Montenegro", "moroccan": "Morocco",
    "new zealander": "New Zealand", "nicaraguan": "Nicaragua", "nigerian": "Nigeria",
    "north korean": "North Korea", "norwegian": "Norway", "omani": "Oman", "pakistani": "Pakistan",
    "palestinian": "Palestine", "panamanian": "Panama", "paraguayan": "Paraguay", "peruvian": "Peru",
    "filipino": "Philippines", "philippine": "Philippines", "polish": "Poland", "portuguese": "Portugal",
    "puerto rican": "Puerto Rico", "qatari": "Qatar", "romanian": "Romania", "russian": "Russia",
    "saudi": "Saudi Arabia", "serbian": "Serbia", "sierra leonean": "Sierra Leone",
    "singaporean": "Singapore", "slovak": "Slovakia", "slovenian": "Slovenia", "somali": "Somalia",
    "south african": "South Africa", "south korean": "South Korea", "spanish": "Spain",
    "sri lankan": "Sri Lanka", "sudanese": "Sudan", "swedish": "Sweden", "swiss": "Switzerland",
    "syrian": "Syria", "taiwanese": "Taiwan", "thai": "Thailand", "trinidadian": "Trinidad and Tobago",
    "tunisian": "Tunisia", "turkish": "Turkey", "ugandan": "Uganda", "ukrainian": "Ukraine",
    "emirati": "United Arab Emirates", "american": "United States", "uruguayan": "Uruguay",
    "uzbek": "Uzbekistan", "venezuelan": "Venezuela", "vietnamese": "Vietnam", "yemeni": "Yemen",
    "zambian": "Zambia", "zimbabwean": "Zimbabwe", "english": "United Kingdom", "scottish": "United Kingdom",
    "welsh": "United Kingdom", "kiwi": "New Zealand", "cameroonian": "Cameroon", "nepali": "Nepal", "nepalese": "Nepal", "belarusian": "Belarus", "senegalese": "Senegal", "malian": "Mali", "chadian": "Chad", "congolese": "DR Congo", "angolan": "Angola", "tanzanian": "Tanzania", "rwandan": "Rwanda", "libyan": "Libya", "mongolian": "Mongolia", "burmese": "Myanmar", "cambodian": "Cambodia", "bolivian": "Bolivia", "cuban": "Cuba", "salvadoran": "El Salvador", "macedonian": "North Macedonia",
}

NOT_COUNTRIES = {"international", "europe", "global", "worldwide", "n/a", "unknown", "africa", "asia",
                 "middle east", "latin america", "eu", "european union"}


def _key(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", s)
    s = s.replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", s).strip().lower()


_lookup = {}
for n in NAMES:
    _lookup[_key(n)] = n
for k, v in ALIASES.items():
    _lookup[_key(k)] = v
for k, v in DEMONYMS.items():
    _lookup[k] = v


def norm(value):
    """One value (name, code, demonym, or 'City, Region, Country') -> country or None."""
    if not value:
        return None
    raw = str(value).strip()
    if len(raw) in (2, 3) and raw.upper() in CODES and raw.isupper():
        return CODES[raw.upper()]
    k = _key(raw)
    if not k or k in NOT_COUNTRIES:
        return None
    if k in _lookup:
        return _lookup[k]
    if "," in k:
        return norm(k.split(",")[-1])
    if k.upper() in CODES and len(k) == 2:
        return CODES[k.upper()]
    # unknown but plausible country name: keep it, title-cased
    return raw.strip().title() if len(k) > 2 else None


# For scanning free text: longest phrases first
_scan = sorted(set(list(_lookup.keys())), key=len, reverse=True)
_scan_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in _scan) + r")\b")


def in_text(text):
    """All countries mentioned in free text (names, aliases, demonyms)."""
    if not text:
        return []
    k = _key(text)
    out = []
    for m in _scan_re.finditer(k):
        c = _lookup[m.group(1)]
        if c not in out:
            out.append(c)
    return out
