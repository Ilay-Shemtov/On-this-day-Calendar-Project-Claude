"""Sensitive-topic filter: "history, not true crime".

Each item is classified from its text plus the Wikipedia short descriptions of the
articles it links to (e.g. "American serial killer", "1999 school shooting in Colorado").

  ALWAYS DROPPED   sexual crimes; violence against children; items about serial killers,
                   mass murderers and similar perpetrators; graphic violence (torture,
                   mutilation, lynching...); massacres and mass shootings outside a war or
                   political context; ordinary murders; suicides.
  KEPT             wars, battles, revolutions, coups and everything else in a war context;
                   assassinations of political figures; violence against protesters by
                   state forces. Atrocities inside a war (massacres, genocide) follow the
                   `war_atrocities` setting.
  KEPT IF FAMOUS   crimes that are not gruesome and court cases (e.g. the O. J. Simpson
                   verdict), disasters and accidents, terrorism outside a war context
                   (stricter threshold), criminals in the births/deaths lists.

"Famous" = the number of Wikimedia sites with an article on the topic (Wikidata sitelinks).
Anything the rules get wrong can be fixed in overrides.toml.

To see how a line would be treated:  python -m otd check "text of the event"
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _rx(*parts: str, flags: int = re.IGNORECASE) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", flags)


# --- context: these make violent words acceptable --------------------------------

_NOT_JUST_A_JOB = r"(?! (?:major|captain|colonel|lieutenant|sergeant|private|officer|veteran|psychiatrist|doctor|base|post|reserve|academy|recruiter|deserter)\b)"
WAR = _rx(
    r"wars?", r"warfare", r"wartime", r"battles?", r"battlefield", r"siege", r"besieg\w*",
    r"invasions?", r"invad\w*", r"armies", r"army" + _NOT_JUST_A_JOB, r"troops", r"soldiers?",
    r"military" + _NOT_JUST_A_JOB, r"navy" + _NOT_JUST_A_JOB, r"naval", r"marines",
    r"air force" + _NOT_JUST_A_JOB, r"airstrikes?", r"air raids?", r"bombard\w*",
    r"shelling", r"offensive", r"counter-?offensive", r"front lines?", r"forces", r"allies",
    r"allied", r"guerrillas?", r"insurgen\w*", r"rebels?", r"rebellion", r"revolts?", r"mutiny",
    r"mutineers", r"uprisings?", r"insurrection", r"partisans", r"militias?", r"paramilitar\w*",
    r"armistice", r"cease-?fire", r"truce", r"surrender\w*", r"capitulat\w*", r"genocide",
    r"holocaust", r"nazis?", r"wehrmacht", r"luftwaffe", r"gestapo", r"einsatzgruppen",
    r"concentration camps?", r"death camps?", r"khmer rouge", r"red army", r"viet cong",
    r"crusades?", r"crusaders?", r"conquest", r"conquistadors?", r"legions?", r"fleets?",
    r"warships?", r"battleships?", r"u-boats?", r"submarines?", r"kamikaze", r"atomic bomb\w*",
    r"nuclear weapons?", r"the troubles", r"intifada", r"national guard", r"cavalry", r"dragoons",
    r"regiments?", r"commandos?", r"navy seals", r"paratroop\w*", r"artillery", r"warlords?",
    r"blitz(?:krieg)?",
)

POLITICAL = _rx(
    r"assassinat\w*", r"assassins?", r"coups?", r"coup d'[ée]tat", r"putsch", r"protest\w*",
    r"demonstrators?", r"demonstrations", r"revolution\w*", r"regime", r"juntas?", r"dictator\w*",
    r"apartheid", r"civil rights", r"independence", r"riots?", r"rioting", r"rioters", r"unrest",
    r"martial law", r"crackdown", r"dissidents?", r"political prisoners?", r"secret police",
    r"segregation",
)
ASSASSINATION = _rx(r"assassinat\w*", r"assassins?")
# A massacre counts as political history (Sharpeville, Bloody Sunday) only when state forces did it.
STATE_ACTOR = _rx(
    r"police(?:men)?", r"regime", r"government", r"security forces", r"state forces", r"authorities",
    r"juntas?", r"colonial", r"gendarm\w*", r"secret police", r"soldiers", r"troops",
)

# A murder whose victim is one of these is treated as a political assassination.
POLITICAL_FIGURE = _rx(
    r"politician", r"president", r"prime minister", r"chancellor", r"premier", r"ministers?",
    r"senator", r"congress(?:wo)?man", r"governor", r"mayor", r"kings?", r"queens?", r"monarch",
    r"emperor", r"empress", r"tsar(?:ina)?", r"czar", r"sultan", r"shah", r"pharaoh", r"popes?",
    r"archbishop", r"princes?", r"princess", r"duke", r"duchess", r"archduke", r"regent",
    r"revolutionary", r"activist", r"civil rights leader", r"statesman", r"stateswoman",
    r"diplomat", r"head of (?:state|government)", r"dictator", r"caliph", r"journalist",
)

LEGAL = _rx(
    r"(?<!clinical )(?<!time )trials?", r"tried (?:for|in|by)", r"acquitt\w*", r"convict(?:ed|ion|ions)",
    r"verdicts?", r"jury", r"jurors?", r"sentenc(?:ed|ing)", r"pleads? guilty", r"pleaded guilty",
    r"found (?:not )?guilty", r"indict\w*", r"arraign\w*", r"exonerat\w*", r"pardon\w*", r"courts?",
    r"extradit\w*", r"executed", r"execution", r"hanged",
)

# --- always-drop material --------------------------------------------------------

SEXUAL = _rx(
    r"rap(?:e|ed|es|ist|ists|ing)", r"sexual(?:ly)? (?:assault\w*|abus\w*|violence|harass\w*|exploit\w*|slavery|offen[cs]es?|predators?|misconduct)",
    r"molest\w*", r"pa?edophil\w*", r"child pornography", r"child sex\w*", r"sex offenders?",
    r"sex trafficking", r"sex crimes?", r"sex abuse", r"incest\w*", r"indecent assault", r"grooming gangs?",
)

CHILD = _rx(
    r"child", r"children", r"kids?", r"bab(?:y|ies)", r"infants?", r"toddlers?", r"newborns?",
    r"schoolchild(?:ren)?", r"schoolgirls?", r"schoolboys?", r"pupils", r"kindergarten",
    r"nursery school", r"day ?care", r"orphanage", r"elementary school", r"primary school", r"minors",
)
CHILD_AGE = re.compile(r"\b(\d{1,2})-(year|month|week|day)-old\b", re.IGNORECASE)

KILLER_STRONG = _rx(
    r"serial killers?", r"spree killers?", r"mass murderers?", r"mass shooters?", r"spree shooters?",
    r"school shooters?", r"contract killers?", r"hitm[ae]n", r"cannibals?", r"rapists?", r"sex offenders?",
    r"child molesters?", r"pa?edophiles?", r"child abusers?", r"child murderers?", r"stranglers?",
)
# Only count when the description is clearly about a person (or in the births/deaths lists).
KILLER_WEAK = _rx(r"murderers?", r"killers?(?! whales?)", r"terrorists?", r"cult leaders?", r"torturers?", r"poisoners?")

GORE = _rx(
    r"tortur\w*", r"mutilat\w*", r"dismember\w*", r"decapitat\w*", r"disembowel\w*", r"cannibal\w*",
    r"(?:burned|burnt|buried|skinned|boiled|eaten|roasted) alive", r"flay(?:ed|ing)", r"impal(?:ed|ement|ing)",
    r"acid attacks?", r"lynch\w*", r"beheading videos?", r"gruesome", r"grisly",
)

MASS = _rx(
    r"massacre[sd]?", r"mass shootings?", r"school shootings?", r"shooting spree", r"spree (?:killings?|shootings?)",
    r"killing spree", r"rampage", r"gunm[ae]n", r"(?<!person )shooters?(?! games?)",
    r"(?<!sport )(?<!sports )shootings?(?! (?:stars?|of (?:the|a) (?:film|movie)))", r"opens? fire", r"opened fire",
    r"mass (?:murders?|killings?|stabbings?|graves?)", r"pogroms?", r"hate crimes?", r"genocides?",
    r"holocaust", r"ethnic cleansing", r"death squads?", r"death camps?", r"extermination camps?",
    r"gas chambers?", r"bloodbath", r"slaughter(?:ed|s|ing)?", r"atrocit\w*", r"war crimes?",
)

MURDER = _rx(
    r"murder\w*", r"homicides?", r"manslaughter", r"strangl\w*", r"stabbed", r"stabbings?", r"shot dead",
    r"shot and killed", r"shoots? (?:and kills?|dead)", r"fatally (?:shot|shoots?|stabbed|stabs?)",
    r"gunned down", r"beaten to death", r"bludgeon\w*", r"poisoned",
    r"hono(?:u)?r killings?", r"femicides?", r"infanticide", r"matricide", r"patricide", r"parricide",
    r"killed by (?:his|her) (?:husband|wife|partner|boyfriend|girlfriend|father|mother|son|daughter)",
)

SUICIDE = _rx(
    r"suicides?(?! (?:bomb\w*|attack\w*|missions?|squads?|vests?|cars?|runs?))",
    r"kill(?:s|ed) (?:himself|herself|themselves)", r"t(?:ook|akes) (?:his|her|their) own li(?:fe|ves)",
    r"overdos\w*", r"self-immolat\w*",
)

ABUSE = _rx(r"abus\w*", r"maltreat\w*", r"neglect\w*")
KIDNAP = _rx(r"kidnap\w*", r"abduct\w*")
HOSTAGE_TERROR = _rx(r"terroris\w*", r"suicide bomb\w*", r"hostages?")

# --- kept only when famous ---------------------------------------------------------

TERROR = _rx(
    r"terroris\w*", r"suicide (?:bomb\w*|attacks?|attackers?)", r"(?:car|truck|letter|nail|pipe|barrel)[ -]bomb\w*",
    r"bomb attacks?", r"bombings?", r"al-?qa[ei]da", r"al-?qaida", r"islamic state", r"boko haram",
    r"aum shinrikyo", r"sarin", r"anthrax attacks?", r"unabomber", r"jihadis\w*",
)
TERROR_CS = re.compile(r"\b(?:ISIS|ISIL|IS militants)\b")  # case-sensitive: not the goddess Isis

CRIME = _rx(
    r"(?<!cardiac )(?<!respiratory )arrest(?:s|ed|ing)?", r"taken into custody", r"detained", r"convict\w*",
    r"sentenced", r"acquitt\w*", r"(?<!clinical )(?<!time )trials?", r"indict\w*", r"robber(?:y|ies|s)?",
    r"robbed", r"heists?", r"theft", r"thie(?:f|ves)", r"stolen", r"stole", r"steal(?:s|ing)?", r"burglar\w*",
    r"fraud\w*", r"embezzl\w*", r"brib(?:e|es|ed|ery|ing)", r"extort\w*", r"smuggl\w*", r"counterfeit\w*",
    r"forger(?:y|ies)", r"ponzi", r"racketeer\w*", r"gangsters?", r"mobsters?", r"mafia", r"mafioso",
    r"cartels?", r"organi[sz]ed crime", r"crimes?(?! (?:writer|novel\w*|fiction|author|drama|film|thriller|series))",
    r"criminals?(?! (?:law\w*|lawyer|defen[cs]e|justice|code|procedure|court|psycholog\w*|investigat\w*))",
    r"prison break", r"escape[sd]? from (?:prison|jail)", r"jailbreak", r"hijack\w*", r"hostages?",
    r"kidnap\w*", r"abduct\w*", r"outlaws?", r"bandits?", r"piracy", r"(?<!pittsburgh )pirates?",
    r"arson\w*", r"looting", r"scandal",
)

CRIME_PERSON = _rx(
    r"criminal(?! (?:law\w*|lawyer|defen[cs]e|justice|psycholog\w*|investigat\w*))", r"gangsters?", r"mobsters?",
    r"mafios[oi]", r"mafia (?:boss|figure|member)", r"crime (?:boss|lord|figure|family)",
    r"drug (?:lord|kingpin|trafficker|dealer|baron)", r"narco\w*", r"(?:bank )?robbers?", r"outlaws?", r"bandits?",
    r"con (?:artist|man)", r"conman", r"fraudsters?", r"swindlers?", r"embezzlers?", r"smugglers?", r"thie(?:f|ves)",
    r"burglars?", r"forgers?", r"counterfeiters?", r"kidnappers?", r"hijackers?", r"(?<!pittsburgh )pirates?",
    r"convicted", r"felon",
)

DISASTER = _rx(
    r"crash(?:es|ed|ing)?", r"derail\w*", r"sinks", r"sank", r"sunk", r"sinking", r"shipwreck\w*", r"capsiz\w*",
    r"collid\w*", r"collision", r"explosions?", r"explod\w*", r"blasts?(?! off)", r"fires?", r"wildfires?", r"blaze",
    r"inferno", r"earthquakes?", r"quake", r"tsunamis?", r"hurricanes?", r"typhoons?", r"cyclones?",
    r"tornado(?:e?s)?", r"flood\w*", r"eruptions?", r"erupt\w*", r"avalanches?", r"landslides?", r"mudslides?",
    r"stampedes?", r"crowd crush", r"collaps\w*", r"famines?", r"epidemics?", r"pandemics?", r"outbreaks?",
    r"meltdown", r"nuclear (?:accident|disaster)", r"disasters?", r"accidents?", r"heat wave", r"perish\w*",
    r"kill(?:s|ed|ing)", r"death toll", r"fatalities",
)

# --- helpers ---------------------------------------------------------------------------

PERSON_DESC = re.compile(
    r"\((?:born|b\.|died|d\.)\s+(?:c\.\s*)?\d{1,4}|\(\s*(?:c\.\s*)?\d{1,4}(?:\s*BC)?\s*[–—-]\s*(?:c\.\s*)?\d{1,4}"
)
# "1934 novel by Agatha Christie", "American television series" - but not "American film director".
CREATIVE_WORK = re.compile(
    r"^(?:[\w’'.-]+\s+){0,5}?(?:novel|novella|book|film|movie|play|musical|opera|album|song|single|poem|"
    r"painting|sculpture|series|sitcom|video game|comic|manga|anime|short story|documentary|episode|franchise|"
    r"board game)(?:\s+(?:by|series|written|directed|starring|about|from|based)\b|\s*$|\s*\()",
    re.IGNORECASE,
)
GENERIC_PLACE = re.compile(
    r"^(?:[\w’'.,-]+\s+){0,4}?(?:country|countries|sovereign state|city|town|village|capital|municipality|commune|"
    r"county|province|region|island|archipelago|continent|ocean|sea|river|lake|mountain range|planet|"
    r"natural satellite|state|empire|kingdom|republic|ethnic group|language|religion|religious denomination|"
    r"borough|district|metropolis|megacity)\b",
    re.IGNORECASE,
)
TOPIC_PREFIX = re.compile(r"^([^:]{3,70}):\s+\S")
PICTURED = re.compile(r"\s*\((?:pictured|illustrated|depicted|shown)\)", re.IGNORECASE)


def clean_text(text: str) -> str:
    return " ".join(PICTURED.sub("", text).split())


def topic_prefix(text: str) -> str | None:
    m = TOPIC_PREFIX.match(text)
    return m.group(1).strip() if m else None


def is_generic(desc: str) -> bool:
    return bool(desc) and bool(GENERIC_PLACE.match(desc))


def is_person_desc(desc: str) -> bool:
    return bool(PERSON_DESC.search(desc or ""))


def has_child(text: str) -> bool:
    if CHILD.search(text):
        return True
    for m in CHILD_AGE.finditer(text):
        if m.group(2).lower() != "year" or int(m.group(1)) < 18:
            return True
    return False


@dataclass(frozen=True)
class Verdict:
    action: str  # "keep" | "drop" | "gate" | "atrocity"
    category: str  # short label used in the review report
    reason: str  # human-readable explanation
    gate: str | None = None  # "famous" | "terrorism" when action == "gate"


def _keep(category: str = "ok", reason: str = "") -> Verdict:
    return Verdict("keep", category, reason)


def _drop(category: str, match: re.Match | str) -> Verdict:
    word = match.group(0) if isinstance(match, re.Match) else match
    return Verdict("drop", category, f'{category} ("{word}")')


def _gate(category: str, gate: str, match: re.Match) -> Verdict:
    return Verdict("gate", category, f'{category} ("{match.group(0)}")', gate)


def _neutralise_titles(text: str, pages: list[dict]) -> str:
    """Blank out titles of books/films/etc. so 'Murder on the Orient Express is published' is harmless."""
    for page in pages:
        if CREATIVE_WORK.match(page.get("desc") or "") and len(page["title"]) > 3:
            text = re.sub(re.escape(page["title"]), " ", text, flags=re.IGNORECASE)
    return text


def classify_event(text: str, pages: list[dict]) -> Verdict:
    text = clean_text(text)
    work_free = [p for p in pages if not CREATIVE_WORK.match(p.get("desc") or "")]
    body = _neutralise_titles(text, pages)
    prefix = topic_prefix(text)
    # Context (war / political) comes from the text and the main article only, not from every
    # linked place: "2009 Fort Hood shooting" must not count as war because Fort Hood is an army post.
    ctx_pages = pages[:1] + [p for p in pages if prefix and p["title"].casefold() == prefix.casefold()]
    ctx = " ".join([body] + [p.get("desc") or "" for p in ctx_pages])
    everything = " ".join([body] + [p["title"] for p in work_free] + [p.get("desc") or "" for p in work_free])

    war = WAR.search(ctx)
    political = POLITICAL.search(ctx)
    legal = LEGAL.search(" ".join([body] + [p["title"] for p in work_free]))

    if m := SEXUAL.search(everything):
        return _drop("sexual violence", m)
    if has_child(body):
        for rx in (MURDER, MASS, GORE, ABUSE, KIDNAP, HOSTAGE_TERROR):
            if m := rx.search(everything):
                return _drop("harm to children", m)
    for page in work_free:
        desc = page.get("desc") or ""
        # "serial killer", "mass murderer"... always; "terrorist", "murderer"... unless it's a war item.
        if KILLER_STRONG.search(desc) or (not war and is_person_desc(desc) and KILLER_WEAK.search(desc)):
            return Verdict("drop", "about a killer or abuser", f'about {page["title"]} ("{desc}")')
    if m := GORE.search(everything):
        return Verdict("atrocity", "war atrocity", f'war context + "{m.group(0)}"') if war else _drop("graphic violence", m)
    assassination = ASSASSINATION.search(ctx)
    if m := MASS.search(everything):
        if war:
            return Verdict("atrocity", "war atrocity", f'war context + "{m.group(0)}"')
        if assassination or (political and STATE_ACTOR.search(ctx)):
            return _keep("political violence", f'"{m.group(0)}" by state forces / in an assassination')
        return _drop("massacre / mass violence", m)
    if m := MURDER.search(everything):
        if war:
            return _keep("war", f'"{m.group(0)}" in a war context')
        victim = next((p for p in work_free if is_person_desc(p.get("desc") or "")
                       and POLITICAL_FIGURE.search(p.get("desc") or "")), None)
        if assassination or victim:
            who = f' of {victim["title"]}' if victim else ""
            return _keep("political violence", f"assassination{who}")
        if legal:
            return Verdict("gate", "crime / court case", f'court case ("{m.group(0)}", "{legal.group(0)}")', "famous")
        return _drop("murder", m)
    if m := SUICIDE.search(body):
        if war or political:
            return _keep("war" if war else "political violence", f'"{m.group(0)}" in a war/political context')
        return _drop("suicide", m)
    if war:
        return _keep("war", f'war context ("{war.group(0)}")')
    if m := TERROR.search(everything) or TERROR_CS.search(everything):
        return _gate("terrorism", "terrorism", m)
    if m := CRIME.search(everything):
        return _gate("crime / court case", "famous", m)
    if m := DISASTER.search(body):
        return _gate("disaster / accident", "famous", m)
    return _keep()


def classify_person(text: str, pages: list[dict]) -> Verdict:
    """Births and deaths: text looks like 'Ted Bundy, American serial killer (d. 1989)'."""
    text = clean_text(text)
    descriptor = text.split(",", 1)[1] if "," in text else text
    blob = " ".join([descriptor] + [(pages[0].get("desc") or "") if pages else ""])
    if m := SEXUAL.search(blob):
        return _drop("sexual violence", m)
    if m := KILLER_STRONG.search(blob) or KILLER_WEAK.search(blob):
        return _drop("killer or abuser", m)
    if m := MURDER.search(blob) or GORE.search(blob):
        return _drop("murder (victim or perpetrator)", m)
    if m := CRIME_PERSON.search(blob):
        return _gate("criminal", "famous", m)
    return _keep()


def classify(kind: str, text: str, pages: list[dict]) -> Verdict:
    if kind in ("births", "deaths"):
        return classify_person(text, pages)
    return classify_event(text, pages)


def decide(verdict: Verdict, fame: int, cfg: dict) -> tuple[bool, str]:
    """Apply the configured policy. Returns (keep?, explanation)."""
    f = cfg["filter"]
    if verdict.action == "keep":
        return True, verdict.reason or "ok"
    if verdict.action == "drop":
        return False, verdict.reason
    if verdict.action == "atrocity":
        keep = f["war_atrocities"] == "keep"
        return keep, f'{verdict.reason}; war_atrocities = "{f["war_atrocities"]}"'
    threshold = f["terrorism_threshold"] if verdict.gate == "terrorism" else f["famous_threshold"]
    keep = fame >= threshold
    return keep, f"{verdict.reason}; fame {fame} {'>=' if keep else '<'} {threshold}"
