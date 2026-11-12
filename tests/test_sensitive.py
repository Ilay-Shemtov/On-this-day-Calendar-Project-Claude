"""Filter behaviour on real-world examples.

Texts follow the style of Wikipedia's date pages; descriptions follow Wikipedia short descriptions.
Lines marked [Dec 1] are verbatim from a real snapshot of en.wikipedia.org/wiki/December_1.
Run:  python -m unittest discover -s tests
"""

import unittest

from otd.config import DEFAULTS
from otd.sensitive import classify, decide


def P(title, desc=""):
    return {"title": title, "desc": desc, "qid": "", "type": "standard"}


KEEP, DROP, GATE, ATROCITY = "keep", "drop", "gate", "atrocity"

EVENTS = [
    # --- the user's own examples
    ("Columbine", DROP,
     "Columbine High School massacre: Eric Harris and Dylan Klebold kill 13 people and injure 24 others before "
     "committing suicide at Columbine High School in Columbine, Colorado.",
     [P("Columbine High School massacre", "1999 school shooting in Colorado, US"),
      P("Eric Harris and Dylan Klebold", "American mass murderers"), P("Columbine High School", "public high school in Colorado")]),
    ("OJ verdict", GATE,
     "O. J. Simpson is acquitted of the murders of Nicole Brown Simpson and Ronald Goldman.",
     [P("O. J. Simpson", "American football player and actor (1947–2024)"),
      P("Murder trial of O. J. Simpson", "1995 US criminal trial"),
      P("Nicole Brown Simpson", "American murder victim (1959–1994)"), P("Murder of Ronald Goldman", "")]),
    ("OJ murders themselves", DROP,
     "Nicole Brown Simpson and Ronald Goldman are murdered outside Simpson's home in Los Angeles.",
     [P("Nicole Brown Simpson", "American murder victim (1959–1994)"), P("Los Angeles", "city in California, United States")]),
    ("Ted Bundy executed", DROP,
     "Serial killer Ted Bundy is executed in Florida's electric chair.",
     [P("Ted Bundy", "American serial killer (1946–1989)"), P("Electric chair", "execution device")]),
    ("Dahmer arrested", DROP,
     "Jeffrey Dahmer is arrested in Milwaukee after police find human remains in his apartment.",
     [P("Jeffrey Dahmer", "American serial killer and sex offender (1960–1994)")]),
    ("Zodiac", DROP,
     "The Zodiac Killer sends his first letter to the San Francisco Chronicle.",
     [P("Zodiac Killer", "unidentified American serial killer"), P("San Francisco Chronicle", "newspaper")]),
    # --- wars and conflicts
    ("D-Day", KEEP,
     "World War II: Operation Overlord begins with the Normandy landings, as Allied troops land on the beaches of Normandy.",
     [P("World War II", "1939–1945 global conflict"), P("Normandy landings", "1944 Allied invasion of France")]),
    ("Hiroshima", KEEP,
     "World War II: The United States drops an atomic bomb on Hiroshima, Japan, killing an estimated 70,000–80,000 people.",
     [P("World War II", "1939–1945 global conflict"), P("Atomic bombings of Hiroshima and Nagasaki", "1945 nuclear attacks on Japan")]),
    ("Hitler's suicide", KEEP,
     "World War II: Adolf Hitler and Eva Braun commit suicide in the Führerbunker as the Red Army closes in on Berlin.",
     [P("World War II", "1939–1945 global conflict"), P("Adolf Hitler", "Dictator of Germany (1889–1945)")]),
    ("My Lai", ATROCITY,
     "Vietnam War: American soldiers kill between 347 and 504 unarmed civilians in the My Lai massacre.",
     [P("Vietnam War", "1955–1975 conflict in Southeast Asia"), P("My Lai massacre", "1968 mass murder by US troops in Vietnam")]),
    ("Holocaust deportations", ATROCITY,
     "The Holocaust: Nazi Germany begins deporting Jews from the Warsaw Ghetto to the Treblinka extermination camp.",
     [P("The Holocaust", "genocide of European Jews during World War II"), P("Treblinka extermination camp", "Nazi German extermination camp")]),
    ("Boston Massacre", ATROCITY,
     "Boston Massacre: Five Americans, including Crispus Attucks, are fatally shot by British troops in an event that "
     "would contribute to the outbreak of the American Revolutionary War five years later.",
     [P("Boston Massacre", "1770 killing of colonists by British soldiers"), P("Crispus Attucks", "American stevedore (1723–1770)")]),
    ("Kent State", ATROCITY,
     "Vietnam War: Kent State shootings: The Ohio National Guard opens fire on anti-war protesters at Kent State "
     "University, killing four students.",
     [P("Vietnam War", "1955–1975 conflict in Southeast Asia"), P("Kent State shootings", "1970 shooting of students in Ohio, US")]),
    ("Tiananmen", ATROCITY,
     "Tiananmen Square protests: The Chinese army opens fire on demonstrators in Beijing, killing hundreds.",
     [P("1989 Tiananmen Square protests and massacre", "1989 student-led protests in China")]),
    ("Philippine coup attempt [Dec 1]", KEEP,
     "Philippine coup attempt: The right-wing military rebel Reform the Armed Forces Movement attempts to oust "
     "Philippine President Corazon Aquino in a failed bloody coup d'état.",
     [P("1989 Philippine coup attempt"), P("Reform the Armed Forces Movement"), P("Corazon Aquino", "President of the Philippines (1933–2009)")]),
    ("Khmer Rouge [Dec 1]", KEEP,
     "Cambodian Civil War: Khmer Rouge rebels intensify assaults on Cambodian government positions, forcing their "
     "retreat from Kompong Thmar and nearby Ba Ray.",
     [P("Cambodian Civil War"), P("Khmer Rouge", "Cambodian communist party"), P("Cambodia", "country in Southeast Asia")]),
    ("Bin Laden killed", KEEP,
     "War on terror: Osama bin Laden is killed by United States Navy SEALs in Abbottabad, Pakistan.",
     [P("War on terror", "military campaign"), P("Osama bin Laden", "Saudi Arabian terrorist, founder of al-Qaeda (1957–2011)")]),
    # --- assassinations and political violence
    ("JFK", KEEP,
     "U.S. President John F. Kennedy is assassinated in Dallas, Texas; Governor John Connally is seriously wounded.",
     [P("John F. Kennedy", "President of the United States from 1961 to 1963"),
      P("Assassination of John F. Kennedy", "1963 murder in Dallas, Texas, US"),
      P("Lee Harvey Oswald", "American assassin of John F. Kennedy (1939–1963)")]),
    ("Franz Ferdinand", KEEP,
     "Archduke Franz Ferdinand of Austria and his wife Sophie are assassinated in Sarajevo by Gavrilo Princip, "
     "the casus belli of World War I.",
     [P("Archduke Franz Ferdinand of Austria", "Austro-Hungarian archduke (1863–1914)"), P("Gavrilo Princip", "Bosnian Serb assassin (1894–1918)")]),
    ("Lincoln shot", KEEP,
     "American Civil War: President Abraham Lincoln is shot by John Wilkes Booth at Ford's Theatre in Washington, D.C.",
     [P("Abraham Lincoln", "President of the United States from 1861 to 1865"), P("John Wilkes Booth", "American actor (1838–1865)")]),
    ("Gandhi", KEEP,
     "Mahatma Gandhi is assassinated by Nathuram Godse in New Delhi.",
     [P("Mahatma Gandhi", "Indian lawyer and independence activist (1869–1948)"), P("Nathuram Godse", "Indian assassin (1910–1949)")]),
    ("Kirov [Dec 1]", KEEP,
     "In the Soviet Union, Politburo member Sergey Kirov is shot dead by Leonid Nikolaev at the Communist Party "
     "headquarters in Leningrad.",
     [P("Soviet Union", "country in Eurasia (1922–1991)"), P("Politburo"), P("Sergey Kirov", "Soviet politician (1886–1934)"),
      P("Leonid Nikolaev", "Soviet assassin of Sergei Kirov (1904–1934)")]),
    ("Sharpeville", KEEP,
     "Apartheid: Police in Sharpeville, South Africa, open fire on a crowd of black demonstrators, killing 69 people.",
     [P("Apartheid", "system of racial segregation in South Africa"), P("Sharpeville massacre", "1960 massacre in South Africa")]),
    # --- other gruesome crime (dropped)
    ("Lennon", DROP,
     "John Lennon is shot and killed by Mark David Chapman outside The Dakota in New York City.",
     [P("Murder of John Lennon", "1980 killing in New York City"), P("John Lennon", "English musician (1940–1980)"),
      P("Mark David Chapman", "American murderer of John Lennon (born 1955)")]),
    ("St. Valentine's Day Massacre", DROP,
     "Saint Valentine's Day Massacre: Seven gangsters, rivals of Al Capone's gang, are murdered in Chicago.",
     [P("Saint Valentine's Day Massacre", "1929 gangland murders in Chicago"), P("Al Capone", "American gangster (1899–1947)")]),
    ("Christchurch", DROP,
     "Christchurch mosque shootings: A gunman kills 51 people at two mosques in Christchurch, New Zealand.",
     [P("Christchurch mosque shootings", "2019 terrorist attacks in New Zealand")]),
    ("Fort Hood", DROP,
     "2009 Fort Hood shooting: U.S. Army Major Nidal Hasan kills 13 people and wounds 32 others at Fort Hood, Texas.",
     [P("2009 Fort Hood shooting", "2009 mass shooting in Texas, US"),
      P("Nidal Hasan", "American mass murderer and former U.S. Army officer (born 1970)"), P("Fort Hood", "U.S. Army post in Texas")]),
    ("Norway attacks", DROP,
     "2011 Norway attacks: Anders Behring Breivik kills 8 people with a car bomb in Oslo, then 69 at a youth camp on Utøya.",
     [P("2011 Norway attacks", "domestic terrorist attacks in Norway"),
      P("Anders Behring Breivik", "Norwegian far-right terrorist and mass murderer (born 1979)")]),
    ("Sandy Hook", DROP,
     "Sandy Hook Elementary School shooting: Twenty children and six adults are shot dead in Newtown, Connecticut.",
     [P("Sandy Hook Elementary School shooting", "2012 mass shooting in Connecticut, US")]),
    ("Oklahoma City", DROP,
     "Oklahoma City bombing: A truck bomb explodes outside the Alfred P. Murrah Federal Building, killing 168 people, "
     "including 19 children.",
     [P("Oklahoma City bombing", "1995 domestic terrorist truck bombing in Oklahoma, US")]),
    ("Beslan", DROP,
     "Beslan school siege: Chechen separatists take more than 1,100 people hostage at a school in Beslan, Russia; "
     "334 hostages, including 186 children, are killed.",
     [P("Beslan school siege", "2004 terrorist attack in North Ossetia, Russia")]),
    ("Munich massacre", DROP,
     "Munich massacre: Members of the Palestinian militant group Black September take eleven Israeli Olympic athletes "
     "hostage; all are killed.",
     [P("Munich massacre", "1972 terrorist attack at the Munich Olympics")]),
    ("Jonestown", DROP,
     "Jim Jones leads his Peoples Temple cult in a mass murder–suicide at Jonestown, Guyana, killing 918 people, "
     "including 276 children.",
     [P("Jim Jones", "American cult leader (1931–1978)"), P("Jonestown", "former settlement in Guyana")]),
    ("Lindbergh kidnapping", DROP,
     "The 20-month-old son of aviator Charles Lindbergh is kidnapped from his home in New Jersey.",
     [P("Lindbergh kidnapping", "1932 kidnapping and murder in New Jersey, US"), P("Charles Lindbergh", "American aviator (1902–1974)")]),
    ("Weinstein", DROP,
     "Harvey Weinstein is convicted of rape and sexual assault in New York.",
     [P("Harvey Weinstein", "American film producer (born 1952)")]),
    ("Murder (no context)", DROP,
     "A man is stabbed to death in a robbery in Paris.",
     [P("Paris", "capital and largest city of France")]),
    # --- famous-only (gated)
    ("9/11", GATE,
     "September 11 attacks: Nineteen al-Qaeda hijackers crash four airliners into the World Trade Center, the Pentagon "
     "and a field in Pennsylvania, killing nearly 3,000 people.",
     [P("September 11 attacks", "2001 Islamist terrorist attacks in the United States"),
      P("Al-Qaeda", "Sunni pan-Islamist militant organization"), P("World Trade Center (1973–2001)", "former office complex")]),
    ("Watergate", GATE,
     "Watergate scandal: Five White House operatives are arrested for burglarizing the offices of the Democratic "
     "National Committee.",
     [P("Watergate scandal", "1972–1974 American political scandal")]),
    ("Al Capone sentenced", GATE,
     "Al Capone is sentenced to eleven years in prison for tax evasion.",
     [P("Al Capone", "American gangster (1899–1947)")]),
    ("Iran hostage crisis", GATE,
     "Iran hostage crisis: Iranian students storm the US embassy in Tehran and take 52 Americans hostage.",
     [P("Iran hostage crisis", "1979–1981 diplomatic standoff")]),
    ("Titanic", GATE,
     "The RMS Titanic sinks in the North Atlantic about two hours after striking an iceberg; 1,500 people die.",
     [P("RMS Titanic", "British ocean liner")]),
    ("Chernobyl", GATE,
     "A nuclear reactor explodes at the Chernobyl Nuclear Power Plant in the Soviet Union, causing the worst nuclear "
     "disaster in history.",
     [P("Chernobyl disaster", "1986 nuclear accident in the Soviet Union")]),
    ("Rosa Parks [Dec 1]", GATE,
     "American Civil Rights Movement: In Montgomery, Alabama, seamstress Rosa Parks refuses to give up her bus seat to "
     "a white man and is arrested for violating the city's racial segregation laws.",
     [P("Civil rights movement"), P("Montgomery, Alabama", "capital city of Alabama, United States"),
      P("Rosa Parks", "American civil rights activist (1913–2005)")]),
    ("McCartney arrested [Dec 1]", GATE,
     "Paul McCartney and Pete Best are arrested (and later deported) from Hamburg, Germany, after accusations of "
     "attempted arson.",
     [P("Paul McCartney", "English musician (born 1942)"), P("Pete Best", "English drummer (born 1941)"), P("Hamburg", "city in Germany")]),
    ("School fire [Dec 1]", GATE,
     "The Our Lady of the Angels School fire in Chicago kills 92 children and three nuns.",
     [P("Our Lady of the Angels School fire", "1958 school fire in Chicago")]),
    ("Plane crash [Dec 1]", GATE,
     "TWA Flight 514, a Boeing 727, crashes northwest of Dulles International Airport, killing all 92 people on board.",
     [P("TWA Flight 514", "1974 aviation accident"), P("Boeing 727", "airliner")]),
    ("Caste massacre [Dec 1]", GATE,
     "In the Indian state of Bihar, Ranvir Sena attacked the CPI(ML) Party Unity stronghold Lakshmanpur-Bathe, "
     "killing 63 lower caste people.",
     [P("Bihar", "state of India"), P("Ranvir Sena", "caste-based militia")]),
    # --- ordinary history (kept)
    ("Apollo 11", KEEP,
     "Apollo 11 astronauts Neil Armstrong (pictured) and Buzz Aldrin become the first humans to walk on the Moon.",
     [P("Apollo 11", "first crewed Moon landing (1969)"), P("Neil Armstrong", "American astronaut (1930–2012)")]),
    ("Novel with 'Murder' in the title", KEEP,
     "Agatha Christie's novel Murder on the Orient Express is published in the United Kingdom.",
     [P("Agatha Christie", "English writer (1890–1976)"), P("Murder on the Orient Express", "1934 novel by Agatha Christie")]),
    ("Poem with 'Rape' in the title", KEEP,
     "Alexander Pope publishes the first version of The Rape of the Lock.",
     [P("Alexander Pope", "English poet (1688–1744)"), P("The Rape of the Lock", "poem by Alexander Pope")]),
    ("Apollo launch", KEEP,
     "Apollo 8 blasts off from Cape Kennedy on the first crewed mission to orbit the Moon.",
     [P("Apollo 8", "1968 crewed lunar orbital mission")]),
    ("Ford assembly line [Dec 1]", KEEP,
     "Ford Motor Company introduces the first moving assembly line.",
     [P("Ford Motor Company", "American automobile manufacturer"), P("Assembly line", "manufacturing process")]),
    ("Jorgensen [Dec 1]", KEEP,
     "The New York Daily News reports the news of Christine Jorgensen, the first notable case of sex reassignment surgery.",
     [P("New York Daily News", "American newspaper"), P("Christine Jorgensen", "American transgender woman (1926–1989)")]),
    ("Slavery abolished [Dec 1]", KEEP,
     "Slavery is abolished in the Cape Colony in accordance with the Slavery Abolition Act 1833.",
     [P("Cape Colony", "British colony in southern Africa (1806–1910)"), P("Slavery Abolition Act 1833", "UK act of Parliament")]),
]

