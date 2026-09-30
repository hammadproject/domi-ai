"""Fair Housing rule tables. Rules-first: cheap regexes decide clear cases; only
genuinely ambiguous input goes to the LLM classifier (saves Gemini quota).

Goal: never steer by race, color, religion, sex, disability, familial status or national
origin (plus age / source-of-income proxies), and never make subjective neighborhood claims.
"""

import re

# Phrases that contain a group word but are ordinary property / place language.
# They are blanked out before any rule runs.
ALLOW_PHRASES = re.compile(
    r"\b(?:"
    r"single[- ]family|multi[- ]family|family[- ]?(?:room|size|sized|home|homes)|"
    r"wheelchair[- ]accessible|handicap[- ]accessible|ada[- ]compliant|accessible|"
    r"mother[- ]in[- ]law|in[- ]law|"
    r"black (?:appliances?|granite|countertops?|cabinets?|fixtures?|roof|tile|stainless|"
    r"canyon|rock|mountain|hills?|forest|oak|walnut|iron|steel|windows?|trim|door)|"
    r"white (?:kitchen|cabinets?|cabinetry|walls?|fence|picket|oak|granite|quartz|marble|"
    r"appliances?|house|paint|brick|stucco|tile|exterior|siding|rock|tank|settlement|"
    r"countertops?|trim|interior|flooring|shaker)|"
    r"indian (?:school|trail|hills?|wells?|creek|springs?|village|bend|ridge|run)|"
    r"(?:mexican|spanish|italian|asian|french|japanese|chinese)[- ](?:tile|tiles|style|"
    r"decor|saltillo|pavers?|architecture|restaurants?|food|revival|colonial)"
    r")\b"
)

# Terms that are (almost) always about people.
_PEOPLE_TERMS = (
    r"hispanics?|latinos?|latinas?|latinx|asians?|african[- ]americans?|caucasians?|"
    r"native[- ]americans?|mexicans?|chinese|koreans?|vietnamese|japanese|arabs?|"
    r"middle[- ]eastern|muslims?|jews?|jewish|christians?|catholics?|hindus?|buddhists?|"
    r"mormons?|sikhs?|atheists?|gay|lesbian|lgbtq?\+?|transgender|trans|queer|same[- ]sex|"
    r"immigrants?|foreigners?|minorit(?:y|ies)|people of color|illegals?|"
    r"disabled|handicapped|section ?8|voucher holders?|welfare|spanish[- ]speaking|"
    r"ethnic|ethnicity|racial|religious|"
    r"women|single (?:women|woman|moms?|mothers?|dads?|fathers?|parents?)|"
    r"seniors?|senior citizens?|elderly|retirees?|old people|young people|"
    r"young professionals?|young singles?|singles|millennials?|empty[- ]nesters?|"
    r"students?|newlyweds?|bachelors?|young families"
)
# Color words only count as people references in these forms.
_COLOR_PEOPLE = (
    r"blacks|whites|indians|"
    r"(?:black|white|indian)[- ](?:people|folks|families|residents|neighbors|community|"
    r"communities|neighborhoods?|buyers|population|individuals|owners)|"
    r"(?:all|mostly|mainly|majority|predominantly|primarily|heavily)[- ](?:black|white|indian)"
)
# Very common in legitimate requests about one's own needs, so they only matter with
# place / steering context.
_FAMILY_TERMS = r"families|kids|children|parents|toddlers|babies|family[- ]friendly|kid[- ]friendly"

_STRICT = f"{_PEOPLE_TERMS}|{_COLOR_PEOPLE}"
_ANY = f"{_STRICT}|{_FAMILY_TERMS}"
GROUP_STRICT = re.compile(rf"\b(?:{_STRICT})\b")
GROUP_ANY = re.compile(rf"\b(?:{_ANY})\b")

