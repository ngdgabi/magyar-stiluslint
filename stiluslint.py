#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""magyar-stiluslint: gépies, hivataloskodó fordulatok megjelölése magyar és angol szövegben.

A program csak jelöl és javaslatot ad. Nem írja át a szöveget, nem becsüli meg,
hogy azt ember vagy gép írta-e, és nem MI-detektorok ellen készült.

Flags mechanical, bureaucratic phrasing in Hungarian and English prose. It only
flags and advises; it never rewrites, and it is not an AI detector.

Használat / usage:
    python3 stiluslint.py szoveg.txt
    python3 stiluslint.py paper.docx --lang en --guide --output guide.md
    cat szoveg.md | python3 stiluslint.py - --json

Csak a Python szabványos könyvtárát használja (3.8+).
"""

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree

__version__ = "0.3.0"

SZINTEK = {"info": 0, "figyelem": 1}
FLAGS = re.IGNORECASE | re.UNICODE | re.MULTILINE

# Mondat eleje (sor eleje vagy mondatzáró írásjel után).
ME = r"(?:^|(?<=[.!?…]\s))"


NEVSOR = "nevsor"  # a hármas felsorolásnál a csupa nagybetűs névsor kivétel


class Szabaly(object):
    """Egy stílusszabály a hozzá tartozó útmutató-szöveggel.

    mintak   -- reguláris kifejezések; kifejezés-szabálynál minden egyezés találat
    suruseg  -- (küszöb, hatókör): csak akkor jelez, ha a bekezdésben ("b") vagy
                a mondatban ("m") legalább ennyi egyezés van
    kivetel  -- az erre illeszkedő egyezések nem számítanak
    kulon    -- kóddal megvalósított szabály: "hosszu", "lanc", "ritmus"
    """

    def __init__(self, az, szint, leiras, javaslat, cim, miert, lepesek, sablon,
                 mintak=None, suruseg=None, kivetel=None, kulon=None):
        self.az = az
        self.szint = szint
        self.leiras = leiras
        self.javaslat = javaslat
        self.cim = cim
        self.miert = miert
        self.lepesek = lepesek
        self.sablon = sablon
        self.mintak = [re.compile(m, FLAGS) for m in (mintak or [])]
        self.suruseg = suruseg
        self.kivetel = kivetel if kivetel in (None, NEVSOR) else re.compile(kivetel, FLAGS)
        self.kulon = kulon


HOSSZU_MONDAT_SZO = 40
LANC_DB = 3
EMOJI = r"[\U0001F300-\U0001FAFF☀-⛿✀-➿]"
CIMKE = r"^[ \t]*(?:[-*•]|\d+\.)[ \t]+\*\*[^*\n]{1,60}:\*\*"

# ===========================================================================
# Magyar szabályok
# ===========================================================================
HU = [
    Szabaly(
        "kerul-asra", "figyelem",
        "Körülíró szerkezet („-ásra/-ésre kerül”)",
        "Nevezd meg, ki mit csinál: „megállapításra került” → „megállapítottuk”.",
        "Oldd fel a körülíró („-ásra/-ésre kerül”) szerkezeteket",
        "A szerkezet elrejti, ki cselekszik, és hivatali hangot ad a mondatnak.",
        ["Keresd meg, ki végzi a cselekvést (a szerző, a kutatók, a rendszer).",
         "Tedd őt alannyá, a főnevet pedig alakítsd vissza igévé.",
         "Ha a cselekvő tényleg ismeretlen vagy lényegtelen, használj többes szám harmadik személyt („bevezették”)."],
        "Nevezd meg a cselekvőt, és írd át igével: „{r}”.",
        mintak=[r"\b\w+(?:ásra|ésre)\s+ker[üu]l\w*", r"\bker[üu]l\w*\s+\w+(?:ásra|ésre)\b",
                r"\bsor\s+ker[üu]l\w*\s+\w+", r"\bker[üu]l\w*\s+sor\b"],
    ),
    Szabaly(
        "funkcioige", "figyelem",
        "Főnevesítés funkcióigével",
        "Használd magát az igét: „elvégzi az ellenőrzést” → „ellenőrzi”.",
        "Cseréld igére a funkcióigés főnevesítéseket",
        "A „főnév + végez/biztosít/irányul” kétszer olyan hosszú, mint az ige, és semmit nem tesz hozzá.",
        ["Keresd meg a szerkezetben a főnévbe rejtett igét („ellenőrzés” → „ellenőriz”).",
         "Írd át a mondatot ezzel az igével, a segédigét hagyd el.",
         "Olvasd újra: ha a mondat rövidebb lett és ugyanazt mondja, a csere jó."],
        "Használd a főnévbe rejtett igét: „{r}”.",
        mintak=[r"\b(?:el)?vég(?:ez|z)\w*\s+(?:\w+\s+){0,3}?\w+(?:ását|ését|ást|ést)\b",
                r"\b\w+(?:ását|ését|ást|ést)\s+(?:el)?vég(?:ez|z)\w*",
                r"\b\w+(?:ást|ést)\s+(?:eszközöl|foganatosít|hajt\w*\s+végre)\w*",
                r"\blehetőséget\s+(?:biztosít|nyújt|kínál|teremt)\w*",
                r"\b\w+(?:ásra|ésre)\s+irányul\w*",
                r"\b\w+(?:ást|ést)\s+(?:nyer|talál)\w*",
                r"\b(?:megvalósítás|végrehajtás|alkalmazás|felhasználás)\w*\s+(?:történik|valósul\s+meg)\b",
                r"\b\w+(?:ás|és)\w{0,5}\s+(?:történik|zajlik|megy\s+végbe)\b",
                r"\bjavaslatot\s+tesz\w*", r"\bdöntést\s+hoz\w*", r"\bhatást\s+gyakorol\w*",
                r"\bbefolyást\s+gyakorol\w*", r"\bsegítséget\s+nyújt\w*", r"\btámogatást\s+nyújt\w*",
                r"\bfelhasználásra\s+ker\w+", r"\balkalmazást\s+nyer\w*"],
    ),
    Szabaly(
        "valo-torteno", "figyelem",
        "„Való/történő” töltelék ragos főnév után",
        "Írd át igével: „a kérdéshez való kapcsolás” → „a kérdéshez kapcsolom”.",
        "Írd át a „való/történő” szerkezeteket",
        "A „-hoz való”, „-val történő” a főnevesítés kelléke; igével a mondat rövidebb és világosabb.",
        ["Keresd meg a „való/történő” utáni főnevet, és alakítsd igévé.",
         "A ragos főnév maradjon az ige bővítménye („a modellhez kapcsolom”).",
         "Ha jelzőként kell, próbáld a ragos alakot önmagában („a hagyományhoz kötődés”)."],
        "Írd át igével a „való/történő” szerkezetet: „{r}”.",
        mintak=[r"\b\w+(?:hoz|hez|höz|ra|re|ba|be|ban|ben|val|vel|tól|től|ról|ről|ból|ből|nak|nek|ig|ként|on|en|ön)\s+(?:való|történő)\s+\w+"],
        kivetel=r"\bvaló\s+(?:viszony|jog|hűség|igény)\w*",  # rögzült szókapcsolatok
    ),
    Szabaly(
        "toltelek", "figyelem",
        "Töltelékfordulat",
        "Töröld a felvezetést, és kezdd a mondatot a tartalommal.",
        "Töröld a töltelékfelvezetéseket",
        "A felvezetés bejelenti, hogy fontos dolog következik, ahelyett hogy kimondaná.",
        ["Töröld a fordulatot a „hogy” kötőszóval együtt.",
         "Kezdd a mondatot azzal, ami a felvezetés után állt.",
         "Ha a mondat így súlytalannak hat, a tartalmát erősítsd, ne a felvezetést tedd vissza."],
        "Töröld a felvezetést, és kezdd a mondatot a tartalommal: „{r}”.",
        mintak=[r"\bfontos\s+(?:megjegyezni|kiemelni|hangsúlyozni|megemlíteni|leszögezni|látni|megérteni|tudni),?\s+hogy\b",
                r"\bérdemes\s+(?:megjegyezni|kiemelni|megemlíteni|hangsúlyozni|megfigyelni),?\s+hogy\b",
                r"\b(?:ki\s+kell\s+emelni|hangsúlyozni\s+kell|meg\s+kell\s+jegyezni|le\s+kell\s+szögezni),?\s+hogy\b",
                r"\bebben\s+az\s+összefüggésben\b", r"\bebben\s+a\s+kontextusban\b",
                r"\bmint\s+(?:azt\s+)?(?:korábban|fentebb|már)\s+említett(?:ük|em)\b",
                r"\bösszességében\s+(?:elmondható|megállapítható|kijelenthető)\b",
                r"\b(?:elmondható|megállapítható|kijelenthető|leszögezhető|kiemelendő|megjegyzendő),?\s+hogy\b",
                r"\bnem\s+szabad\s+megfeledkezni\s+arról\b",
                r"\bfigyelembe\s+(?:kell\s+)?venni\s+azt\s+a\s+tényt,?\s+hogy\b",
                r"\bnem\s+túlzás\s+azt\s+állítani\b", r"\bnem\s+meglepő,?\s+hogy\b",
                r"\bmagától\s+értetődik,?\s+hogy\b", r"\bköztudott,?\s+hogy\b",
                r"\ba\s+helyzet\s+az,?\s+hogy\b", r"\bfelmerül\s+a\s+kérdés,?\s+hogy\b"],
    ),
    Szabaly(
        "terjengos-kotoszo", "figyelem",
        "Terjengős kötőszói szerkezet",
        "Van rövidebb: „annak érdekében, hogy” → „hogy”; „abban az esetben, ha” → „ha”.",
        "Rövidítsd a terjengős kötőszói szerkezeteket",
        "Három-négy szó áll egyetlen kötőszó helyén, és lassítja az olvasást.",
        ["Cseréld: „annak érdekében, hogy” → „hogy”; „abban az esetben, ha” → „ha”; „annak ellenére, hogy” → „bár”; „azt a tényt, hogy” → „azt, hogy”.",
         "Olvasd újra a mondatot: a jelentésnek nem szabad változnia."],
        "Cseréld rövid kötőszóra: „{r}”.",
        mintak=[r"\bannak\s+érdekében,?\s+hogy\b", r"\babban\s+az\s+esetben,?\s+(?:ha|amennyiben)\b",
                r"\bannak\s+ellenére,?\s+hogy\b", r"\bazt\s+a\s+tényt,?\s+hogy\b",
                r"\bazzal\s+kapcsolatban,?\s+hogy\b", r"\bolyan\s+módon,?\s+hogy\b",
                r"\barra\s+való\s+tekintettel,?\s+hogy\b", r"\bannak\s+köszönhetően,?\s+hogy\b",
                r"\babból\s+a\s+célból,?\s+hogy\b", r"\bazon\s+oknál\s+fogva\b"],
    ),
    Szabaly(
        "felnagyitas", "figyelem",
        "A jelentőség felnagyítása",
        "Írd le, miért fontos, vagy hagyd el a jelzőt.",
        "Vedd vissza a felnagyító jelzőket",
        "Ha minden kulcsfontosságú, az olvasó nem tudja, mi az, ami tényleg az.",
        ["Kérdezd meg a mondattól: miért fontos ez, és kinek?",
         "Ha van válasz, azt írd le a jelző helyett. Ha nincs, töröld a jelzőt."],
        "Írd le a jelző helyett, miért fontos, vagy töröld: „{r}”.",
        mintak=[r"\bkulcsfontosságú\w*", r"\blétfontosságú\w*", r"\bnélkülözhetetlen\w*",
                r"\b(?:döntő|kiemelkedő|alapvető|meghatározó|kiemelt)\s+(?:jelentőség|fontosság|szerep)\w*",
                r"\brendkívül\s+(?:fontos|jelentős|gyors|nagy|hasznos|összetett)\w*",
                r"\bjelentős\s+(?:mértékben|szerepet|előrelépés\w*|hatás\w*|javulás\w*|előny\w*)",
                r"\bmérföldkő\w*", r"\bparadigmaváltás\w*", r"\báttörés\w*"],
    ),
    Szabaly(
        "reklamiz", "figyelem",
        "Reklámízű jelző",
        "Semleges szövegben cseréld tényre vagy töröld.",
        "Cseréld tényre a reklámízű jelzőket",
        "Semleges szövegben a reklámnyelv hiteltelenné teszi az állítást.",
        ["Írd le, miben különbözik a dolog a többitől (adat, példa, összehasonlítás).",
         "Ha ilyet nem tudsz mondani, hagyd el a jelzőt."],
        "Cseréld konkrét tulajdonságra vagy töröld: „{r}”.",
        mintak=[r"\begyedülálló\w*", r"\búttörő\w*", r"\bforradalmi\w*", r"\bpáratlan\w*",
                r"\bvilágszínvonalú\w*", r"\bélvonalbeli\w*", r"\binnovatív\w*",
                r"\blenyűgöző\w*", r"\blélegzetelállító\w*", r"\bkorszakalkotó\w*",
                r"\bcsúcsminőség\w*", r"\bprémium\s+\w+"],
    ),
    Szabaly(
        "divatszo", "info",
        "Divatszó, amely keveset mond",
        "Írd le konkrétan, mire gondolsz.",
        "Cseréld konkrétumra a divatszavakat",
        "A „komplex”, „átfogó”, „dinamikus” bármire ráillik, ezért nem jellemzi azt, amiről írsz.",
        ["Kérdezd meg: mitől komplex, miben átfogó?",
         "A választ írd a szó helyére, vagy hagyd el a szót."],
        "Mondd meg konkrétan, mit jelent itt: „{r}”.",
        mintak=[r"\bholisztikus\w*", r"\bsokrétű\w*", r"\bzökkenőmentes\w*", r"\brobusztus\w*",
                r"\bdinamikus(?:an)?\s+\w+", r"\bátfogó\s+(?:kép\w*|megoldás\w*|megközelítés\w*|áttekintés\w*|elemzés\w*)",
                r"\bkomplex\s+(?:megoldás\w*|rendszer\w*|megközelítés\w*|folyamat\w*)",
                r"\bszerves\s+rész\w*", r"\brávilágít\w*", r"\bkiaknáz\w*",
                r"\ba\s+mai\s+(?:rohanó|modern|digitális|felgyorsult)\s+világ\w*",
                r"\bnapjaink\w*\s+(?:egyik\s+)?(?:legfontosabb|legnagyobb)\b",
                r"\bszámos\s+(?:lehetőség|előny|kihívás|tényező)\w*",
                r"\bszéles\s+(?:körű|körben|skál\w+|spektrum\w*)", r"\bértéket\s+teremt\w*"],
    ),
    Szabaly(
        "letige-kerules", "info",
        "A „van” kerülése körülírással",
        "Gyakran elég a létige vagy egy egyszerű ige: „eszközként szolgál” → „eszköz”.",
        "Használd bátran a „van” igét",
        "A „szolgál”, „rendelkezik”, „szerepet játszik” fontoskodva mondja ki azt, amit a „van” vagy az egyszerű ige is kimond.",
        ["„X-ként szolgál/működik” → „X”; „rendelkezik valamivel” → „van valamije”; „szerepet játszik benne” → „hat rá / része”.",
         "Ha az egyszerű ige pontatlan volna, a találat maradhat."],
        "Próbáld a „van” igével vagy egyszerű igével: „{r}”.",
        mintak=[r"\b\w+ként\s+(?:szolgál|működik|funkcionál)\w*",
                r"\b(?:fontos|jelentős|központi|meghatározó|kiemelt)?\s*szerepet\s+(?:játsz\w+|tölt\w*\s+be)",
                r"\bjelentőséggel\s+bír\w*", r"\b\w+(?:val|vel)\s+rendelkez\w+", r"\brendelkez\w+\s+\w+(?:val|vel)\b",
                r"\bszert\s+tesz\w*", r"\btesz\w*\s+szert\b", r"\bmegtalálható\w*", r"\bfellelhető\w*"],
    ),
    Szabaly(
        "kivan-ige", "info",
        "„Kíván + főnévi igenév” az egyszerű ige helyett",
        "Mondd ki egyenesen: „hozzá kívánok járulni” → „hozzájárulok”.",
        "Mondd ki egyenesen a „kíván + igenév” szerkezeteket",
        "A „kívánok bemutatni” szándékot jelent be ott, ahol magát a cselekvést várja az olvasó.",
        ["Cseréld az igenevet ragozott igére („bemutatom”, „vizsgálom”).",
         "Kutatási tervben a jövő idő is jó („megvizsgálom”); a „kíván” csak ott maradjon, ahol tényleg a szándék a lényeg."],
        "Írd ragozott igével: „{r}”.",
        mintak=[r"\bkíván(?:ok|unk|om|juk|ja|nak|ják)?\s+(?:\w+\s+){0,2}?\w{3,}ni\b",
                r"\b\w{3,}ni\s+kíván(?:ok|unk|om|juk|ja|nak|ják)?\b",
                r"\bszeretn(?:ék|énk)\s+(?:\w+\s+){0,2}?(?:bemutatni|rámutatni|kiemelni|hangsúlyozni|megjegyezni)\b"],
    ),
    Szabaly(
        "altal-szerkezet", "info",
        "„Által” + befejezett melléknévi igenév",
        "Cselekvő mellékmondattal természetesebb: „a személy által vállalt” → „amelyet a személy vállal”.",
        "Fordítsd cselekvőre az „által” szerkezeteket",
        "Az „X által végzett Y” az angol szenvedő szerkezet tükre; magyarul a cselekvő áll elöl.",
        ["Írd át: „a kutatók által gyűjtött adatok” → „a kutatók gyűjtötte adatok” vagy „az adatok, amelyeket a kutatók gyűjtöttek”.",
         "Rövid, megszokott szakkifejezésnél („a szerző által idézett”) maradhat."],
        "Írd át cselekvő szerkezetre: „{r}”.",
        mintak=[r"\b\w+\s+által\s+(?:\w+\s+){0,2}?\w{3,}(?:ott|ett|ött|olt|elt|ált|ált|zett|zott|rt|nt|lt)\b"],
    ),
    Szabaly(
        "nevmas-tulzas", "figyelem",
        "Felesleges névmás vagy „ez egy olyan” szerkezet",
        "A magyar elhagyja a névmást, ha a rag mutatja: „Mi úgy gondoljuk” → „Úgy gondoljuk”.",
        "Hagyd el a felesleges névmásokat",
        "Az angol mintára kitett „mi”, „ez egy olyan” idegenül hat; a rag magyarul elég.",
        ["Töröld a személyes névmást, ha nincs rajta hangsúly.",
         "„Ez egy olyan eszköz, amely segít” → „Az eszköz segít”."],
        "Töröld a névmást vagy az „ez egy olyan” keretet: „{r}”.",
        mintak=[r"\bez\s+egy\s+olyan\b", r"\bmi\s+úgy\s+(?:gondoljuk|véljük|látjuk|hisszük)\b",
                r"\bsegít\s+(?:neked|önnek|nekünk)\s+abban,?\s+hogy\b",
                r"\bez\s+az,?\s+ami\b", r"\bez\s+az\s+a\s+\w+,\s+am(?:i|ely)\b"],
    ),
    Szabaly(
        "sablonos-lezaras", "figyelem",
        "Sablonos lezárás",
        "Töröld, vagy cseréld konkrét állításra.",
        "Írd át vagy töröld a sablonos lezárásokat",
        "Az általános derűlátás bármely szöveg végére odaillene, ezért itt sem mond semmit.",
        ["Töröld a mondatot, és nézd meg, hiányzik-e.",
         "Ha kell lezárás, mondj konkrétumot: mi következik, mi maradt nyitva."],
        "Töröld, vagy cseréld konkrét állításra: „{r}”.",
        mintak=[r"\ba\s+jövő\s+(?:fényesnek|ígéretesnek|izgalmasnak)\s+ígérkezik\b",
                r"\búj\s+(?:távlatokat|lehetőségeket|utakat|dimenziókat|kapukat)\s+nyit\w*",
                r"\btovábbra\s+is\s+(?:fejlődik|fejlődni\s+fog)\b", r"\ba\s+kihívások\s+ellenére\b",
                r"\bcsak\s+az\s+idő\s+(?:fogja\s+)?(?:mondja|dönti)\s+\w+", r"\bizgalmas\s+(?:időszak|jövő)\w*\s+(?:előtt|vár)\w*",
                r"\bkikövezi\s+az\s+utat\b", r"\bfontos\s+lépés\s+\w+\s+felé\b"],
    ),
    Szabaly(
        "osszegzo-nyito", "info",
        "Összegző mondatkezdet",
        "Az összegzést a tartalma jelezze; a bejelentése többnyire elhagyható.",
        "Hagyd el az összegző mondatkezdeteket",
        "Az „Összességében”, „Végezetül” bejelenti a lezárást, de maga nem állít semmit.",
        ["Töröld a kezdő szót, és nézd meg, megáll-e a mondat nélküle.",
         "Ha a bekezdés csak megismétli a korábbiakat, fontold meg a törlését."],
        "Kezdd a mondatot a tartalommal: „{r}”.",
        mintak=[ME + r"(?:Összességében|Összefoglalva|Összegzésként|Összegezve|Végezetül|Mindent\s+összevetve|Végső\s+soron|Zárásként|Mindezek\s+alapján|Mindezek\s+fényében)\b"],
    ),
    Szabaly(
        "homalyos-hivatkozas", "figyelem",
        "Homályos hivatkozás",
        "Nevezd meg a forrást, vagy hagyd el az állítást.",
        "Nevezd meg a forrásokat",
        "A meg nem nevezett tekintély nem ellenőrizhető, ezért nem is érv.",
        ["Keresd meg, melyik kutatásra, szerzőre vagy adatra gondoltál.",
         "Írd be név és évszám szerint, vagy hivatkozd meg.",
         "Ha nincs ilyen forrás, az állítást töröld, vagy jelöld saját véleményként."],
        "Írd oda a pontos forrást, vagy hagyd el az állítást: „{r}”.",
        mintak=[r"\b(?:szakértők|sokak|egyesek|kutatók|elemzők|megfigyelők)\s+(?:szerint|úgy\s+vélik)\b",
                r"\b(?:kutatások|tanulmányok|vizsgálatok|felmérések)\s+(?:bizonyítják|kimutatták|igazolják|szerint|azt\s+mutatják)\b",
                r"\baz\s+iparág\s+vezető\s+szereplői\b", r"\báltalános(?:an)?\s+(?:elfogadott|ismert),?\s+hogy\b",
                r"\bszéles\s+körben\s+(?:elfogadott|ismert|elterjedt)\s+(?:nézet|vélemény)\b"],
    ),
    Szabaly(
        "tudasvagas", "figyelem",
        "Felesleges kitétel a saját tudásszintről",
        "Hagyd el; az állítás enélkül is megáll.",
        "Töröld a saját tudásszintre tett kitételeket",
        "A kitétel nem ad információt, csak elbizonytalanítja az állítást.",
        ["Töröld a fordulatot.", "Ha az adat kora számít, írd oda a dátumát vagy a forrását."],
        "Töröld a kitételt: „{r}”.",
        mintak=[r"\b(?:legfrissebb|jelenlegi|legjobb)\s+(?:ismereteim|tudásom|információim)\s+szerint\b",
                r"\ba\s+rendelkezésre\s+álló\s+(?:adatok|információk)\s+alapján\b",
                r"\btudomásom\s+szerint\b"],
    ),
    Szabaly(
        "hizelges", "figyelem",
        "Hízelgő hangnem",
        "Töröld, és válaszolj a tárgyra.",
        "Töröld a hízelgő fordulatokat",
        "A kérdés vagy a téma dicsérete magyarul kínosan hat, és nem válasz.",
        ["Töröld a mondatot, és kezdd a tárggyal."],
        "Töröld, és térj a tárgyra: „{r}”.",
        mintak=[r"\b(?:remek|kiváló|nagyszerű|jó|érdekes)\s+(?:kérdés|észrevétel|felvetés|meglátás)\s*!",
                r"\bteljesen\s+igazad\s+van\b", r"\bfeltétlenül\s*!"],
    ),
    Szabaly(
        "chatbot-nyom", "figyelem",
        "Csevegőrobot-válasz maradványa",
        "Töröld: ez a válasz kerete volt, a szövegbe nem való.",
        "Töröld a csevegőrobot-válasz maradványait",
        "Ezek a mondatok egy beszélgetés keretei; kész szövegben elárulják, hogy a szöveget nem nézték át.",
        ["Töröld a bevezető és a záró udvariassági mondatot.",
         "Nézd át a szöveg elejét és végét: gyakran ott maradnak."],
        "Töröld a beszélgetésből maradt mondatot: „{r}”.",
        mintak=[r"\bremélem,?\s+(?:ez\s+)?(?:segít\w*|hasznos\w*)", r"\bszívesen\s+segítek\b",
                r"\bha\s+(?:bármi\s+)?(?:további\s+)?kérdésed\s+van\b", r"\bszólj,?\s+ha\b",
                r"\bmint\s+(?:MI|mesterséges\s+intelligencia|nyelvi\s+modell)\b",
                ME + r"(?:Természetesen|Persze|Rendben)\s*[!,]\s",
                ME + r"Íme\s+(?:a|az|egy|néhány)\b"],
    ),
    Szabaly(
        "udvariaskodas", "figyelem",
        "Túlzott udvariaskodás",
        "Kérj egyenesen: „Szeretettel várunk” többet mond.",
        "Egyszerűsítsd a túlzott udvariaskodást",
        "A nyakatekert kérés magyarul szervilisen vagy ironikusan hat.",
        ["Írd le a kérést egy egyszerű, udvarias mondatban.", "A feltételes mód halmozását szüntesd meg."],
        "Fogalmazd meg egyszerűen: „{r}”.",
        mintak=[r"\b(?:nagyon\s+)?hálás\s+lennék,?\s+(?:ha|amennyiben)\b", r"\bmegköszönn(?:ém|énk),?\s+ha\b",
                r"\blenne\s+szíves\b", r"\bszíveskedj\w*", r"\bszeretném\s+alázatosan\b",
                r"\bmegfontolni\s+annak\s+(?:a\s+)?lehetőségét\b"],
    ),
    Szabaly(
        "birtokos-halmozas", "figyelem",
        "Egymásra torlódó birtokos szerkezetek",
        "Bontsd igei mondatra.",
        "Bontsd szét az egymásra torlódó birtokos szerkezeteket",
        "Három-négy egymásba ágyazott birtokos viszonyt az olvasó visszafelé kénytelen kibogozni.",
        ["Keresd meg a lánc végén álló főnevet: az a mondat valódi tárgya.",
         "A láncból csinálj mellékmondatot vagy külön mondatot igével („megnéztük, hogyan…”).",
         "Egy szerkezetben legfeljebb két birtokos viszony maradjon."],
        "Bontsd igei mondatra a birtokos láncot: „{r}”.",
        mintak=[r"\b(?:\w+(?:ának|ének|ainak|einek|jának|jének)\s+){2,}\w+",
                r"\b\w+(?:ása|ése|ásának|ésének)\s+\w+(?:ásának|ésének)\s+\w+(?:a|e|ja|je|ai|ei)\b"],
    ),
    Szabaly(
        "amely-lanc", "figyelem",
        "Vonatkozó mellékmondatok lánca („amely… amely… amely”)",
        "Használj jelzős szerkezetet vagy külön mondatot.",
        "Bontsd fel az „amely”-láncokat",
        "Az egymásba fűzött vonatkozó mellékmondatok végére az olvasó elveszíti a főmondatot.",
        ["Jelöld meg a főmondatot; az maradjon egyben.",
         "A rövid mellékmondatból csinálj jelzőt („a tavaly elnyert támogatás”).",
         "A hosszabbat tedd külön mondatba."],
        "Hagyj legfeljebb egy „amely” mellékmondatot, a többit írd jelzőnek vagy külön mondatnak: „{r}”.",
        mintak=[r"\b(?:amely|amelyek|amely\w{1,6}|amelyek\w{1,6})\b"], kulon="lanc",
    ),
    Szabaly(
        "hivataloskodas", "info",
        "Hivataloskodó fordulat",
        "Ha nem jogi vagy hivatali szöveg, mondd egyszerűbben.",
        "Egyszerűsítsd a hivataloskodó fordulatokat",
        "Ezek a fordulatok jogi és hivatali szövegbe valók; máshol távolságtartóvá teszik a hangot.",
        ["Döntsd el, kell-e a szöveg műfajához a hivatali hang. Ha igen, a találat maradhat.",
         "Ha nem: „az adott X” → „az X” vagy „ez az X”; „amennyiben” → „ha”; „X tekintetében” → ragos alak („X-ben”, „X-ről”); „E szempont” → „Ez a szempont”."],
        "Mondd egyszerűbben, ha a műfaj engedi: „{r}”.",
        mintak=[r"\baz\s+adott\s+\w+", r"\ba\s+fent(?:ebb|iekben)?\s+említett\b", r"\ba\s+szóban\s+forgó\b",
                r"\bamennyiben\b", r"\bezen\s+(?:felül|túlmenően|kívül)\b",
                r"\b\w+\s+(?:tekintetében|vonatkozásában|viszonylatában|kapcsán)\b",
                r"\bennek\s+megfelelően\b", r"\bmindenekelőtt\b", r"\bigénybe\s+(?:kíván\w*\s+)?ve\w+",
                r"\bmiszerint\b", r"\bjelen\s+(?:tanulmány|dolgozat|kutatás|írás|fejezet|esetben)\w*",
                r"\belsődlegesen\b", r"\bezáltal\b", r"\bmindazonáltal\b", r"\billetőleg\b",
                r"(?<![\w-])e\s+(?:szempont|különbség|megkülönböztetés|dimenzió|kérdés|cél|tekintetben|célból|téren|keretben|megközelítés|fogalom|modell|területen|ponton)\w*",
                r"\behhez\s+képest\b", r"\ba\s+továbbiakban\b", r"\bfentiek\s+(?:alapján|értelmében|fényében)\b"],
    ),
    Szabaly(
        "ovatoskodas", "info",
        "Halmozott óvatoskodás",
        "Egy tompítás elég; ha tudod, állítsd határozottan.",
        "Ritkítsd a tompításokat",
        "Az egymásra halmozott óvatoskodás után nem marad állítás.",
        ["Döntsd el, mennyire vagy biztos az állításban.",
         "Egy tompító szó maradjon („valószínűleg”), a többit töröld.",
         "Ha a bizonytalanságnak oka van, azt nevezd meg."],
        "Hagyj egyetlen tompítást, vagy állítsd határozottan: „{r}”.",
        mintak=[r"\belképzelhető,?\s+hogy\s+(?:esetleg|talán)\b", r"\bbizonyos\s+(?:mértékben|körülmények\s+között|fokig|értelemben)\b",
                r"\b(?:vélhetően|feltételezhetően)\b", r"\besetleg\s+talán\b", r"\bvalamilyen\s+(?:szinten|mértékben|formában)\b",
                r"\btöbbé-kevésbé\b", r"\búgy\s+tűnik,?\s+(?:hogy\s+)?(?:talán|esetleg)\b", r"\bnémiképp(?:en)?\b"],
    ),
    Szabaly(
        "nemcsak-hanem", "info",
        "„Nemcsak… hanem… is” nyomatékként",
        "Gyakran elég az „és”: „hatékonyabb, és javítja az együttműködést”.",
        "Egyszerűsítsd a „nemcsak… hanem… is” szerkezeteket",
        "Nyomatékként használva elkopik; a két tag többnyire egyszerűen összeadódik.",
        ["Ha a két tag egyenrangú, kösd össze „és”-sel.",
         "Csak ott hagyd meg, ahol a második tag valóban meglepő az első után."],
        "Próbáld „és”-sel összekötni a két tagot: „{r}”.",
        mintak=[r"\bnem\s?(?:csak|csupán|pusztán|kizárólag)\b[^.!?\n]{0,160}?\bhanem\b"],
    ),
    Szabaly(
        "skala", "info",
        "„Valamitől valamiig” átfogóságot sugalló szerkezet",
        "Sorold fel, ami tényleg beletartozik: „a tervezést és a megvalósítást is”.",
        "Nézd át a „-tól -ig” szerkezeteket",
        "A skála teljességet ígér, de többnyire csak két dolgot nevez meg.",
        ["Ha valódi tartományról van szó (idő, mennyiség), maradhat.",
         "Ha csak hangzatos, írd le a két-három konkrét elemet."],
        "Ha nem valódi tartomány, nevezd meg a konkrét elemeket: „{r}”.",
        mintak=[r"\b\w{4,}(?:tól|től)\s+az?\s+(?:\w+\s+){0,2}?\w{4,}ig\b"],
    ),
    Szabaly(
        "nem-hanem-suruseg", "info",
        "Sok „nem X, hanem Y” ellentét egy bekezdésben",
        "Hagyj meg egyet-kettőt; a többit írd egyenes állításnak.",
        "Ritkítsd a „nem X, hanem Y” ellentéteket",
        "Ha egy bekezdésben többször is tagadással vezeted fel az állítást, az olvasó előbb azt tudja meg, mit nem mondasz.",
        ["Bekezdésenként legfeljebb egyet hagyj meg, ott, ahol a tagadott tag valódi félreértést hárít el.",
         "A többinél írd le közvetlenül az állítást (az Y-t).",
         "Ha a tagadott rész (az X) is fontos, tedd külön mondatba."],
        "Ebben a bekezdésben írd egyenes állításnak az ellentétek többségét; az első: „{r}”.",
        mintak=[r"\bnem\b[^.!?\n]{0,200}?,\s*hanem\b"], suruseg=(2, "b"),
    ),
    Szabaly(
        "hato-heto-suruseg", "info",
        "Sok személytelen „-ható/-hető” alak egy bekezdésben",
        "Nevezd meg a cselekvőt: „megállapítható” → „megállapítom / azt látjuk”.",
        "Nevezd meg a cselekvőt a „-ható/-hető” alakok helyett",
        "A személytelen alakok sorozata elrejti, ki állít, ki mér, ki következtet.",
        ["Nézd végig a bekezdés „-ható/-hető” alakjait.",
         "Ahol te vagy a cselekvő, írd első személyben („megállapítom”, „azt látjuk”).",
         "Ahol a lehetőség a lényeg („a módszer más adatokon is használható”), az alak maradhat."],
        "Ebben a bekezdésben írd át cselekvő igére a személytelen alakok egy részét; az első: „{r}”.",
        mintak=[r"\b\w{3,}(?:ható|hető)(?:k|ak|ek|vá|vé)?\b"], suruseg=(3, "b"),
    ),
    Szabaly(
        "fonevesites-suruseg", "info",
        "Sok „-ás/-és” főnév egy mondatban",
        "Néhányat alakíts vissza igévé; a mondat rövidebb és mozgalmasabb lesz.",
        "Alakítsd vissza igévé a halmozott „-ás/-és” főneveket",
        "Ha egy mondat cselekvéseit főnevek hordozzák, a mondatban nem történik semmi: minden „elkülönítés” és „rendszerezés”, senki nem különít el és nem rendszerez.",
        ["Jelöld meg a mondat „-ás/-és” végű főneveit.",
         "Válaszd ki a két legfontosabbat, és írd át őket igével, megnevezve, ki teszi.",
         "Ha így túl hosszú lesz a mondat, vágd ketté.",
         "A szakkifejezésként rögzült főnevek („megközelítés”, „elköteleződés”) maradhatnak."],
        "Ebben a mondatban legalább két főnevesítést írj át igével; az első: „{r}”.",
        mintak=[r"\b\w{3,}(?:ás|és)(?:[aeáé]\w{0,6}|ok|ek|t|sal|sel|nak|nek|ra|re|ban|ben|hoz|hez|ról|ről|ból|ből|ként)?\b"],
        suruseg=(4, "m"),
        kivetel=r"^(?:vallás|kérdés|kevés|írás|tudás|hatás|szokás|lakás|állás|egyéb|más|rész|bejegyzés|hozzászólás|választás|kutatás|jelentés|előadás|beszélgetés)\w*$",
    ),
    Szabaly(
        "igenev-suruseg", "info",
        "Sok „-va/-ve” határozói igenév egy mondatban",
        "Egy részüket írd ragozott igével vagy mellékmondattal.",
        "Ritkítsd a „-va/-ve” határozói igeneveket",
        "Az egymásra halmozott igenevek mögül eltűnik, mi az ok és mi az okozat.",
        ["Mondatonként legfeljebb egyet hagyj meg.",
         "A többit írd át: „figyelembe véve” → „mivel figyelembe vesszük” vagy külön mondat."],
        "Ebben a mondatban írd át igével az igenevek egy részét; az első: „{r}”.",
        mintak=[r"\b\w{5,}(?:va|ve|ván|vén)\b"], suruseg=(3, "m"),
        kivetel=r"^(?:\w*(?:könyve|nyelve|szerve|terve|kedve|műve|érve|elve|szíve|neve|helye))$",
    ),
    Szabaly(
        "atvezeto-suruseg", "info",
        "Sok átvezető kötőszóval kezdett mondat egy bekezdésben",
        "A mondatok kapcsolatát a tartalom mutassa; a kötőszavak többsége elhagyható.",
        "Ritkítsd a mondatkezdő átvezetéseket",
        "Az „Emellett”, „Továbbá”, „Ugyanakkor” sorozata felsorolássá lapítja a gondolatmenetet.",
        ["Töröld a kezdő kötőszót, és nézd meg, érthető-e a kapcsolat nélküle.",
         "Ahol ellentét vagy következmény van, az maradjon jelölve, de mondat közben („a minta azonban kicsi”)."],
        "Ebben a bekezdésben hagyd el a mondatkezdő kötőszavak többségét; az első: „{r}”.",
        mintak=[ME + r"(?:Emellett|Továbbá|Ezenkívül|Ezen\s+túlmenően|Mindemellett|Ugyanakkor|Ezáltal|Ennek\s+köszönhetően|Ennek\s+eredményeként|Éppen\s+ezért|Ebből\s+következően|Következésképpen|Mindez|Ezzel\s+szemben|Ráadásul|Sőt)\b"],
        suruseg=(2, "b"),
    ),
    Szabaly(
        "tehat-suruseg", "info",
        "Sok „tehát” egy bekezdésben",
        "Egy következtetés elég bekezdésenként; a többi „tehát” törölhető.",
        "Ritkítsd a „tehát” kötőszót",
        "Ha minden második mondat következtetésnek van álcázva, az olvasó nem tudja, melyik a valódi.",
        ["Hagyd meg azt az egyet, amelyik tényleg az előzőkből következik.", "A többinél töröld a szót."],
        "Ebben a bekezdésben egy „tehát” maradjon; az első: „{r}”.",
        mintak=[r"\b\w+\s+tehát\b|\btehát\s+\w+"], suruseg=(2, "b"),
    ),
    Szabaly(
        "harmas-felsorolas", "info",
        "Több hármas felsorolás egy bekezdésben",
        "Nézd meg, mindhárom tag kell-e; a gépies szöveg mindent hármasával sorol.",
        "Nézd át a hármas felsorolásokat",
        "A gépies szöveg ritmusból sorol hármat akkor is, ha csak egy vagy kettő tag számít.",
        ["Minden felsorolásnál kérdezd meg: mindhárom tag külön dolgot jelent?",
         "A rokon értelmű tagokat vond össze, a súlytalant töröld.",
         "Ahol tényleg három dolog van, a felsorolás maradjon."],
        "Ebben a bekezdésben ellenőrizd, mindhárom tag kell-e; az első felsorolás: „{r}”.",
        mintak=[r"\b\w{4,},\s+(?:az?\s+)?\w{4,}\s+(?:és|valamint|illetve|vagy)\s+(?:az?\s+)?\w{4,}\b"],
        suruseg=(2, "b"), kivetel=NEVSOR,
    ),
    Szabaly(
        "gondolatjel-suruseg", "info",
        "Sok gondolatjel egy bekezdésben",
        "Vesszővel, kettősponttal vagy külön mondattal többnyire jobb.",
        "Ritkítsd a gondolatjeleket",
        "A sűrű gondolatjel szaggatottá teszi a szöveget, és a gépi szöveg egyik ismertetőjegye.",
        ["Bekezdésenként legfeljebb egy közbevetés maradjon gondolatjelek között.",
         "A többit írd vesszővel, kettősponttal vagy külön mondatként."],
        "Ebben a bekezdésben cseréld a gondolatjelek többségét más írásjelre; az első: „{r}”.",
        mintak=[r"\w+\s+[–—]\s+\w+"], suruseg=(3, "b"),
    ),
    Szabaly(
        "felkover-suruseg", "info",
        "Sok félkövér kiemelés egy bekezdésben",
        "Csak azt emeld ki, ami tényleg figyelmet kíván.",
        "Ritkítsd a félkövér kiemeléseket",
        "Ha minden ki van emelve, semmi sincs kiemelve.",
        ["Bekezdésenként legfeljebb egy-két kiemelést hagyj, a kulcsfogalmon."],
        "Ebben a bekezdésben hagyj kevesebb kiemelést; az első: „{r}”.",
        mintak=[r"\*\*[^*\n]+\*\*"], suruseg=(4, "b"),
    ),
    Szabaly(
        "cimke-felsorolas", "info",
        "„Címke:” kezdetű listaelemek sora",
        "Folyó szövegben mondatként többet mond: „A teljesítmény javul”.",
        "Írd mondattá a „Címke:” kezdetű listaelemeket",
        "A félkövér címkével kezdett listaelemek sora diavetítésre emlékeztet, és elrejti az összefüggéseket.",
        ["Ha a pontok összefüggnek, írd meg őket egy bekezdésben.",
         "Ha lista kell, hagyd el a címkét, és kezdj teljes mondattal."],
        "Ezt a listát írd folyó szöveggé vagy címke nélküli mondatokká; az első elem: „{r}”.",
        mintak=[CIMKE], suruseg=(3, "b"),
    ),
    Szabaly(
        "emoji", "info",
        "Emoji vagy díszítő szimbólum",
        "Töröld, ha a szöveg nem kifejezetten kötetlen.",
        "Töröld a díszítő emojikat",
        "Kötetlen csevegésen kívül az emoji komolytalanná teszi a szöveget.",
        ["Töröld az emojit; ha jelentést hordozott, írd le szóval."],
        "Töröld vagy írd le szóval: {r}.",
        mintak=[EMOJI],
    ),
    Szabaly(
        "egyhangu-ritmus", "info",
        "Egyforma hosszú mondatok egy bekezdésben",
        "Váltogasd a rövid és a hosszabb mondatokat.",
        "Törd meg az egyhangú mondatritmust",
        "Ha egy bekezdés minden mondata nagyjából ugyanolyan hosszú, a szöveg gépiesen kopog.",
        ["Olvasd fel a bekezdést hangosan.",
         "Vonj össze két rövidebb mondatot, vagy vágj ketté egy hosszút.",
         "A legfontosabb állítás kapjon rövid, önálló mondatot."],
        "Ebben a bekezdésben változtass a mondatok hosszán; így kezdődik: „{r}”.",
        kulon="ritmus",
    ),
    Szabaly(
        "hosszu-mondat", "info",
        "Nagyon hosszú mondat (%d szó fölött)" % HOSSZU_MONDAT_SZO,
        "Bontsd két-három mondatra.",
        "Bontsd fel a túl hosszú mondatokat",
        "Negyven szó fölött az olvasó a mondat végére elfelejti az elejét.",
        ["Számold meg, hány önálló állítás van a mondatban.",
         "Minden állítás kapjon saját mondatot; a kötőszó („mivel”, „amely”, „és”) helyén vágj.",
         "A két-három rövidebb mondat hossza váltakozzon."],
        "Bontsd két-három mondatra: „{r}”.",
        kulon="hosszu",
    ),
    Szabaly(
        "idezojel", "info",
        "Nem magyar idézőjel",
        "Magyar szövegben „így” idézünk, a belső idézet »ilyen«.",
        "Javítsd magyarra az idézőjeleket",
        "Magyar szövegben az idézőjel alul nyit és felül zár.",
        ["Cseréld a nyitó jelet „-re, a zárót ”-re.", "Idézeten belüli idézethez »ilyen« jelet használj."],
        "Cseréld magyar idézőjelre: {r}.",
        mintak=[r'"[^"\n]{1,300}"|“[^”\n]{1,300}”'],
    ),
]

# ===========================================================================
# English rules
# ===========================================================================
EN = [
    Szabaly(
        "filler", "figyelem",
        "Filler lead-in",
        "Delete the lead-in and start with the point.",
        "Cut filler lead-ins",
        "The phrase announces that something matters instead of saying it.",
        ["Delete the phrase up to and including 'that'.",
         "Start the sentence with what followed it.",
         "If the sentence now feels weak, strengthen the content, not the wrapper."],
        "Delete the lead-in and start with the point: '{r}'.",
        mintak=[r"\bit\s+is\s+(?:important|worth|crucial|essential|interesting|notable)\s+(?:to\s+)?(?:note|noting|mention|mentioning|remember|recognize|recognise|emphasize|emphasise|highlight|point\s+out|understand|acknowledge)\b(?:\s+that)?",
                r"\bit\s+(?:should|must|can|could)\s+be\s+(?:noted|mentioned|emphasized|emphasised|said|argued|observed)\s+that\b",
                r"\bit\s+goes\s+without\s+saying\b", r"\bneedless\s+to\s+say\b",
                r"\bas\s+(?:previously|already)\s+(?:mentioned|noted|stated|discussed)\b",
                r"\bat\s+the\s+end\s+of\s+the\s+day\b", r"\bwhen\s+it\s+comes\s+to\b",
                r"\bin\s+today'?s\s+(?:fast-paced|digital|modern|ever-changing|rapidly\s+evolving|competitive)?\s*(?:world|age|era|landscape|society)\b",
                r"\bin\s+the\s+(?:realm|world|context|field|domain)\s+of\b", r"\bat\s+its\s+core\b",
                r"\bthe\s+fact\s+of\s+the\s+matter\b", r"\bwith\s+that\s+(?:being\s+)?said\b",
                r"\bit\s+is\s+(?:clear|evident|obvious|apparent)\s+that\b", r"\bone\s+(?:could|might|may)\s+(?:argue|say)\s+that\b"],
    ),
    Szabaly(
        "wordy", "figyelem",
        "Wordy connective or verb phrase",
        "Use the short form: 'in order to' → 'to'; 'due to the fact that' → 'because'.",
        "Shorten wordy connectives",
        "Several words stand where one would do, and the sentence slows down.",
        ["Swap: 'in order to' → 'to'; 'due to the fact that' → 'because'; 'in the event that' → 'if'; 'is able to' → 'can'; 'a number of' → 'several'; 'utilize' → 'use'.",
         "Reread: the meaning must not change."],
        "Use the short form: '{r}'.",
        mintak=[r"\bin\s+order\s+to\b", r"\bdue\s+to\s+the\s+fact\s+that\b", r"\bin\s+the\s+event\s+that\b",
                r"\b(?:is|are|was|were)\s+able\s+to\b", r"\bha(?:s|ve|d)\s+the\s+(?:ability|capacity|potential)\s+to\b",
                r"\bfor\s+the\s+purpose\s+of\b", r"\bwith\s+(?:regard|respect)\s+to\b", r"\bin\s+terms\s+of\b",
                r"\bprior\s+to\b", r"\bsubsequent\s+to\b", r"\ba\s+(?:wide|broad|diverse)\s+(?:range|variety|array)\s+of\b",
                r"\ba\s+(?:large\s+)?number\s+of\b", r"\butili[sz]\w+", r"\bdespite\s+the\s+fact\s+that\b",
                r"\bin\s+spite\s+of\s+the\s+fact\s+that\b", r"\bat\s+this\s+point\s+in\s+time\b",
                r"\bon\s+a\s+(?:daily|regular|weekly)\s+basis\b", r"\bin\s+close\s+proximity\s+to\b",
                r"\bthe\s+majority\s+of\b", r"\bin\s+light\s+of\s+the\s+fact\s+that\b"],
    ),
    Szabaly(
        "inflated", "figyelem",
        "Inflated significance",
        "Say why it matters, or drop the claim.",
        "Deflate claims of significance",
        "When everything is pivotal, the reader cannot tell what actually is.",
        ["Ask the sentence: why does this matter, and to whom?",
         "If there is an answer, write that instead. If not, delete the phrase."],
        "State the concrete reason it matters, or delete: '{r}'.",
        mintak=[r"\bplay(?:s|ed|ing)?\s+an?\s+(?:key|crucial|pivotal|vital|significant|central|critical|important|essential|major|fundamental|integral)\s+role\b",
                r"\b(?:is|are|was|were|stands?\s+as|serves?\s+as)\s+a\s+testament\s+to\b", r"\ba\s+testament\s+to\b",
                r"\bpivotal\b", r"\bparamount\b", r"\bindispensable\b", r"\bgame[-\s]chang\w+",
                r"\bmarks?\s+an?\s+(?:significant|pivotal|important|major|key|turning)\s+\w+",
                r"\b(?:of|with)\s+(?:utmost|paramount|critical|vital)\s+importance\b",
                r"\bcannot\s+be\s+overstated\b", r"\bprofound(?:ly)?\s+(?:impact|effect|influence|change|implications?|shift)\w*",
                r"\b(?:watershed|landmark|milestone)\s+\w+", r"\bparadigm\s+shift\b",
                r"\b(?:underscore|highlight|emphasi[sz]e)s?\s+the\s+(?:importance|significance|need)\b",
                r"\bleav(?:es|ing)\s+an?\s+(?:lasting|indelible)\s+(?:mark|impact|legacy|impression)\b"],
    ),
    Szabaly(
        "promo", "figyelem",
        "Promotional adjective",
        "In neutral prose, replace with a fact or delete.",
        "Replace promotional adjectives with facts",
        "Advertising language makes a neutral claim less credible.",
        ["Say what makes the thing different: a number, an example, a comparison.",
         "If you cannot, delete the adjective."],
        "Replace with a concrete property, or delete: '{r}'.",
        mintak=[r"\bworld[-\s]class\b", r"\bstate[-\s]of[-\s]the[-\s]art\b", r"\bcutting[-\s]edge\b", r"\bunparalleled\b",
                r"\bunprecedented\b", r"\brevolutionary\b", r"\bgroundbreaking\b", r"\bbest[-\s]in[-\s]class\b",
                r"\bbreathtaking\b", r"\bstunning\b", r"\bnestled\b", r"\bboasts?\b", r"\bseamless(?:ly)?\b",
                r"\binnovative\b", r"\bremarkable\b", r"\bexceptional\b", r"\bunmatched\b", r"\bnext[-\s]generation\b",
                r"\bvibrant\b", r"\brenowned\b", r"\bmust[-\s](?:have|see|read|visit)\b", r"\brich\s+(?:cultural\s+)?(?:heritage|history|tapestry|tradition)\b"],
    ),
    Szabaly(
        "buzzword", "info",
        "Overused, vague word",
        "Say concretely what you mean.",
        "Replace buzzwords with specifics",
        "'Robust', 'holistic', 'landscape' fit anything, so they describe nothing in particular.",
        ["Ask: robust against what? comprehensive in which respect?",
         "Write the answer in place of the word, or cut the word.",
         "A term of art in your field can stay."],
        "Say what this means here, in concrete terms: '{r}'.",
        mintak=[r"\bdelv(?:e|es|ed|ing)\b", r"\btapestry\b", r"\bmultifaceted\b", r"\bintricate\w*", r"\bintricac\w+",
                r"\bholistic(?:ally)?\b", r"\brobust(?:ly|ness)?\b", r"\bleverag(?:e|es|ed|ing)\b", r"\bharness(?:es|ed|ing)?\b",
                r"\bfoster(?:s|ed|ing)?\b", r"\bgarner(?:s|ed|ing)?\b", r"\bbolster(?:s|ed|ing)?\b", r"\bshowcas(?:e|es|ed|ing)\b",
                r"\bunderscor(?:e|es|ed|ing)\b", r"\bembark(?:s|ed|ing)?\b", r"\belevat(?:e|es|ed|ing)\b",
                r"\bnavigat(?:e|es|ed|ing)\s+(?:the\s+)?(?:complex\w*|challeng\w+|landscape|intricac\w+|nuances)\b",
                r"\b(?:the\s+)?(?:\w+\s+)?landscape\s+of\b", r"\b(?:ever|rapidly|constantly)[-\s](?:evolving|changing|shifting)\b",
                r"\btransformative\b", r"\bsynerg\w+", r"\becosystem\b", r"\bempower(?:s|ed|ing|ment)?\b",
                r"\bunlock(?:s|ed|ing)?\s+(?:the\s+)?(?:potential|power|value|opportunit\w+)\b", r"\bstreamlin(?:e|es|ed|ing)\b",
                r"\bcomprehensive\s+(?:overview|understanding|approach|solution|guide|analysis|framework)\b",
                r"\bnuanced\s+(?:understanding|approach|picture|view)\b", r"\bkey\s+(?:takeaways?|insights?)\b",
                r"\bshed(?:s|ding)?\s+light\s+on\b", r"\bdeep\s+dive\b", r"\bdouble[-\s]edged\s+sword\b",
                r"\bcrucial(?:ly)?\b", r"\bvital\b", r"\benhanc(?:e|es|ed|ing)\b", r"\bfacilitat(?:e|es|ed|ing)\b",
                r"\bmeticulous(?:ly)?\b", r"\bcommendable\b", r"\binterplay\b", r"\bunderpin(?:s|ned|ning)?\b",
                r"\bmyriad\b", r"\bplethora\b", r"\brealm\b", r"\bbeacon\b", r"\bcornerstone\b"],
    ),
    Szabaly(
        "copula-avoidance", "info",
        "Avoiding plain 'is' or 'has'",
        "Often 'is' or 'has' is enough: 'serves as a tool' → 'is a tool'.",
        "Use plain 'is' and 'has'",
        "'Serves as', 'stands as', 'boasts' dress up what 'is' or 'has' says directly.",
        ["Swap: 'serves as / functions as / stands as' → 'is'; 'features / boasts / offers' → 'has'.",
         "Keep the longer verb only where it adds meaning."],
        "Try plain 'is' or 'has': '{r}'.",
        mintak=[r"\b(?:serv(?:e|es|ed|ing)|stand(?:s|ing)?|stood|function(?:s|ed|ing)?|act(?:s|ed|ing)?)\s+as\s+(?:an?|the)\b",
                r"\brepresents?\s+an?\s+(?:significant|major|key|important|new|unique|fundamental)\b",
                r"\bconstitutes?\s+an?\b"],
    ),
    Szabaly(
        "ing-tail", "figyelem",
        "Trailing '-ing' clause that adds a vague comment",
        "End the sentence at the fact; put the consequence in its own sentence, with evidence.",
        "Cut trailing '-ing' commentary",
        "The tacked-on participle ('…, highlighting the importance of…') asserts significance without showing it.",
        ["End the sentence before the comma.",
         "If the consequence is real, give it its own sentence and say how you know.",
         "If it is only commentary, delete it."],
        "End the sentence before the participle and state any real consequence separately: '{r}'.",
        mintak=[r",\s+(?:thereby\s+|thus\s+|further\s+|ultimately\s+)?(?:highlighting|underscoring|emphasizing|emphasising|reflecting|showcasing|ensuring|fostering|demonstrating|illustrating|signaling|signalling|symbolizing|symbolising|cementing|solidifying|reinforcing|underlining|marking|paving\s+the\s+way|contributing\s+to|shaping|enabling|allowing|making\s+it)\b[^.!?\n]{0,60}"],
    ),
    Szabaly(
        "vague-attribution", "figyelem",
        "Vague attribution",
        "Name the source, or drop the claim.",
        "Name your sources",
        "An unnamed authority cannot be checked, so it is not evidence.",
        ["Find the study, author or dataset you had in mind.",
         "Cite it by name and year.",
         "If there is none, delete the claim or mark it as your own view."],
        "Give the exact source, or drop the claim: '{r}'.",
        mintak=[r"\b(?:experts|critics|scholars|researchers|observers|analysts|many|some|commentators)\s+(?:say|argue|believe|suggest|contend|note|claim|agree|have\s+(?:argued|noted|suggested|pointed\s+out))\b",
                r"\b(?:studies|research|evidence|reports|surveys|data)\s+(?:show|shows|suggest|suggests|indicate|indicates|ha(?:s|ve)\s+shown|ha(?:s|ve)\s+found|demonstrate|demonstrates)\b",
                r"\bit\s+is\s+(?:widely|generally|commonly|often|well)\s+(?:believed|accepted|regarded|recognized|recognised|known|acknowledged|argued|assumed|understood)\b",
                r"\bindustry\s+(?:reports|experts|leaders|insiders)\b", r"\bis\s+(?:widely|often|commonly)\s+(?:regarded|considered|seen|viewed)\s+as\b"],
    ),
    Szabaly(
        "generic-conclusion", "figyelem",
        "Generic conclusion",
        "Delete it, or replace it with a specific claim.",
        "Rewrite or delete generic conclusions",
        "Upbeat generalities would fit the end of any text, so they say nothing about this one.",
        ["Delete the sentence and see whether anything is missing.",
         "If you need a close, be specific: what follows, what remains open."],
        "Delete, or replace with a specific claim: '{r}'.",
        mintak=[r"\bthe\s+future\s+(?:looks|is|remains|seems)\s+(?:bright|promising|exciting)\b", r"\bonly\s+time\s+will\s+tell\b",
                r"\bexciting\s+times\s+(?:lie\s+)?ahead\b", r"\bpav(?:e|es|ed|ing)\s+the\s+way\s+for\b",
                r"\bopen(?:s|ed|ing)?\s+(?:up\s+)?(?:new\s+)?(?:avenues|possibilities|doors|horizons|opportunities)\b",
                r"\bcontinues?\s+to\s+(?:evolve|grow|thrive|shape|inspire)\b", r"\bdespite\s+(?:these|its|the|such|their)\s+challenges\b",
                r"\ba\s+(?:step|leap)\s+(?:forward|in\s+the\s+right\s+direction)\b", r"\bremains\s+to\s+be\s+seen\b",
                r"\bpoised\s+to\b", r"\bthe\s+possibilities\s+are\s+endless\b", r"\bjourney\s+(?:toward|towards|of)\b"],
    ),
    Szabaly(
        "summary-opener", "info",
        "Summary or signpost opener",
        "Let the content signal the conclusion; the announcement can usually go.",
        "Drop summary and signpost openers",
        "'In conclusion', 'Overall' announce a wrap-up but assert nothing themselves.",
        ["Delete the opener and check the sentence still stands.",
         "If the paragraph only repeats earlier points, consider cutting it."],
        "Start the sentence with its content: '{r}'.",
        mintak=[ME + r"(?:In\s+conclusion|In\s+summary|To\s+sum(?:marize|marise)?(?:\s+up)?|To\s+conclude|Overall|Ultimately|All\s+in\s+all|In\s+essence|In\s+short|Taken\s+together|In\s+a\s+nutshell|At\s+the\s+end\s+of\s+the\s+day),",
                r"\blet'?s\s+(?:dive\s+in|delve|explore|take\s+a\s+(?:closer\s+)?look|unpack|break\s+(?:it|this)\s+down)\b",
                r"\b(?:this|the\s+following)\s+(?:section|article|essay|paper|guide|post)\s+(?:will\s+)?(?:explore|delve|examine|discuss|dive)\w*"],
    ),
    Szabaly(
        "knowledge-cutoff", "figyelem",
        "Disclaimer about the writer's own knowledge",
        "Delete it; the claim stands without it.",
        "Delete knowledge disclaimers",
        "The disclaimer adds no information and undercuts the claim.",
        ["Delete the phrase.", "If the date of the data matters, give the date or the source."],
        "Delete the disclaimer: '{r}'.",
        mintak=[r"\bas\s+of\s+my\s+(?:last|latest|most\s+recent)\s+(?:knowledge\s+)?(?:update|cutoff|training)\b",
                r"\bbased\s+on\s+(?:the\s+)?(?:available|current|limited)\s+(?:information|data|knowledge)\b",
                r"\bto\s+the\s+best\s+of\s+my\s+knowledge\b", r"\bi\s+(?:do\s+not|don'?t)\s+have\s+access\s+to\s+real[-\s]time\b",
                r"\bas\s+an\s+AI\b", r"\bas\s+a\s+(?:large\s+)?language\s+model\b",
                r"\bwhile\s+(?:specific\s+)?details\s+are\s+(?:limited|scarce|not\s+(?:widely\s+)?available)\b"],
    ),
    Szabaly(
        "chatbot-residue", "figyelem",
        "Leftover chatbot phrasing",
        "Delete: it framed a reply and does not belong in the text.",
        "Delete leftover chatbot phrasing",
        "These sentences frame a chat reply; in finished prose they show the text was not read through.",
        ["Delete the opening and closing courtesy sentences.", "Check the first and last lines of the text: they hide there."],
        "Delete the sentence left over from a chat reply: '{r}'.",
        mintak=[r"\bi\s+hope\s+this\s+(?:helps|is\s+helpful|clarifies|answers)\b", r"\blet\s+me\s+know\s+if\b",
                r"\bfeel\s+free\s+to\b", r"\b(?:great|good|excellent|fantastic|interesting)\s+(?:question|point|observation)\s*!",
                r"\byou(?:'re|\s+are)\s+absolutely\s+right\b", ME + r"(?:Certainly|Absolutely|Of\s+course|Sure)\s*[!,]",
                ME + r"Here(?:'s|\s+is|\s+are)\s+(?:an?|the|some|your)\b", r"\bwould\s+you\s+like\s+me\s+to\b",
                r"\bhappy\s+to\s+help\b", r"\bI\s+apologi[sz]e\s+for\s+(?:the|any)\s+confusion\b"],
    ),
    Szabaly(
        "nominalisation", "figyelem",
        "Nominalisation with an empty verb",
        "Use the verb hidden in the noun: 'conduct an analysis of' → 'analyse'.",
        "Turn nominalisations back into verbs",
        "'Make a decision', 'conduct an analysis' take three words to say what one verb says.",
        ["Find the verb hidden in the noun ('analysis' → 'analyse').",
         "Rewrite with that verb and drop the empty verb.",
         "Name who does the action."],
        "Use the verb hidden in the noun: '{r}'.",
        mintak=[r"\b(?:make|makes|made|making|conduct|conducts|conducted|conducting|perform|performs|performed|performing|carry|carries|carried|carrying\s+out|undertake|undertakes|undertook|undertaking|provide|provides|provided|providing|give|gives|gave|giving|reach|reaches|reached|have|has|had)\s+(?:out\s+)?(?:an?|the)\s+(?:\w+\s+)?(?:\w+(?:tion|sion|ment|ysis|ance|ence|al))\s+(?:of|to|for|on|about)\b",
                r"\bis\s+(?:indicative|reflective|suggestive|supportive|representative)\s+of\b",
                r"\b(?:has|have|had)\s+an?\s+(?:impact|effect|influence)\s+on\b", r"\bcome\s+to\s+the\s+conclusion\b",
                r"\btake\s+into\s+consideration\b", r"\bmake\s+use\s+of\b", r"\bgive\s+rise\s+to\b"],
    ),
    Szabaly(
        "rhetorical-fragment", "figyelem",
        "Self-answered rhetorical question",
        "State the point directly.",
        "State the point instead of asking and answering",
        "'The result? …' is a marketing cadence; in prose it reads as a tic.",
        ["Merge question and answer into one statement: 'The result is …'."],
        "Merge the question and its answer into one statement: '{r}'.",
        mintak=[r"\b(?:The|And\s+the|But\s+the)\s+(?:result|answer|catch|problem|solution|kicker|best\s+part|bottom\s+line|takeaway|upshot|reason)\?",
                r"\bWhy\s+does\s+(?:this|it|that)\s+matter\?", r"\bSound\s+familiar\?", r"\bSo,?\s+what\s+does\s+this\s+mean\?"],
    ),
    Szabaly(
        "hedging", "info",
        "Stacked hedging",
        "One hedge is enough; if you know, say it plainly.",
        "Thin out the hedges",
        "After several stacked hedges no claim is left.",
        ["Decide how sure you are.", "Keep one hedge ('probably'), delete the rest.",
         "If there is a reason for the uncertainty, name it."],
        "Keep a single hedge, or state it plainly: '{r}'.",
        mintak=[r"\b(?:could|may|might)\s+(?:potentially|possibly|perhaps|conceivably)\b", r"\bit\s+(?:could|might|may)\s+be\s+argued\s+that\b",
                r"\bto\s+(?:some|a\s+certain|a\s+large)\s+(?:extent|degree)\b", r"\bgenerally\s+speaking\b",
                r"\b(?:seems|appears)\s+to\s+(?:suggest|indicate|imply)\b", r"\b(?:somewhat|arguably|seemingly)\b",
                r"\btends?\s+to\s+(?:suggest|be\s+somewhat)\b", r"\bmay\s+or\s+may\s+not\b", r"\bin\s+some\s+(?:ways|cases|respects|sense)\b"],
    ),
    Szabaly(
        "not-only-but", "info",
        "'Not only… but also' for emphasis",
        "Often 'and' is enough.",
        "Simplify 'not only… but also'",
        "Used for emphasis it wears thin; the two items usually just add up.",
        ["If the items are equal, join them with 'and'.", "Keep it only where the second item is a real surprise after the first."],
        "Try joining the two items with 'and': '{r}'.",
        mintak=[r"\bnot\s+(?:only|just|merely|simply)\b[^.!?\n]{0,160}?\bbut\b(?:\s+also)?",
                r"\b(?:is|are|was|were)(?:n'?t|\s+not)\s+(?:just|merely|simply|only)\s+(?:about\s+)?[^.!?\n]{0,80}?[;,—–-]\s*(?:it|they|this|that)(?:'s|'re|\s+is|\s+are|\s+was|\s+were)\b",
                r"\b(?:more|much\s+more)\s+than\s+(?:just|merely|simply)\b"],
    ),
    Szabaly(
        "false-range", "info",
        "'From X to Y' suggesting completeness",
        "List what is actually covered.",
        "Check 'from X to Y' constructions",
        "The range promises completeness but usually names two things.",
        ["If it is a real range (time, quantity, place), keep it.", "If it only sounds sweeping, name the two or three concrete items."],
        "If this is not a real range, name the concrete items: '{r}'.",
        mintak=[r"\bfrom\s+(?:the\s+)?\w+(?:\s+\w+){0,2}\s+to\s+(?:the\s+)?\w+(?:\s+\w+){0,2},\s+(?:\w+\s+){0,3}(?:everything|all|every|each|covers?|spans?|ranges?)\b",
                r"\b(?:everything|anything|all)\s+from\s+\w+(?:\s+\w+){0,3}\s+to\s+\w+"],
    ),
    Szabaly(
        "not-but-density", "info",
        "Several 'not X, but Y' contrasts in one paragraph",
        "Keep one; write the rest as direct statements.",
        "Thin out 'not X, but Y' contrasts",
        "If you keep introducing claims by denial, the reader first learns what you are not saying.",
        ["Keep at most one per paragraph, where the denied part heads off a real misreading.",
         "For the rest, state Y directly.", "If X matters too, give it its own sentence."],
        "In this paragraph, write most contrasts as direct statements; the first is: '{r}'.",
        mintak=[r"\b(?:not|n't)\b[^.!?\n]{0,160}?[,;]\s*but\b(?!\s+also)", r"\brather\s+than\b", r"\b(?:instead|as\s+opposed)\s+(?:of|to)\b"],
        suruseg=(3, "b"),
    ),
    Szabaly(
        "passive-density", "info",
        "Many passive constructions in one paragraph",
        "Name who acts: 'it was found that' → 'we found that'.",
        "Name the actor in passive constructions",
        "A run of passives hides who claims, measures and concludes.",
        ["Go through the passives in the paragraph.", "Where you are the actor, write 'I' or 'we'.",
         "Where the actor is unknown or irrelevant, the passive can stay."],
        "In this paragraph, rewrite some passives with a named actor; the first is: '{r}'.",
        mintak=[r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w{3,}(?:ed|wn|en|ght|de|ld|nt)\b"], suruseg=(4, "b"),
        kivetel=r"\b(?:is|are|was|were|be|been|being)\s+(?:between|seven|eleven|ten|sudden|different|important|evident|consistent|present|absent|open|often|even|then|when|dependent|independent|sufficient|significant|relevant|apparent|frequent|recent|silent|limited\s+to|based|needed|interested|concerned|related|associated)\b",
    ),
    Szabaly(
        "of-noun-density", "info",
        "Many abstract '-tion of' noun phrases in one sentence",
        "Turn some back into verbs.",
        "Unpack stacked abstract nouns",
        "When nouns carry all the action ('the implementation of the evaluation of…'), nothing happens in the sentence.",
        ["Mark the abstract nouns followed by 'of'.", "Rewrite the two most important with verbs and a named actor.",
         "Split the sentence if it gets too long."],
        "In this sentence, rewrite at least one abstract noun as a verb; the first is: '{r}'.",
        mintak=[r"\b\w+(?:tion|sion|ment|ance|ence|ity|ness|ism)s?\s+of\b"], suruseg=(3, "m"),
    ),
    Szabaly(
        "transition-density", "info",
        "Many sentences opening with a transition word in one paragraph",
        "Let the content show the link; most of these can go.",
        "Thin out sentence-opening transitions",
        "A run of 'Moreover', 'Furthermore', 'Additionally' flattens an argument into a list.",
        ["Delete the opener and check the link is still clear.",
         "Where there is real contrast or consequence, keep it marked, preferably mid-sentence."],
        "In this paragraph, drop most sentence-opening transitions; the first is: '{r}'.",
        mintak=[ME + r"(?:Moreover|Furthermore|Additionally|In\s+addition|Notably|Importantly|Crucially|Interestingly|Consequently|Indeed|Thus|Hence|Therefore|That\s+said|Similarly|Likewise|As\s+a\s+result|On\s+the\s+other\s+hand|By\s+contrast|Nevertheless|Nonetheless),?\s"],
        suruseg=(2, "b"),
    ),
    Szabaly(
        "intensifier-density", "info",
        "Many intensifiers in one paragraph",
        "Delete them; a precise word needs no booster.",
        "Cut intensifiers",
        "'Very', 'truly', 'highly' signal that the word they modify was not strong enough.",
        ["Delete the intensifier.", "If the sentence now feels weak, choose a more exact word."],
        "In this paragraph, delete most intensifiers; the first is: '{r}'.",
        mintak=[r"\b(?:very|really|truly|incredibly|extremely|highly|deeply|significantly|particularly|especially|remarkably|fundamentally|greatly|profoundly|vastly|immensely|undoubtedly|certainly|clearly|simply|essentially|inherently)\s+\w+"],
        suruseg=(3, "b"),
    ),
    Szabaly(
        "triad-density", "info",
        "Several three-item lists in one paragraph",
        "Check that all three items are needed.",
        "Review three-item lists",
        "Mechanical prose lists in threes for rhythm even when one or two items matter.",
        ["For each list ask: do all three items mean different things?",
         "Merge near-synonyms and cut the weakest.", "Where there really are three things, keep the list."],
        "In this paragraph, check that all three items are needed; the first list is: '{r}'.",
        mintak=[r"\b\w{4,},\s+(?:\w+\s+)?\w{4,},?\s+(?:and|or)\s+(?:\w+\s+)?\w{4,}\b"], suruseg=(2, "b"), kivetel=NEVSOR,
    ),
    Szabaly(
        "dash-density", "info",
        "Many em dashes in one paragraph",
        "A comma, colon or new sentence usually reads better.",
        "Thin out em dashes",
        "Frequent dashes make prose choppy and are a familiar mark of machine-written text.",
        ["Keep at most one dashed aside per paragraph.", "Rewrite the rest with commas, a colon, or separate sentences."],
        "In this paragraph, replace most dashes with other punctuation; the first is: '{r}'.",
        mintak=[r"\w+\s?—\s?\w+|\w+\s–\s\w+"], suruseg=(2, "b"),
    ),
    Szabaly(
        "bold-density", "info",
        "Much bold emphasis in one paragraph",
        "Emphasise only what truly needs it.",
        "Thin out bold emphasis",
        "If everything is emphasised, nothing is.",
        ["Keep one or two bolded terms per paragraph at most."],
        "In this paragraph, keep less bold; the first is: '{r}'.",
        mintak=[r"\*\*[^*\n]+\*\*"], suruseg=(4, "b"),
    ),
    Szabaly(
        "label-bullets", "info",
        "Run of 'Label:' bullet points",
        "In prose a sentence says more: 'Performance improves.'",
        "Turn 'Label:' bullets into sentences",
        "A run of bold-labelled bullets reads like a slide and hides how the points connect.",
        ["If the points are connected, write them as a paragraph.", "If you need a list, drop the label and start with a full sentence."],
        "Rewrite this list as prose or as unlabelled sentences; the first item is: '{r}'.",
        mintak=[CIMKE], suruseg=(3, "b"),
    ),
    Szabaly(
        "emoji", "info",
        "Emoji or decorative symbol",
        "Delete unless the text is explicitly informal.",
        "Delete decorative emoji",
        "Outside casual chat, emoji make the text look unserious.",
        ["Delete the emoji; if it carried meaning, say it in words."],
        "Delete, or say it in words: {r}.",
        mintak=[EMOJI],
    ),
    Szabaly(
        "uniform-rhythm", "info",
        "Sentences of nearly identical length in one paragraph",
        "Vary short and longer sentences.",
        "Break up uniform sentence rhythm",
        "When every sentence in a paragraph is about the same length, the prose drones.",
        ["Read the paragraph aloud.", "Merge two shorter sentences or split a long one.",
         "Give the most important claim a short sentence of its own."],
        "In this paragraph, vary the sentence lengths; it begins: '{r}'.",
        kulon="ritmus",
    ),
    Szabaly(
        "long-sentence", "info",
        "Very long sentence (over %d words)" % HOSSZU_MONDAT_SZO,
        "Split it into two or three sentences.",
        "Split overlong sentences",
        "Past forty words the reader has forgotten the start by the time they reach the end.",
        ["Count the separate claims in the sentence.", "Give each its own sentence; cut at the conjunction.",
         "Vary the length of the resulting sentences."],
        "Split into two or three sentences: '{r}'.",
        kulon="hosszu",
    ),
]

NYELVEK = {"hu": HU, "en": EN}
SZABALYTAR = {ny: {s.az: s for s in lista} for ny, lista in NYELVEK.items()}
# Visszafelé kompatibilis, nyelvfüggetlen nézetek.
SZABALY_LEIRASOK = {}
UTMUTATO = {}
for _ny, _lista in NYELVEK.items():
    for _s in _lista:
        SZABALY_LEIRASOK.setdefault(_s.az, (_s.szint, _s.leiras, _s.javaslat))
        UTMUTATO.setdefault(_s.az, (_s.cim, _s.miert, _s.lepesek, _s.sablon))

SZOVEGEK = {
    "hu": {
        "szint": {"figyelem": "figyelem", "info": "info"},
        "db_bek": "%d db a bekezdésben", "db_mondat": "%d db a mondatban", "szo": "%d szó", "szotol": "%d–%d szó", "db": "%d db",
        "sor": "%d. sor", "bekezdes": "%d. bekezdés",
        "osszeg": "%s: %d találat, %d szó (%.1f / ezer szó)",
        "idezet": ("„", "”"),
        "u_cim": "# Javítási útmutató: %s",
        "u_nincs": "A program nem talált megjelölendő fordulatot (%d szó).",
        "u_osszeg": "A szövegben %d megjelölt hely van %d szóra (%.1f / ezer szó), %d féle teendővel.",
        "u_megj": "Az útmutató utasításokat ad, a szöveget nem írja át. Minden jelölés kérdés: ha egy fordulat a műfajhoz tartozik vagy szándékos, maradhat.",
        "u_1": "## 1. Teendők fontossági sorrendben",
        "u_sor": "%d hely · %s · szabály: `%s`",
        "u_szint": {"figyelem": "javítandó", "info": "mérlegelendő"},
        "u_miert": "**Miért gond:** %s", "u_igy": "**Így javítsd:**", "u_hol": "**Hol:**",
        "u_2": "## 2. Végighaladás a szövegen",
        "u_2b": "A fenti teendők a szöveg sorrendjében, helyenként:",
        "u_3": "## 3. Ellenőrzés a javítás után",
        "u_3l": ["Olvasd fel hangosan az átírt bekezdéseket: ahol megakadsz, ott még dolgozni kell.",
                 "Nézd meg, hogy a tartalom nem változott-e: minden tény, szám és hivatkozás megvan.",
                 "Futtasd újra a programot, és vesd össze a találatok számát."],
    },
    "en": {
        "szint": {"figyelem": "fix", "info": "consider"},
        "db_bek": "%d in the paragraph", "db_mondat": "%d in the sentence", "szo": "%d words", "szotol": "%d–%d words", "db": "%d",
        "sor": "line %d", "bekezdes": "paragraph %d",
        "osszeg": "%s: %d findings, %d words (%.1f per 1,000 words)",
        "idezet": ("'", "'"),
        "u_cim": "# Revision guide: %s",
        "u_nincs": "No phrasing was flagged (%d words).",
        "u_osszeg": "The text has %d flagged places in %d words (%.1f per 1,000 words), under %d kinds of task.",
        "u_megj": "This guide gives instructions; it does not rewrite the text. Every flag is a question: if a phrase belongs to the genre or is deliberate, it can stay.",
        "u_1": "## 1. Tasks in order of priority",
        "u_sor": "%d places · %s · rule: `%s`",
        "u_szint": {"figyelem": "fix", "info": "consider"},
        "u_miert": "**Why it is a problem:** %s", "u_igy": "**How to fix it:**", "u_hol": "**Where:**",
        "u_2": "## 2. Walk-through in text order",
        "u_2b": "The same tasks place by place, in the order of the text:",
        "u_3": "## 3. Checks after revising",
        "u_3l": ["Read the revised paragraphs aloud: where you stumble, there is more to do.",
                 "Check that the content is unchanged: every fact, number and citation is still there.",
                 "Run the program again and compare the number of findings."],
    },
}

SZO_RE = re.compile(r"\w+(?:[-'’]\w+)*", re.UNICODE)
MONDAT_RE = re.compile(r"[^.!?…\n]+(?:[.!?…]+|$)", re.UNICODE)
BEKEZDES_RE = re.compile(r"(?:[^\n]|\n(?!\s*\n))+", re.UNICODE)
KODBLOKK_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
HU_BETUK = set("áéíóöőúüűÁÉÍÓÖŐÚÜŰ")
HU_SZAVAK = re.compile(r"\b(?:és|hogy|nem|egy|az|is|van|volt|vagy|mint|csak|már|még|ezt|azt)\b", re.IGNORECASE)
EN_SZAVAK = re.compile(r"\b(?:the|and|of|to|is|in|that|it|was|for|with|as|are|this|be)\b", re.IGNORECASE)


def nyelv_felismer(szoveg):
    """„hu” vagy „en” a gyakori szavak és az ékezetes betűk alapján."""
    hu = len(HU_SZAVAK.findall(szoveg)) + sum(1 for c in szoveg if c in HU_BETUK) / 4.0
    en = len(EN_SZAVAK.findall(szoveg))
    return "en" if en > hu else "hu"


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


def _nevsor(reszlet):
    """Igaz, ha a felsorolás minden hosszabb tagja nagybetűs (például szerzőhármas)."""
    tagok = [s for s in re.split(r"[,\s]+", reszlet) if len(s) > 3]
    return bool(tagok) and all(s[:1].isupper() for s in tagok)


def _egyezesek(szabaly, szoveg):
    """A szabály összes, egymást nem átfedő egyezése a szövegben, pozíció szerint."""
    talalt = []
    for minta in szabaly.mintak:
        for m in minta.finditer(szoveg):
            if not m.group(0).strip():
                continue
            if szabaly.kivetel is NEVSOR:
                pass
            elif szabaly.kivetel is not None and szabaly.kivetel.search(m.group(0)):
                continue
            talalt.append((m.start(), m.end()))
    talalt.sort()
    szurt, veg = [], -1
    for k, v in talalt:
        if k >= veg:
            szurt.append((k, v))
            veg = v
    return szurt


def ellenoriz(szoveg, kihagy=(), nyelv="hu"):
    """Visszaadja a találatok listáját (szótárak), a szövegbeli sorrendben."""
    if nyelv == "auto":
        nyelv = nyelv_felismer(szoveg)
    kihagy = set(kihagy)
    sz = SZOVEGEK[nyelv]
    tiszta = _kod_kitakarasa(szoveg)
    sorkezdetek = [0] + [m.end() for m in re.finditer(r"\n", tiszta)]
    bekezdesek = [(m.start(), m.group(0)) for m in BEKEZDES_RE.finditer(tiszta)]
    mondatok = []
    for m in MONDAT_RE.finditer(tiszta):
        resz = m.group(0)
        if resz.strip():
            mondatok.append((m.start() + len(resz) - len(resz.lstrip()), resz.strip()))
    talalatok = []

    def felvesz(szabaly, kezdet, veg, megjegyzes=None):
        sor, oszlop = _sor_oszlop(sorkezdetek, kezdet)
        leiras = szabaly.leiras if megjegyzes is None else "%s (%s)" % (szabaly.leiras, megjegyzes)
        talalatok.append({
            "szabaly": szabaly.az, "szint": szabaly.szint, "sor": sor, "oszlop": oszlop,
            "reszlet": _rovid(tiszta[kezdet:veg]), "leiras": leiras, "javaslat": szabaly.javaslat,
        })

    for szabaly in NYELVEK[nyelv]:
        if szabaly.az in kihagy:
            continue
        if szabaly.kulon == "hosszu":
            for kezdet, resz in mondatok:
                szavak = len(SZO_RE.findall(resz))
                if szavak > HOSSZU_MONDAT_SZO:
                    felvesz(szabaly, kezdet, kezdet + len(resz), sz["szo"] % szavak)
        elif szabaly.kulon == "lanc":
            for kezdet, resz in mondatok:
                db = len(_egyezesek(szabaly, resz))
                if db >= LANC_DB:
                    felvesz(szabaly, kezdet, kezdet + len(resz), sz["db"] % db)
        elif szabaly.kulon == "ritmus":
            for kezdet, bek in bekezdesek:
                hosszak = [len(SZO_RE.findall(m.group(0))) for m in MONDAT_RE.finditer(bek) if m.group(0).strip()]
                hosszak = [h for h in hosszak if h > 0]
                if len(hosszak) >= 4 and min(hosszak) >= 10 and max(hosszak) - min(hosszak) <= 5:
                    eleje = MONDAT_RE.search(bek)
                    felvesz(szabaly, kezdet + eleje.start(), kezdet + eleje.end(),
                            sz["szotol"] % (min(hosszak), max(hosszak)))
        elif szabaly.suruseg:
            kuszob, hatokor = szabaly.suruseg
            egysegek = bekezdesek if hatokor == "b" else mondatok
            cimke = sz["db_bek"] if hatokor == "b" else sz["db_mondat"]
            for kezdet, resz in egysegek:
                egy = _egyezesek(szabaly, resz)
                if szabaly.kivetel is NEVSOR:
                    egy = [(k, v) for k, v in egy if not _nevsor(resz[k:v])]
                if len(egy) >= kuszob:
                    felvesz(szabaly, kezdet + egy[0][0], kezdet + egy[0][1], cimke % len(egy))
        else:
            for k, v in _egyezesek(szabaly, tiszta):
                felvesz(szabaly, k, v)

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
def _hely(talalat, docx, nyelv):
    """Ember számára olvasható helymegjelölés."""
    sz = SZOVEGEK[nyelv]
    if docx:  # a kinyert szövegben a bekezdéseket üres sor választja el
        return sz["bekezdes"] % ((talalat["sor"] + 1) // 2)
    return sz["sor"] % talalat["sor"]


def utmutato(fajl, talalatok, osszes, docx=False, nyelv="hu"):
    """Markdown javítási útmutató: mit, miért és hol kell javítani, utasításokként."""
    sz = SZOVEGEK[nyelv]
    tar = SZABALYTAR[nyelv]
    nyit, zar = sz["idezet"]
    ki = [sz["u_cim"] % fajl, ""]
    if not talalatok:
        ki += [sz["u_nincs"] % osszes["szavak"], ""]
        return "\n".join(ki)

    csoportok = {}
    for t in talalatok:
        csoportok.setdefault(t["szabaly"], []).append(t)
    # Előbb a „figyelem” szintű teendők, azon belül a gyakoribb elöl.
    sorrend = sorted(csoportok, key=lambda az: (-SZINTEK[tar[az].szint], -len(csoportok[az]), az))

    ki += [sz["u_osszeg"] % (osszes["talalatok"], osszes["szavak"], osszes["ezer_szora"], len(sorrend)), "",
           sz["u_megj"], "", sz["u_1"], ""]
    for i, az in enumerate(sorrend, 1):
        s = tar[az]
        helyek = csoportok[az]
        ki += ["### %d. %s" % (i, s.cim), "",
               sz["u_sor"] % (len(helyek), sz["u_szint"][s.szint], az), "",
               sz["u_miert"] % s.miert, "", sz["u_igy"], ""]
        ki += ["%d. %s" % (n, lepes) for n, lepes in enumerate(s.lepesek, 1)]
        ki += ["", sz["u_hol"], ""]
        ki += ["- %s: %s%s%s" % (_hely(t, docx, nyelv), nyit, t["reszlet"], zar) for t in helyek]
        ki.append("")

    ki += [sz["u_2"], "", sz["u_2b"], ""]
    elozo = None
    for t in talalatok:
        hely = _hely(t, docx, nyelv)
        if hely != elozo:
            if elozo is not None:
                ki.append("")
            ki += ["**%s**" % (hely[:1].upper() + hely[1:]), ""]
            elozo = hely
        ki.append("- %s" % tar[t["szabaly"]].sablon.format(r=t["reszlet"]))
    ki += ["", sz["u_3"], ""]
    ki += ["%d. %s" % (n, s) for n, s in enumerate(sz["u_3l"], 1)]
    ki.append("")
    return "\n".join(ki)


# ---------------------------------------------------------------------------
# Parancssor
# ---------------------------------------------------------------------------
def _szabalylista(nyelvek):
    sorok = []
    for ny in nyelvek:
        sorok.append("[%s]" % ny)
        for s in sorted(NYELVEK[ny], key=lambda s: (-SZINTEK[s.szint], s.az)):
            sorok.append("%-22s %-9s %s\n%33s%s" % (s.az, SZOVEGEK[ny]["szint"][s.szint], s.leiras, "", s.javaslat))
    return "\n".join(sorok)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="stiluslint",
        description="Gépies, hivataloskodó fordulatok megjelölése magyar és angol szövegben. "
        "Csak jelöl és javasol, a szöveget nem írja át. / "
        "Flags mechanical phrasing in Hungarian and English prose; never rewrites.",
    )
    p.add_argument("fajlok", nargs="*", metavar="FÁJL", help=".txt, .md vagy .docx; „-” a szabványos bemenet")
    p.add_argument("--nyelv", "--lang", choices=["auto", "hu", "en"], default="auto",
                   help="a szöveg nyelve (alapértelmezés: auto, fájlonként felismeri)")
    p.add_argument("--json", action="store_true", help="gépi feldolgozásra alkalmas JSON-kimenet")
    p.add_argument("--utmutato", "--guide", action="store_true",
                   help="javítási útmutató Markdown formában: mit, miért és hol javíts")
    p.add_argument("--kimenet", "--output", metavar="FÁJL", help="a kimenet ebbe a fájlba kerül a képernyő helyett")
    p.add_argument("--kihagy", "--skip", default="", metavar="SZABÁLY[,SZABÁLY]", help="kihagyandó szabályok azonosítói")
    p.add_argument("--szint", "--level", choices=["info", "figyelem", "consider", "fix"], default="info",
                   help="legalább ilyen szintű találatok (info/consider vagy figyelem/fix; alapértelmezés: info)")
    p.add_argument("--szabalyok", "--rules", action="store_true", help="a szabályok listája")
    p.add_argument("--szigoru", "--strict", action="store_true", help="1-es kilépési kód, ha van találat")
    p.add_argument("--version", action="version", version="stiluslint " + __version__)
    args = p.parse_args(argv)

    if args.szabalyok:
        print(_szabalylista(["hu", "en"] if args.nyelv == "auto" else [args.nyelv]))
        return 0
    if not args.fajlok:
        p.error("adj meg legalább egy fájlt (vagy „-” a szabványos bemenethez)")
    if args.json and args.utmutato:
        p.error("a --json és az --utmutato nem használható együtt")

    kihagy = [s.strip() for s in args.kihagy.split(",") if s.strip()]
    ismeretlen = [s for s in kihagy if s not in SZABALY_LEIRASOK]
    if ismeretlen:
        p.error("ismeretlen szabály: " + ", ".join(ismeretlen))

    kuszob = SZINTEK[{"consider": "info", "fix": "figyelem"}.get(args.szint, args.szint)]
    eredmenyek = []
    volt_talalat = False
    for utvonal in args.fajlok:
        try:
            szoveg = beolvas(utvonal)
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, ElementTree.ParseError) as hiba:
            print("stiluslint: %s: nem olvasható (%s)" % (utvonal, hiba), file=sys.stderr)
            return 2
        nyelv = nyelv_felismer(szoveg) if args.nyelv == "auto" else args.nyelv
        talalatok = [t for t in ellenoriz(szoveg, kihagy, nyelv) if SZINTEK[t["szint"]] >= kuszob]
        volt_talalat = volt_talalat or bool(talalatok)
        eredmenyek.append({"fajl": utvonal, "nyelv": nyelv, "talalatok": talalatok,
                           "osszesites": osszesites(szoveg, talalatok)})

    sorok = []
    if args.json:
        sorok.append(json.dumps(eredmenyek, ensure_ascii=False, indent=2))
    elif args.utmutato:
        for e in eredmenyek:
            docx = e["fajl"].lower().endswith(".docx")
            sorok.append(utmutato(e["fajl"], e["talalatok"], e["osszesites"], docx, e["nyelv"]))
    else:
        for e in eredmenyek:
            sz = SZOVEGEK[e["nyelv"]]
            nyit, zar = sz["idezet"]
            for t in e["talalatok"]:
                sorok.append("%s:%d:%d  %s  [%s]" % (e["fajl"], t["sor"], t["oszlop"], sz["szint"][t["szint"]], t["szabaly"]))
                sorok.append("    %s: %s%s%s" % (t["leiras"], nyit, t["reszlet"], zar))
                sorok.append("    → %s" % t["javaslat"])
            o = e["osszesites"]
            sorok.append(sz["osszeg"] % (e["fajl"], o["talalatok"], o["szavak"], o["ezer_szora"]))
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