PEOPLE = [
    ("Ted Bundy", DROP, "Ted Bundy, American serial killer (d. 1989)", [P("Ted Bundy", "American serial killer (1946–1989)")]),
    ("Charles Manson", DROP, "Charles Manson, American criminal and cult leader (d. 2017)", [P("Charles Manson", "American criminal and cult leader")]),
    ("Dahmer", DROP, "Jeffrey Dahmer, American serial killer and sex offender (d. 1994)", [P("Jeffrey Dahmer")]),
    ("JonBenét", DROP, "JonBenét Ramsey, American child beauty queen and murder victim (b. 1990)", [P("JonBenét Ramsey")]),
    ("Bin Laden", DROP, "Osama bin Laden, Saudi Arabian terrorist, founder of al-Qaeda (b. 1957)", [P("Osama bin Laden")]),
    ("Al Capone", GATE, "Al Capone, American gangster (d. 1947)", [P("Al Capone", "American gangster (1899–1947)")]),
    ("Bonnie Parker", GATE, "Bonnie Parker, American criminal (d. 1934)", [P("Bonnie Parker")]),
    ("Pablo Escobar", GATE, "Pablo Escobar, Colombian drug lord (d. 1993)", [P("Pablo Escobar")]),
    ("Gregor Mendel", KEEP, "Gregor Mendel, Austrian-Czech monk and scientist (d. 1884)", [P("Gregor Mendel")]),
    ("Hitler", KEEP, "Adolf Hitler, Austrian-born German politician, dictator of Nazi Germany (d. 1945)", [P("Adolf Hitler")]),
    ("Elie Wiesel", KEEP, "Elie Wiesel, Romanian-born American novelist, Holocaust survivor, Nobel Prize laureate (d. 2016)", [P("Elie Wiesel")]),
    ("Agatha Christie", KEEP, "Agatha Christie, English crime novelist (d. 1976)", [P("Agatha Christie", "English writer (1890–1976)")]),
    ("Rex Stout [Dec 1]", KEEP, "Rex Stout, American detective novelist (d. 1975)", [P("Rex Stout")]),
    ("Oswald", KEEP, "Lee Harvey Oswald, American assassin of John F. Kennedy (b. 1939)", [P("Lee Harvey Oswald")]),
    ("Edmund Campion [Dec 1]", KEEP, "Edmund Campion, English Roman Catholic priest, martyr, and saint (b. 1540)", [P("Edmund Campion")]),
]