PLACE = re.compile(
    r"\b(?:neighbou?rhoods?|areas?|communit(?:y|ies)|parts? of (?:town|the city)|"
    r"sides? of town|suburbs?|districts?|zip codes?|streets?|subdivisions?|towns?|"
    r"live|living|lives|reside|settle|residents|surrounded by|being around|live around|"
    r"next door|neighbors|neighbours|people who live|crowd)\b"
)
PLACE_OF_WORSHIP = re.compile(r"\b(?:church(?:es)?|mosques?|synagogues?|temples?|gurdwaras?)\b")

_EVAL = (
    r"best|good|great|safe|safest|top|ideal|perfect|right|suitable|nice|popular|welcoming|"
    r"friendly|comfortable|recommend(?:ed)?|preferred|desirable|appropriate|better"
)
_AVOID = (
    r"avoid|stay away from|keep away from|away from|steer (?:me )?(?:clear of|away from)|"
    r"not near|not next to|don'?t want|do not want|no|without|free of|exclude|fewest|few|"
    r"least|fewer|zero|hate|not many"
)
_CONC = (
    r"mostly|mainly|majority|predominantly|primarily|lots of|many|full of|filled with|"
    r"high concentration of|heavily|all|only|dominated by|most|a lot of|plenty of|with"
)

FAMILIAL = re.compile(
    r"\b(?:adults?[- ]only|no (?:kids|children|families)|without (?:kids|children)|"
    r"child[- ]?free|kid[- ]?free|no (?:elderly|seniors|old people))\b"
)
DEMOGRAPHIC = re.compile(
    r"\b(?:demographics?|racial (?:makeup|mix|composition|breakdown)|"
    r"ethnic (?:makeup|mix|composition|diversity)|religious (?:makeup|mix|composition)|"
    r"diverse|diversity|racial|ethnicity|ethnic)\b"
)
SAFETY = re.compile(
    r"\b(?:crime|crimes|criminal|dangerous|sketchy|ghettos?|shady|unsafe|"
    r"bad (?:area|areas|neighborhood|neighborhoods|part of town)|"
    r"rough (?:area|areas|neighborhood|neighborhoods)|"
    r"(?:class|type|kind|quality) of (?:people|residents|neighbors)|"
    r"safe(?:r|st)? (?:neighborhoods?|areas?|communit(?:y|ies)|streets?|parts? of town|"
    r"sides? of town|suburbs?)|"
    r"(?:neighborhood|area|street|community)s? (?:is|are|feels?|seems?)(?: very| really)? "
    r"(?:safe|unsafe|rough|dangerous|bad))\b"
)
SAFETY_LOOSE = re.compile(
    r"\b(?:rough|dangerous|sketchy|bad|unsafe)\b.{0,15}\b(?:area|neighborhood)\b"
)

WHERE_LIVE = re.compile(
    rf"\bwhere\b.{{0,40}}\b(?:{_STRICT})\b.{{0,25}}\b(?:live|settle|stay|reside|congregate)\b|"
    rf"\b(?:{_STRICT})\b.{{0,40}}\bwhere\b.{{0,25}}\b(?:live|settle|stay|reside|move)\b|"
    r"\baround (?:my own|my kind|people like me|my people|others like me)\b"
)
# "mostly white", "predominantly indian" next to place language is a concentration claim
COLOR_CONCENTRATION = re.compile(
    r"\b(?:all|mostly|mainly|majority|predominantly|primarily|heavily)[- ](?:black|white|indian)\b"
)
GROUP_FRIENDLY = re.compile(r"\b(?:family|kid|child|senior|student|lgbtq?)[- ]friendly\b")
# evaluative word ... for/with/among ... group      ("best area for families")
EVAL_FOR_GROUP = re.compile(
    rf"\b(?:{_EVAL})\b.{{0,60}}\b(?:for|to|with|among)\b.{{0,25}}\b(?:{_ANY})\b"
)
# avoid / prefer / concentration word ... group      ("avoid areas with immigrants")
LEAD_GROUP = re.compile(rf"\b(?:{_AVOID}|{_CONC})\b.{{0,40}}\b(?:{_ANY})\b")
LEAD_GROUP_STRICT = re.compile(rf"\b(?:{_AVOID}|{_CONC})\b.{{0,40}}\b(?:{_STRICT})\b")
GROUP_PLACE = re.compile(rf"\b(?:{_STRICT})\b.{{0,25}}\b(?:neighborhoods?|areas?|communit\w*)\b")
LIVING_NEAR = re.compile(r"\b(?:live|living|near|around|next to|neighbou?rs?)\b")
FIRST_PERSON = re.compile(r"\b(?:i|we|my|me)\b")


