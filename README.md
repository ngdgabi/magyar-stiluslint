# magyar-stiluslint

Parancssori stílusellenőrző magyar és angol szöveghez. Megjelöli a gépies, hivataloskodó fordulatokat, mindegyikhez javaslatot ad, és kérésre javítási útmutatót ír.

*English summary: a command-line style checker for Hungarian and English prose. It flags mechanical, bureaucratic phrasing, gives advice for each finding, and can write a revision guide. It never rewrites the text, it is not an AI detector, and it is not built to evade one. See [English](#english) below.*

**Mit nem csinál:**

- Nem írja át a szöveget. A döntés és az átírás az íróé.
- Nem állapítja meg, hogy a szöveget ember vagy gép írta. A megjelölt fordulatok emberi szövegben is gyakoriak (hivatali, pályázati, tudományos nyelv).
- Nem MI-detektorok kijátszására készült, és nem azokhoz igazodik. Ha egy szöveg mesterséges intelligenciával készült, azt ott, ahol kérik (folyóirat, egyetem, pályázat), a javítás után is jelezni kell.

## Használat

Python 3.8 vagy újabb kell hozzá, más függősége nincs.

```bash
python3 stiluslint.py kezirat.docx
```

```bash
python3 stiluslint.py peldak/minta.txt --szint figyelem
```

```bash
cat jegyzet.md | python3 stiluslint.py - --json
```

Bemenet lehet `.txt`, `.md` és `.docx` fájl. A Markdown-kódrészleteket kihagyja. A `.docx` fájlból csak a törzsszöveget olvassa (lábjegyzetet, fejlécet nem).

A nyelvet fájlonként magától felismeri (magyar vagy angol); a `--nyelv hu` vagy `--nyelv en` kapcsolóval rögzíthető. A kimenet a szöveg nyelvén készül.

Példakimenet:

```
peldak/minta.txt:3:327  figyelem  [kerul-asra]
    Körülíró szerkezet („-ásra/-ésre kerül”): „megállapításra került”
    → Nevezd meg, ki mit csinál: „megállapításra került” → „megállapítottuk”.
```

### Javítási útmutató

Az `--utmutato` kapcsolóval a program a találatok listája helyett Markdown útmutatót ír: mit, miért és hol érdemes javítani, utasítások formájában. A szöveget ekkor sem írja át.

```bash
python3 stiluslint.py kezirat.docx --utmutato --kimenet utmutato.md
```

Az útmutató három részből áll:

1. **Teendők fontossági sorrendben:** minden teendőhöz leírja, miért gond, lépésekben megadja a javítás módját, és felsorolja az érintett helyeket. Elöl a `figyelem` szintű, gyakoribb teendők állnak.
2. **Végighaladás a szövegen:** ugyanezek helyenként, a szöveg sorrendjében, egy-egy utasítással.
3. **Ellenőrzés a javítás után.**

A hely `.txt` és `.md` fájlnál a sor száma, `.docx` fájlnál a nem üres bekezdés sorszáma. Minták: [peldak/minta_utmutato.md](peldak/minta_utmutato.md), [peldak/sample_en_guide.md](peldak/sample_en_guide.md).

### Kapcsolók

Minden kapcsolónak van angol neve is.

| Kapcsoló | Angol név | Mire való |
|---|---|---|
| `--nyelv auto\|hu\|en` | `--lang` | A szöveg nyelve (alapértelmezés: `auto`) |
| `--szint info\|figyelem` | `--level consider\|fix` | Csak a legalább ilyen szintű találatok |
| `--kihagy a,b` | `--skip` | A felsorolt szabályok kihagyása |
| `--utmutato` | `--guide` | Javítási útmutató Markdown formában |
| `--kimenet FÁJL` | `--output` | A kimenet fájlba kerül a képernyő helyett |
| `--json` | | JSON-kimenet más programnak |
| `--szigoru` | `--strict` | 1-es kilépési kód, ha van találat (például CI-ben) |
| `--szabalyok` | `--rules` | A szabályok listája leírással |

## Magyar szabályok (39)

Két szint van: a `figyelem` szintű találat többnyire javítandó, az `info` szintű mérlegelendő.

**Kifejezések (`figyelem`)**

| Azonosító | Mit jelöl |
|---|---|
| `kerul-asra` | „megállapításra került”, „sor kerül” |
| `funkcioige` | „elvégzi az ellenőrzést”, „lehetőséget biztosít”, „döntést hoz” |
| `valo-torteno` | „a megközelítéshez való kapcsolás”, „-val történő” |
| `toltelek` | „Fontos megjegyezni, hogy”, „összességében elmondható” |
| `terjengos-kotoszo` | „annak érdekében, hogy”, „abban az esetben, ha” |
| `felnagyitas` | „kulcsfontosságú”, „döntő jelentőségű”, „mérföldkő” |
| `reklamiz` | „úttörő”, „egyedülálló”, „innovatív” |
| `nevmas-tulzas` | „Mi úgy gondoljuk”, „ez egy olyan” |
| `sablonos-lezaras` | „új lehetőségeket nyit”, „a kihívások ellenére” |
| `homalyos-hivatkozas` | „kutatások bizonyítják”, „szakértők szerint” |
| `tudasvagas` | „jelenlegi tudásom szerint” |
| `hizelges` | „Remek kérdés!” |
| `chatbot-nyom` | „Remélem, ez segít”, „Íme a…” |
| `udvariaskodas` | „hálás lennék, amennyiben”, „szíveskedjen” |
| `birtokos-halmozas` | „a minőségének javításának lehetőségei” |
| `amely-lanc` | három vagy több „amely…” egy mondatban |

**Kifejezések (`info`)**

| Azonosító | Mit jelöl |
|---|---|
| `hivataloskodas` | „az adott”, „amennyiben”, „tekintetében”, „E szempont”, „jelen tanulmány” |
| `divatszo` | „holisztikus”, „átfogó megoldás”, „szerves része” |
| `letige-kerules` | „eszközként szolgál”, „szerepet játszik”, „rendelkezik” |
| `kivan-ige` | „kívánok hozzájárulni”, „be kívánja mutatni” |
| `altal-szerkezet` | „a személy által vállalt” |
| `osszegzo-nyito` | „Összességében”, „Végezetül” a mondat elején |
| `ovatoskodas` | „elképzelhető, hogy esetleg”, „bizonyos mértékben” |
| `nemcsak-hanem` | „nemcsak… hanem… is” |
| `skala` | „a tervezéstől a megvalósításig” |
| `emoji` | emoji vagy díszítő szimbólum |
| `idezojel` | "egyenes" vagy “angol” idézőjel a magyar „…” helyett |

**Sűrűség és szerkezet (`info`)**

| Azonosító | Mikor jelez |
|---|---|
| `fonevesites-suruseg` | négy vagy több „-ás/-és” főnév egy mondatban |
| `igenev-suruseg` | három vagy több „-va/-ve” igenév egy mondatban |
| `nem-hanem-suruseg` | két vagy több „nem X, hanem Y” egy bekezdésben |
| `hato-heto-suruseg` | három vagy több „-ható/-hető” alak egy bekezdésben |
| `atvezeto-suruseg` | két vagy több „Emellett/Továbbá/Ugyanakkor” mondatkezdet egy bekezdésben |
| `tehat-suruseg` | két vagy több „tehát” egy bekezdésben |
| `harmas-felsorolas` | két vagy több hármas felsorolás egy bekezdésben (névsorokat nem számít) |
| `gondolatjel-suruseg` | három vagy több gondolatjel egy bekezdésben |
| `felkover-suruseg` | négy vagy több félkövér kiemelés egy bekezdésben |
| `cimke-felsorolas` | három vagy több „**Címke:**” kezdetű listaelem |
| `egyhangu-ritmus` | legalább négy, közel egyforma hosszú mondat egy bekezdésben |
| `hosszu-mondat` | 40 szónál hosszabb mondat |

## Korlátok

A szabályok reguláris kifejezések, nyelvtani elemzés nincs mögöttük. Ebből következik:

- **Téves riasztás:** a végződésre illesztő szabályok (`kerul-asra`, `funkcioige`, `birtokos-halmozas`, `fonevesites-suruseg`, `igenev-suruseg`, angolul `passive-density`) olyan szót is megfoghatnak, amely csak véletlenül végződik ugyanúgy. A `fonevesites-suruseg` a szöveg tárgyát jelölő főneveket is számolja („megközelítés”, „elköteleződés”).
- **Kimaradó találat:** a ragozott, közbeékelt vagy szokatlan szórendű változatokat nem mindig ismeri fel. Az alacsony találatszám nem bizonyítja, hogy a szöveg jó.
- **Regiszter:** tudományos és jogi szövegben az `info` szintű találatok nagy része rendben lévő fordulat. Ilyen szövegnél érdemes a `--szint figyelem` kapcsolóval kezdeni.

A találat ezért kérdés az írónak, és nem hiba.

## English

The same program checks English text. The language is detected per file; force it with `--lang en`.

```bash
python3 stiluslint.py paper.docx --lang en
```

```bash
python3 stiluslint.py peldak/sample_en.txt --guide --output guide.md
```

Findings have two levels: `fix` (usually worth changing) and `consider` (a judgement call). In JSON output the levels appear under their internal names, `figyelem` and `info`.

**English rules (29)**

| Rule | Level | Flags |
|---|---|---|
| `filler` | fix | 'It is important to note that', 'when it comes to' |
| `wordy` | fix | 'in order to', 'due to the fact that', 'utilize' |
| `inflated` | fix | 'plays a crucial role', 'a testament to', 'pivotal' |
| `promo` | fix | 'groundbreaking', 'state-of-the-art', 'seamless' |
| `ing-tail` | fix | '…, highlighting the importance of…' |
| `vague-attribution` | fix | 'studies show', 'experts argue', 'it is widely believed' |
| `generic-conclusion` | fix | 'continues to evolve', 'paving the way for' |
| `knowledge-cutoff` | fix | 'as of my last update', 'as an AI' |
| `chatbot-residue` | fix | 'I hope this helps', 'Certainly!' |
| `nominalisation` | fix | 'conduct an analysis of', 'make a decision to' |
| `rhetorical-fragment` | fix | 'The result? …' |
| `buzzword` | consider | 'delve', 'robust', 'leverage', 'landscape of' |
| `copula-avoidance` | consider | 'serves as a', 'stands as the' |
| `summary-opener` | consider | 'In conclusion,', 'Overall,', 'Let's dive in' |
| `hedging` | consider | 'could potentially', 'to some extent' |
| `not-only-but` | consider | 'not only… but also', 'more than just' |
| `false-range` | consider | 'everything from X to Y' |
| `emoji` | consider | emoji or decorative symbols |
| `not-but-density` | consider | three or more 'not X, but Y' / 'rather than' in a paragraph |
| `passive-density` | consider | four or more passives in a paragraph |
| `of-noun-density` | consider | three or more '-tion of' phrases in a sentence |
| `transition-density` | consider | two or more 'Moreover/Furthermore/…' openers in a paragraph |
| `intensifier-density` | consider | three or more intensifiers in a paragraph |
| `triad-density` | consider | two or more three-item lists in a paragraph (name lists excluded) |
| `dash-density` | consider | two or more em dashes in a paragraph |
| `bold-density` | consider | four or more bold spans in a paragraph |
| `label-bullets` | consider | three or more '**Label:**' bullets |
| `uniform-rhythm` | consider | four or more sentences of near-identical length in a paragraph |
| `long-sentence` | consider | sentences over 40 words |

**Limits.** The rules are regular expressions with no parsing behind them. They produce false alarms (any word ending like a participle can count as a passive) and they miss inflected or reordered variants. A low count does not show the text is good. In academic and legal writing many `consider` findings are legitimate; start with `--level fix`.

## Tesztek

```bash
python3 -m unittest discover -s tests
```

## Források

A szabályok kiindulópontja a [hungarian-humanizer](https://github.com/ngdgabi/bencium-marketplace/tree/main/hungarian-humanizer) mintalistája (bencium.io), amely a [Hakku/finnish-humanizer](https://github.com/Hakku/finnish-humanizer) (MIT) magyar adaptációja. Az angol szabályok a szerkesztői gyakorlatban ismert jegyekre épülnek. A minták megfogalmazása és a kód saját.

## Licenc

MIT, lásd [LICENSE](LICENSE).