class TestClassification(unittest.TestCase):
    def _check(self, kind, cases):
        for name, expected, text, pages in cases:
            with self.subTest(name):
                v = classify(kind, text, pages)
                self.assertEqual(v.action, expected, f"{name}: got {v.action} ({v.reason})")

    def test_events(self):
        self._check("events", EVENTS)

    def test_people(self):
        self._check("births", PEOPLE)

    def test_terrorism_uses_stricter_threshold(self):
        name, _, text, pages = next(c for c in EVENTS if c[0] == "9/11")
        self.assertEqual(classify("events", text, pages).gate, "terrorism")
        name, _, text, pages = next(c for c in EVENTS if c[0] == "OJ verdict")
        self.assertEqual(classify("events", text, pages).gate, "famous")


class TestPolicy(unittest.TestCase):
    cfg = DEFAULTS

    def verdict(self, name):
        _, _, text, pages = next(c for c in EVENTS if c[0] == name)
        return classify("events", text, pages)

    def test_famous_court_case_kept_obscure_dropped(self):
        v = self.verdict("OJ verdict")
        self.assertTrue(decide(v, 70, self.cfg)[0])
        self.assertFalse(decide(v, 5, self.cfg)[0])

    def test_terrorism_needs_more_fame(self):
        v = self.verdict("9/11")
        self.assertTrue(decide(v, 150, self.cfg)[0])
        self.assertFalse(decide(v, 50, self.cfg)[0])

    def test_war_atrocities_switch(self):
        v = self.verdict("My Lai")
        self.assertTrue(decide(v, 0, self.cfg)[0])
        strict = {**self.cfg, "filter": {**self.cfg["filter"], "war_atrocities": "drop"}}
        self.assertFalse(decide(v, 0, strict)[0])

    def test_drops_ignore_fame(self):
        self.assertFalse(decide(self.verdict("Columbine"), 10_000, self.cfg)[0])


if __name__ == "__main__":
    unittest.main()
