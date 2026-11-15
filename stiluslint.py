#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""magyar-stiluslint: gépies, hivataloskodó fordulatok megjelölése magyar szövegben.

A program csak jelöl és javaslatot ad. Nem írja át a szöveget, nem becsüli meg,
hogy azt ember vagy gép írta-e, és nem MI-detektorok ellen készült.

Használat:
    python3 stiluslint.py szoveg.txt
    python3 stiluslint.py kezirat.docx --json
    cat szoveg.md | python3 stiluslint.py -

Csak a Python szabványos könyvtárát használja (3.8+).
"""

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree

__version__ = "0.2.0"

SZINTEK = {"info": 0, "figyelem": 1}
FLAGS = re.IGNORECASE | re.UNICODE

# ---------------------------------------------------------------------------
# Szabályok
# ---------------------------------------------------------------------------
# Kifejezés-szabály: (azonosító, szint, leírás, javaslat, [minták])
KIFEJEZES_SZABALYOK = [
    (
        "kerul-asra",
        "figyelem",
        "Körülíró szerkezet („-ásra/-ésre kerül”)",
        "Nevezd meg, ki mit csinál: „megállapításra került” → „megállapítottuk”.",
        [
            r"\b\w+(?:ásra|ésre)\s+ker[üu]l\w*",
            r"\bker[üu]l\w*\s+\w+(?:ásra|ésre)\b",
        ],
    ),
    (
        "funkcioige",
        "figyelem",
        "Főnevesítés funkcióigével",
        "Használd magát az igét: „elvégzi az ellenőrzést” → „ellenőrzi”.",
        [
            r"\b(?:el)?vég(?:ez|z)\w*\s+(?:\w+\s+){0,3}?\w+(?:ását|ését|ást|ést)\b",
            r"\b\w+(?:ását|ését|ást|ést)\s+(?:el)?vég(?:ez|z)\w*",
            r"\b\w+(?:ást|ést)\s+(?:eszközöl|foganatosít|hajt\w*\s+végre)\w*",
            r"\blehetőséget\s+(?:biztosít|nyújt|kínál)\w*",
            r"\b\w+(?:ásra|ésre)\s+irányul\w*",
            r"\b\w+(?:ást|ést)\s+(?:nyer|talál)\w*",
        ],
    ),
    (
        "toltelek",
        "figyelem",
        "Töltelékfordulat",
        "Töröld a felvezetést, és kezdd a mondatot a tartalommal.",
        [
            r"\bfontos\s+(?:megjegyezni|kiemelni|hangsúlyozni|megemlíteni|leszögezni),?\s+hogy\b",
            r"\bérdemes\s+(?:megjegyezni|kiemelni|megemlíteni|hangsúlyozni),?\s+hogy\b",
            r"\b(?:ki\s+kell\s+emelni|hangsúlyozni\s+kell|meg\s+kell\s+jegyezni),?\s+hogy\b",
            r"\bebben\s+az\s+összefüggésben\b",
            r"\bmint\s+(?:azt\s+)?(?:korábban|fentebb)\s+említettük\b",
            r"\bösszességében\s+(?:elmondható|megállapítható|kijelenthető)\b",
            r"\b(?:elmondható|megállapítható|kijelenthető|leszögezhető),?\s+hogy\b",
            r"\bnem\s+szabad\s+megfeledkezni\s+arról\b",
            r"\bfigyelembe\s+(?:kell\s+)?venni\s+azt\s+a\s+tényt,?\s+hogy\b",
        ],
    ),
    (
        "felnagyitas",
        "figyelem",
        "A jelentőség felnagyítása",
        "Írd le, miért fontos, vagy hagyd el a jelzőt.",
        [
            r"\bkulcsfontosságú\w*",
            r"\blétfontosságú\w*",
            r"\b(?:döntő|kiemelkedő|alapvető|meghatározó)\s+(?:jelentőség|fontosság|szerep)\w*",
            r"\brendkívül\s+(?:fontos|jelentős|gyors|nagy)\w*",
            r"\bjelentős\s+(?:mértékben|szerepet|előrelépés\w*|hatás\w*)",
        ],
    ),
    (
        "reklamiz",
        "figyelem",
        "Reklámízű jelző",
        "Semleges szövegben cseréld tényre vagy töröld.",
        [
            r"\begyedülálló\w*",
            r"\búttörő\w*",
            r"\bforradalmi\w*",
            r"\bpáratlan\w*",
            r"\bvilágszínvonalú\w*",
            r"\bélvonalbeli\w*",
            r"\binnovatív\w*",
        ],
    ),
    (
        "hivataloskodas",
        "info",
        "Hivataloskodó fordulat",
        "Ha nem jogi vagy hivatali szöveg, mondd egyszerűbben.",
        [
            r"\baz\s+adott\s+\w+",
            r"\ba\s+fent(?:ebb)?\s+említett\b",
            r"\ba\s+szóban\s+forgó\b",
            r"\bamennyiben\b",
            r"\bezen\s+felül\b",
            r"\b\w+\s+(?:tekintetében|vonatkozásában)\b",
            r"\bennek\s+megfelelően\b",
            r"\bmindenekelőtt\b",
            r"\bigénybe\s+(?:kíván\w*\s+)?ve\w+",
            r"\bszíveskedj\w*",
        ],
    ),
    (
        "ovatoskodas",
        "info",
        "Halmozott óvatoskodás",
        "Egy tompítás elég; ha tudod, állítsd határozottan.",
        [
            r"\belképzelhető,?\s+hogy\s+(?:esetleg|talán)\b",
            r"\bbizonyos\s+(?:mértékben|körülmények\s+között|fokig)\b",
            r"\b(?:vélhetően|feltételezhetően)\b",
            r"\besetleg\s+talán\b",
        ],
    ),
    (
        "sablonos-lezaras",
        "figyelem",
        "Sablonos lezárás",
        "Töröld, vagy cseréld konkrét állításra.",
        [
            r"\ba\s+jövő\s+(?:fényesnek|ígéretesnek)\s+ígérkezik\b",
            r"\búj\s+(?:távlatokat|lehetőségeket|utakat)\s+nyit\w*",
            r"\btovábbra\s+is\s+(?:fejlődik|fejlődni\s+fog)\b",
            r"\ba\s+kihívások\s+ellenére\b",
        ],
    ),
    (
        "homalyos-hivatkozas",
        "figyelem",
        "Homályos hivatkozás",
        "Nevezd meg a forrást, vagy hagyd el az állítást.",
        [
            r"\b(?:szakértők|sokak|egyesek|kutatók)\s+szerint\b",
            r"\b(?:kutatások|tanulmányok|vizsgálatok)\s+(?:bizonyítják|kimutatták|igazolják|szerint)\b",
            r"\baz\s+iparág\s+vezető\s+szereplői\b",
        ],
    ),
    (
        "tudasvagas",
        "figyelem",
        "Felesleges kitétel a saját tudásszintről",
        "Hagyd el; az állítás enélkül is megáll.",
        [
            r"\b(?:legfrissebb|jelenlegi)\s+(?:ismereteim|tudásom)\s+szerint\b",
            r"\ba\s+rendelkezésre\s+álló\s+(?:adatok|információk)\s+alapján\b",
        ],
    ),
    (
        "hizelges",
        "figyelem",
        "Hízelgő hangnem",
        "Töröld, és válaszolj a tárgyra.",
        [
            r"\b(?:remek|kiváló|nagyszerű)\s+(?:kérdés|észrevétel|felvetés)\b",
            r"\bteljesen\s+igazad\s+van\b",
        ],
    ),
    (
        "nemcsak-hanem",
        "info",
        "„Nemcsak… hanem… is” nyomatékként",
        "Gyakran elég az „és”: „hatékonyabb, és javítja az együttműködést”.",
        [r"\bnem\s?csak\b[^.!?\n]{0,160}?\bhanem\b"],
    ),
    (
        "birtokos-halmozas",
        "figyelem",
        "Egymásra torlódó birtokos szerkezetek",
        "Bontsd igei mondatra.",
        [r"\b(?:\w+(?:ának|ének|ainak|einek|jának|jének)\s+){2,}\w+"],
    ),
]

# Sűrűség-szabály: bekezdésen belül ennyi találat fölött jelez.
SURUSEG_SZABALYOK = [
    (
        "nem-hanem-suruseg",
        "info",
        "Sok „nem X, hanem Y” ellentét egy bekezdésben",
        "Hagyj meg egyet-kettőt; a többit írd egyenes állításnak.",
        r"\bnem\b[^.!?\n]{0,200}?,\s*hanem\b",
        2,
    ),
    (
        "hato-heto-suruseg",
        "info",
        "Sok személytelen „-ható/-hető” alak egy bekezdésben",
        "Nevezd meg a cselekvőt: „megállapítható” → „megállapítom / azt látjuk”.",
        r"\b\w{3,}(?:ható|hető)\b(?!\w)",
        3,
    ),
    (
        "harmas-felsorolas",
        "info",
        "Több hármas felsorolás egy bekezdésben",
        "Nézd meg, mindhárom tag kell-e; a gépies szöveg mindent hármasával sorol.",
        r"\b\w{4,},\s+\w{4,}\s+(?:és|valamint|illetve)\s+\w{4,}\b",
        2,
    ),
    (
        "felkover-suruseg",
        "info",
        "Sok félkövér kiemelés egy bekezdésben",
        "Csak azt emeld ki, ami tényleg figyelmet kíván.",
        r"\*\*[^*\n]+\*\*",
        4,
    ),
]

AMELY_RE = re.compile(r"\b(?:amely|amelyek|amely\w{1,6}|amelyek\w{1,6})\b", FLAGS)
SZO_RE = re.compile(r"\w+(?:-\w+)*", re.UNICODE)
MONDAT_RE = re.compile(r"[^.!?…\n]+(?:[.!?…]+|$)", re.UNICODE)
BEKEZDES_RE = re.compile(r"(?:[^\n]|\n(?!\s*\n))+", re.UNICODE)
EGYENES_IDEZOJEL_RE = re.compile(r'"[^"\n]{1,300}"|“[^”\n]{1,300}”')
KODBLOKK_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)

HOSSZU_MONDAT_SZO = 40
AMELY_LANC_DB = 3

SZABALY_LEIRASOK = {}
for _az, _szint, _leiras, _jav, _m in KIFEJEZES_SZABALYOK:
    SZABALY_LEIRASOK[_az] = (_szint, _leiras, _jav)
for _az, _szint, _leiras, _jav, _m, _k in SURUSEG_SZABALYOK:
    SZABALY_LEIRASOK[_az] = (_szint, _leiras, _jav)
SZABALY_LEIRASOK["amely-lanc"] = (
    "figyelem",
    "Vonatkozó mellékmondatok lánca („amely… amely… amely”)",
    "Használj jelzős szerkezetet vagy külön mondatot.",
)
SZABALY_LEIRASOK["hosszu-mondat"] = (
    "info",
    "Nagyon hosszú mondat (%d szó fölött)" % HOSSZU_MONDAT_SZO,
    "Bontsd két-három mondatra.",
)
SZABALY_LEIRASOK["idezojel"] = (
    "info",
    "Nem magyar idézőjel",
    "Magyar szövegben „így” idézünk, a belső idézet »ilyen«.",
)

# Javítási útmutató: szabályonként (cím, miért gond, lépések, egy találatra szóló utasítás).
# A „{r}” helyére a megjelölt szövegrészlet kerül.
UTMUTATO = {
    "kerul-asra": (
        "Oldd fel a körülíró („-ásra/-ésre kerül”) szerkezeteket",
        "A szerkezet elrejti, ki cselekszik, és hivatali hangot ad a mondatnak.",
        [
            "Keresd meg, ki végzi a cselekvést (a szerző, a kutatók, a rendszer).",
            "Tedd őt alannyá, a főnevet pedig alakítsd vissza igévé.",
            "Ha a cselekvő tényleg ismeretlen vagy lényegtelen, használj többes szám harmadik személyt („bevezették”).",
        ],
        "Nevezd meg a cselekvőt, és írd át igével: „{r}”.",
    ),
    "funkcioige": (
        "Cseréld igére a funkcióigés főnevesítéseket",
        "A „főnév + végez/biztosít/irányul” kétszer olyan hosszú, mint az ige, és semmit nem tesz hozzá.",
        [
            "Keresd meg a szerkezetben a főnévbe rejtett igét („ellenőrzés” → „ellenőriz”).",
            "Írd át a mondatot ezzel az igével, a segédigét hagyd el.",
            "Olvasd újra: ha a mondat rövidebb lett és ugyanazt mondja, a csere jó.",
        ],
        "Használd a főnévbe rejtett igét: „{r}”.",
    ),
    "toltelek": (
        "Töröld a töltelékfelvezetéseket",
        "A felvezetés bejelenti, hogy fontos dolog következik, ahelyett hogy kimondaná.",
        [
            "Töröld a fordulatot a „hogy” kötőszóval együtt.",
            "Kezdd a mondatot azzal, ami a felvezetés után állt.",
            "Ha a mondat így súlytalannak hat, a tartalmát erősítsd, ne a felvezetést tedd vissza.",
        ],
        "Töröld a felvezetést, és kezdd a mondatot a tartalommal: „{r}”.",
    ),
    "felnagyitas": (
        "Vedd vissza a felnagyító jelzőket",
        "Ha minden kulcsfontosságú, az olvasó nem tudja, mi az, ami tényleg az.",
        [
            "Kérdezd meg a mondattól: miért fontos ez, és kinek?",
            "Ha van válasz, azt írd le a jelző helyett. Ha nincs, töröld a jelzőt.",
        ],
        "Írd le a jelző helyett, miért fontos, vagy töröld: „{r}”.",
    ),
    "reklamiz": (
        "Cseréld tényre a reklámízű jelzőket",
        "Semleges szövegben a reklámnyelv hiteltelenné teszi az állítást.",
        [
            "Írd le, miben különbözik a dolog a többitől (adat, példa, összehasonlítás).",
            "Ha ilyet nem tudsz mondani, hagyd el a jelzőt.",
        ],
        "Cseréld konkrét tulajdonságra vagy töröld: „{r}”.",
    ),
    "sablonos-lezaras": (
        "Írd át vagy töröld a sablonos lezárásokat",
        "Az általános derűlátás bármely szöveg végére odaillene, ezért itt sem mond semmit.",
        [
            "Töröld a mondatot, és nézd meg, hiányzik-e.",
            "Ha kell lezárás, mondj konkrétumot: mi következik, mi maradt nyitva.",
        ],
        "Töröld, vagy cseréld konkrét állításra: „{r}”.",
    ),
    "homalyos-hivatkozas": (
        "Nevezd meg a forrásokat",
        "A meg nem nevezett tekintély nem ellenőrizhető, ezért nem is érv.",
        [
            "Keresd meg, melyik kutatásra, szerzőre vagy adatra gondoltál.",
            "Írd be név és évszám szerint, vagy hivatkozd meg.",
            "Ha nincs ilyen forrás, az állítást töröld, vagy jelöld saját véleményként.",
        ],
        "Írd oda a pontos forrást, vagy hagyd el az állítást: „{r}”.",
    ),
    "tudasvagas": (
        "Töröld a saját tudásszintre tett kitételeket",
        "A kitétel nem ad információt, csak elbizonytalanítja az állítást.",
        ["Töröld a fordulatot.", "Ha az adat kora számít, írd oda a dátumát vagy a forrását."],
        "Töröld a kitételt: „{r}”.",
    ),
    "hizelges": (
        "Töröld a hízelgő fordulatokat",
        "A kérdés vagy a téma dicsérete magyarul kínosan hat, és nem válasz.",
        ["Töröld a mondatot, és kezdd a tárggyal."],
        "Töröld, és térj a tárgyra: „{r}”.",
    ),
    "birtokos-halmozas": (
        "Bontsd szét az egymásra torlódó birtokos szerkezeteket",
        "Három-négy egymásba ágyazott birtokos viszonyt az olvasó visszafelé kénytelen kibogozni.",
        [
            "Keresd meg a lánc végén álló főnevet: az a mondat valódi tárgya.",
            "A láncból csinálj mellékmondatot vagy külön mondatot igével („megnéztük, hogyan…”).",
            "Egy szerkezetben legfeljebb két birtokos viszony maradjon.",
        ],
        "Bontsd igei mondatra a birtokos láncot: „{r}”.",
    ),
    "amely-lanc": (
        "Bontsd fel az „amely”-láncokat",
        "Az egymásba fűzött vonatkozó mellékmondatok végére az olvasó elveszíti a főmondatot.",
        [
            "Jelöld meg a főmondatot; az maradjon egyben.",
            "A rövid mellékmondatból csinálj jelzőt („a tavaly elnyert támogatás”).",
            "A hosszabbat tedd külön mondatba.",
        ],
        "Hagyj legfeljebb egy „amely” mellékmondatot, a többit írd jelzőnek vagy külön mondatnak: „{r}”.",
    ),
    "hivataloskodas": (
        "Egyszerűsítsd a hivataloskodó fordulatokat",
        "Ezek a fordulatok jogi és hivatali szövegbe valók; máshol távolságtartóvá teszik a hangot.",
        [
            "Döntsd el, kell-e a szöveg műfajához a hivatali hang. Ha igen, a találat maradhat.",
            "Ha nem: „az adott X” → „az X” vagy „ez az X”; „amennyiben” → „ha”; „X tekintetében” → ragos alak („X-ben”, „X-ről”).",
        ],
        "Mondd egyszerűbben, ha a műfaj engedi: „{r}”.",
    ),
    "ovatoskodas": (
        "Ritkítsd a tompításokat",
        "Az egymásra halmozott óvatoskodás után nem marad állítás.",
        [
            "Döntsd el, mennyire vagy biztos az állításban.",
            "Egy tompító szó maradjon („valószínűleg”), a többit töröld.",
            "Ha a bizonytalanságnak oka van, azt nevezd meg.",
        ],
        "Hagyj egyetlen tompítást, vagy állítsd határozottan: „{r}”.",
    ),
    "nemcsak-hanem": (
        "Egyszerűsítsd a „nemcsak… hanem… is” szerkezeteket",
        "Nyomatékként használva elkopik; a két tag többnyire egyszerűen összeadódik.",
        [
            "Ha a két tag egyenrangú, kösd össze „és”-sel.",
            "Csak ott hagyd meg, ahol a második tag valóban meglepő az első után.",
        ],
        "Próbáld „és”-sel összekötni a két tagot: „{r}”.",
    ),
    "nem-hanem-suruseg": (
        "Ritkítsd a „nem X, hanem Y” ellentéteket",
        "Ha egy bekezdésben többször is tagadással vezeted fel az állítást, az olvasó előbb azt tudja meg, mit nem mondasz.",
        [
            "Bekezdésenként legfeljebb egyet hagyj meg, ott, ahol a tagadott tag valódi félreértést hárít el.",
            "A többinél írd le közvetlenül az állítást (az Y-t).",
            "Ha a tagadott rész (az X) is fontos, tedd külön mondatba.",
        ],
        "Ebben a bekezdésben írd egyenes állításnak az ellentétek többségét; az első: „{r}”.",
    ),
    "hato-heto-suruseg": (
        "Nevezd meg a cselekvőt a „-ható/-hető” alakok helyett",
        "A személytelen alakok sorozata elrejti, ki állít, ki mér, ki következtet.",
        [
            "Nézd végig a bekezdés „-ható/-hető” alakjait.",
            "Ahol te vagy a cselekvő, írd első személyben („megállapítom”, „azt látjuk”).",
            "Ahol a lehetőség a lényeg („a módszer más adatokon is használható”), az alak maradhat.",
        ],
        "Ebben a bekezdésben írd át cselekvő igére a személytelen alakok egy részét; az első: „{r}”.",
    ),
    "harmas-felsorolas": (
        "Nézd át a hármas felsorolásokat",
        "A gépies szöveg ritmusból sorol hármat akkor is, ha csak egy vagy kettő tag számít.",
        [
            "Minden felsorolásnál kérdezd meg: mindhárom tag külön dolgot jelent?",
            "A rokon értelmű tagokat vond össze, a súlytalant töröld.",
            "Ahol tényleg három dolog van, a felsorolás maradjon.",
        ],
        "Ebben a bekezdésben ellenőrizd, mindhárom tag kell-e; az első felsorolás: „{r}”.",
    ),
    "felkover-suruseg": (
        "Ritkítsd a félkövér kiemeléseket",
        "Ha minden ki van emelve, semmi sincs kiemelve.",
        ["Bekezdésenként legfeljebb egy-két kiemelést hagyj, a kulcsfogalmon."],
        "Ebben a bekezdésben hagyj kevesebb kiemelést; az első: „{r}”.",
    ),
    "hosszu-mondat": (
        "Bontsd fel a túl hosszú mondatokat",
        "Negyven szó fölött az olvasó a mondat végére elfelejti az elejét.",
        [
            "Számold meg, hány önálló állítás van a mondatban.",
            "Minden állítás kapjon saját mondatot; a kötőszó („mivel”, „amely”, „és”) helyén vágj.",
            "A két-három rövidebb mondat hossza váltakozzon.",
        ],
        "Bontsd két-három mondatra: „{r}”.",
    ),
    "idezojel": (
        "Javítsd magyarra az idézőjeleket",
        "Magyar szövegben az idézőjel alul nyit és felül zár.",
        [
            "Cseréld a nyitó jelet „-re, a zárót ”-re.",
            "Idézeten belüli idézethez »ilyen« jelet használj.",
        ],
        "Cseréld magyar idézőjelre: {r}.",
    ),
}

_FORDITOTT = [
    (az, [re.compile(m, FLAGS) for m in mintak])
    for az, _s, _l, _j, mintak in KIFEJEZES_SZABALYOK
]
_SURUSEG = [
    (az, re.compile(minta, FLAGS), kuszob)
    for az, _s, _l, _j, minta, kuszob in SURUSEG_SZABALYOK
]


# ---------------------------------------------------------------------------
# Beolvasás
# ---------------------------------------------------------------------------
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_szoveg(utvonal):
    """A .docx törzsszövege, bekezdésenként üres sorral elválasztva."""
    with zipfile.ZipFile(utvonal) as z:
        gyoker = ElementTree.fromstring(z.read("word/document.xml"))
    bekezdesek = []
    for p in gyoker.iter(W_NS + "p"):
        reszek = []
        for elem in p.iter():
            if elem.tag == W_NS + "t" and elem.text:
                reszek.append(elem.text)
            elif elem.tag in (W_NS + "tab", W_NS + "br"):
                reszek.append(" ")
        szoveg = "".join(reszek).strip()
        if szoveg:
            bekezdesek.append(szoveg)
    return "\n\n".join(bekezdesek)


def beolvas(utvonal):
    if utvonal == "-":
        return sys.stdin.read()
    if utvonal.lower().endswith(".docx"):
        return docx_szoveg(utvonal)
    with open(utvonal, encoding="utf-8-sig") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Ellenőrzés
# ---------------------------------------------------------------------------
def _kod_kitakarasa(szoveg):
    """A Markdown-kódrészleteket azonos hosszú szóközzel takarja ki."""
    return KODBLOKK_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), szoveg)


def _sor_oszlop(sorkezdetek, poz):
    also, felso = 0, len(sorkezdetek) - 1
    while also < felso:
        kozep = (also + felso + 1) // 2
        if sorkezdetek[kozep] <= poz:
            also = kozep
        else:
            felso = kozep - 1
    return also + 1, poz - sorkezdetek[also] + 1


def _rovid(szoveg, hossz=90):
    szoveg = " ".join(szoveg.split())
    return szoveg if len(szoveg) <= hossz else szoveg[: hossz - 1] + "…"


def ellenoriz(szoveg, kihagy=()):
    """Visszaadja a találatok listáját (szótárak), a szövegbeli sorrendben."""
    kihagy = set(kihagy)
    tiszta = _kod_kitakarasa(szoveg)
    sorkezdetek = [0] + [m.end() for m in re.finditer(r"\n", tiszta)]
    talalatok = []

    def felvesz(az, kezdet, veg, megjegyzes=None):
        if az in kihagy:
            return
        szint, leiras, javaslat = SZABALY_LEIRASOK[az]
        sor, oszlop = _sor_oszlop(sorkezdetek, kezdet)
        talalatok.append(
            {
                "szabaly": az,
                "szint": szint,
                "sor": sor,
                "oszlop": oszlop,
                "reszlet": _rovid(tiszta[kezdet:veg]),
                "leiras": leiras if megjegyzes is None else "%s (%s)" % (leiras, megjegyzes),
                "javaslat": javaslat,
            }
        )

    for az, mintak in _FORDITOTT:
        foglalt = []
        for minta in mintak:
            for m in minta.finditer(tiszta):
                if any(m.start() < v and k < m.end() for k, v in foglalt):
                    continue
                foglalt.append((m.start(), m.end()))
                felvesz(az, m.start(), m.end())

    for bek in BEKEZDES_RE.finditer(tiszta):
        for az, minta, kuszob in _SURUSEG:
            egyezesek = list(minta.finditer(bek.group(0)))
            if az == "harmas-felsorolas":
                # A nevek felsorolása (például szerzőhármas) nem stíluskérdés.
                egyezesek = [
                    m for m in egyezesek
                    if not all(s[:1].isupper() for s in re.split(r",\s+|\s+", m.group(0)) if len(s) > 3)
                ]
            if len(egyezesek) >= kuszob:
                elso = egyezesek[0]
                felvesz(
                    az,
                    bek.start() + elso.start(),
                    bek.start() + elso.end(),
                    "%d db a bekezdésben" % len(egyezesek),
                )

    for mondat in MONDAT_RE.finditer(tiszta):
        resz = mondat.group(0)
        if not resz.strip():
            continue
        eltolas = len(resz) - len(resz.lstrip())
        szavak = len(SZO_RE.findall(resz))
        if szavak > HOSSZU_MONDAT_SZO:
            felvesz("hosszu-mondat", mondat.start() + eltolas, mondat.end(), "%d szó" % szavak)
        amelyek = AMELY_RE.findall(resz)
        if len(amelyek) >= AMELY_LANC_DB:
            felvesz("amely-lanc", mondat.start() + eltolas, mondat.end(), "%d db" % len(amelyek))

    for m in EGYENES_IDEZOJEL_RE.finditer(tiszta):
        felvesz("idezojel", m.start(), m.end())

    talalatok.sort(key=lambda t: (t["sor"], t["oszlop"], t["szabaly"]))
    return talalatok


def osszesites(szoveg, talalatok):
    szavak = len(SZO_RE.findall(_kod_kitakarasa(szoveg)))
    szabalyonkent = Counter(t["szabaly"] for t in talalatok)
    return {
        "szavak": szavak,
        "talalatok": len(talalatok),
        "ezer_szora": round(len(talalatok) * 1000.0 / szavak, 1) if szavak else 0.0,
        "szabalyonkent": dict(szabalyonkent.most_common()),
    }


# ---------------------------------------------------------------------------
# Javítási útmutató
# ---------------------------------------------------------------------------
def _hely(talalat, docx):
    """Ember számára olvasható helymegjelölés."""
    if docx:  # a kinyert szövegben a bekezdéseket üres sor választja el
        return "%d. bekezdés" % ((talalat["sor"] + 1) // 2)
    return "%d. sor" % talalat["sor"]


def utmutato(fajl, talalatok, osszes, docx=False):
    """Markdown javítási útmutató: mit, miért és hol kell javítani, utasításokként."""
    ki = ["# Javítási útmutató: %s" % fajl, ""]
    if not talalatok:
        ki += ["A program nem talált megjelölendő fordulatot (%d szó)." % osszes["szavak"], ""]
        return "\n".join(ki)

    csoportok = {}
    for t in talalatok:
        csoportok.setdefault(t["szabaly"], []).append(t)
    # Előbb a „figyelem” szintű teendők, azon belül a gyakoribb elöl.
    sorrend = sorted(
        csoportok,
        key=lambda az: (-SZINTEK[SZABALY_LEIRASOK[az][0]], -len(csoportok[az]), az),
    )

    ki += [
        "A szövegben %d megjelölt hely van %d szóra (%.1f / ezer szó), %d féle teendővel."
        % (osszes["talalatok"], osszes["szavak"], osszes["ezer_szora"], len(sorrend)),
        "",
        "Az útmutató utasításokat ad, a szöveget nem írja át. Minden jelölés kérdés: "
        "ha egy fordulat a műfajhoz tartozik vagy szándékos, maradhat.",
        "",
        "## 1. Teendők fontossági sorrendben",
        "",
    ]
    for i, az in enumerate(sorrend, 1):
        cim, miert, lepesek, _sablon = UTMUTATO[az]
        helyek = csoportok[az]
        szint = SZABALY_LEIRASOK[az][0]
        ki.append("### %d. %s" % (i, cim))
        ki.append("")
        ki.append(
            "%d hely · %s · szabály: `%s`"
            % (len(helyek), "javítandó" if szint == "figyelem" else "mérlegelendő", az)
        )
        ki.append("")
        ki.append("**Miért gond:** %s" % miert)
        ki.append("")
        ki.append("**Így javítsd:**")
        ki.append("")
        for n, lepes in enumerate(lepesek, 1):
            ki.append("%d. %s" % (n, lepes))
        ki.append("")
        ki.append("**Hol:**")
        ki.append("")
        for t in helyek:
            ki.append("- %s: „%s”" % (_hely(t, docx), t["reszlet"]))
        ki.append("")

    ki += ["## 2. Végighaladás a szövegen", "", "A fenti teendők a szöveg sorrendjében, helyenként:", ""]
    elozo = None
    for t in talalatok:
        hely = _hely(t, docx)
        if hely != elozo:
            if elozo is not None:
                ki.append("")
            ki.append("**%s**" % hely)
            ki.append("")
            elozo = hely
        ki.append("- %s" % UTMUTATO[t["szabaly"]][3].format(r=t["reszlet"]))
    ki.append("")
    ki += [
        "## 3. Ellenőrzés a javítás után",
        "",
        "1. Olvasd fel hangosan az átírt bekezdéseket: ahol megakadsz, ott még dolgozni kell.",
        "2. Nézd meg, hogy a tartalom nem változott-e: minden tény, szám és hivatkozás megvan.",
        "3. Futtasd újra a programot, és vesd össze a találatok számát.",
        "",
    ]
    return "\n".join(ki)


# ---------------------------------------------------------------------------
# Parancssor
# ---------------------------------------------------------------------------
def _szabalylista():
    sorok = []
    for az in sorted(SZABALY_LEIRASOK):
        szint, leiras, javaslat = SZABALY_LEIRASOK[az]
        sorok.append("%-22s %-9s %s\n%33s%s" % (az, szint, leiras, "", javaslat))
    return "\n".join(sorok)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="stiluslint",
        description="Gépies, hivataloskodó fordulatok megjelölése magyar szövegben. "
        "Csak jelöl és javasol, a szöveget nem írja át.",
    )
    p.add_argument("fajlok", nargs="*", metavar="FÁJL", help=".txt, .md vagy .docx; „-” a szabványos bemenet")
    p.add_argument("--json", action="store_true", help="gépi feldolgozásra alkalmas JSON-kimenet")
    p.add_argument("--utmutato", action="store_true", help="javítási útmutató Markdown formában: mit, miért és hol javíts")
    p.add_argument("--kimenet", metavar="FÁJL", help="a kimenet ebbe a fájlba kerül a képernyő helyett")
    p.add_argument("--kihagy", default="", metavar="SZABÁLY[,SZABÁLY]", help="kihagyandó szabályok azonosítói")
    p.add_argument("--szint", choices=sorted(SZINTEK, key=SZINTEK.get), default="info", help="legalább ilyen szintű találatok (alapértelmezés: info)")
    p.add_argument("--szabalyok", action="store_true", help="a szabályok listája")
    p.add_argument("--szigoru", action="store_true", help="1-es kilépési kód, ha van találat")
    p.add_argument("--version", action="version", version="stiluslint " + __version__)
    args = p.parse_args(argv)

    if args.szabalyok:
        print(_szabalylista())
        return 0
    if not args.fajlok:
        p.error("adj meg legalább egy fájlt (vagy „-” a szabványos bemenethez)")

    kihagy = [s.strip() for s in args.kihagy.split(",") if s.strip()]
    ismeretlen = [s for s in kihagy if s not in SZABALY_LEIRASOK]
    if ismeretlen:
        p.error("ismeretlen szabály: " + ", ".join(ismeretlen))

    kuszob = SZINTEK[args.szint]
    eredmenyek = []
    volt_talalat = False
    for utvonal in args.fajlok:
        try:
            szoveg = beolvas(utvonal)
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, ElementTree.ParseError) as hiba:
            print("stiluslint: %s: nem olvasható (%s)" % (utvonal, hiba), file=sys.stderr)
            return 2
        talalatok = [t for t in ellenoriz(szoveg, kihagy) if SZINTEK[t["szint"]] >= kuszob]
        volt_talalat = volt_talalat or bool(talalatok)
        eredmenyek.append({"fajl": utvonal, "talalatok": talalatok, "osszesites": osszesites(szoveg, talalatok)})

    if args.json and args.utmutato:
        p.error("a --json és az --utmutato nem használható együtt")

    sorok = []
    if args.json:
        sorok.append(json.dumps(eredmenyek, ensure_ascii=False, indent=2))
    elif args.utmutato:
        for e in eredmenyek:
            docx = e["fajl"].lower().endswith(".docx")
            sorok.append(utmutato(e["fajl"], e["talalatok"], e["osszesites"], docx))
    else:
        for e in eredmenyek:
            for t in e["talalatok"]:
                sorok.append("%s:%d:%d  %s  [%s]" % (e["fajl"], t["sor"], t["oszlop"], t["szint"], t["szabaly"]))
                sorok.append("    %s: „%s”" % (t["leiras"], t["reszlet"]))
                sorok.append("    → %s" % t["javaslat"])
            o = e["osszesites"]
            sorok.append("%s: %d találat, %d szó (%.1f / ezer szó)" % (e["fajl"], o["talalatok"], o["szavak"], o["ezer_szora"]))
            for az, db in o["szabalyonkent"].items():
                sorok.append("    %-22s %d" % (az, db))
    szoveg_ki = "\n".join(sorok) + "\n"

    if args.kimenet:
        try:
            with open(args.kimenet, "w", encoding="utf-8") as f:
                f.write(szoveg_ki)
        except OSError as hiba:
            print("stiluslint: %s: nem írható (%s)" % (args.kimenet, hiba), file=sys.stderr)
            return 2
    else:
        sys.stdout.write(szoveg_ki)
    return 1 if (args.szigoru and volt_talalat) else 0


if __name__ == "__main__":
    sys.exit(main())