def hard_category(text: str) -> tuple[str, str] | None:
    """Return (category, rule) when the message clearly steers, else None.
    `text` must be lowercased with ALLOW_PHRASES already neutralised."""
    place = PLACE.search(text) is not None
    strict = GROUP_STRICT.search(text) is not None
    any_group = strict or GROUP_ANY.search(text) is not None

    if FAMILIAL.search(text):
        return "familial_status", "familial-status preference"
    if SAFETY.search(text) or SAFETY_LOOSE.search(text):
        return "neighborhood_quality", "crime/safety/quality characterisation"
    if DEMOGRAPHIC.search(text) and place:
        return "demographic", "demographic request about an area"
    if (strict or "my own" in text or "people like me" in text) and WHERE_LIVE.search(text):
        return "steering", "where should <group> live"
    if place and COLOR_CONCENTRATION.search(text):
        return "steering", "concentration of a group in an area"
    if place and GROUP_FRIENDLY.search(text):
        return "steering", "'<group>-friendly' area"
    if place and any_group:
        if EVAL_FOR_GROUP.search(text):
            return "steering", "evaluative 'for <group>' about an area"
        if LEAD_GROUP.search(text):
            return "steering", "prefer/avoid area by group"
        if GROUP_PLACE.search(text):
            return "steering", "<group> neighborhood"
    if strict and LEAD_GROUP_STRICT.search(text) and LIVING_NEAR.search(text):
        return "steering", "avoid <group>"
    return None


def is_ambiguous(text: str) -> bool:
    """Not clearly steering, but mentions a group or place of worship in a way that could be."""
    if PLACE_OF_WORSHIP.search(text):
        return True
    place = PLACE.search(text) is not None
    if GROUP_STRICT.search(text):
        return place or not FIRST_PERSON.search(text)
    return place and GROUP_ANY.search(text) is not None


REFUSALS = {
    "steering": (
        "I can't recommend or filter neighborhoods based on who lives there or who they're "
        "'best for' (race, religion, family status, disability, national origin and similar). "
        "Fair Housing rules exist to keep home search fair for everyone. I'm happy to search "
        "by objective criteria instead: price, bedrooms, square footage, property type, "
        "location, or features. What are your budget and must-haves?"
    ),
    "demographic": (
        "I don't provide demographic information about neighborhoods, and I can't choose "
        "areas based on who lives there. I can help you search by price, size, property "
        "type, location and features. What would you like to see?"
    ),
    "familial_status": (
        "I can't filter or recommend homes by whether children, families or particular age "
        "groups live there; that would run against Fair Housing rules. I can search by "
        "price, size, features and location. What matters most to you in the home itself?"
    ),
    "neighborhood_quality": (
        "I don't have crime or safety data and can't characterise a neighborhood as safe, "
        "unsafe, or 'good' or 'bad'. For that, please use official local sources such as the "
        "local police department's public data. I can search by objective criteria: price, "
        "size, property type, location and features."
    ),
    "unverified": (
        "I couldn't confirm that request is okay to answer under Fair Housing guidelines. "
        "Could you rephrase it in terms of price, size, property type, location or features?"
    ),
}
