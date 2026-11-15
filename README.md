# magyar-stiluslint

Parancssori stílusellenőrző magyar szöveghez. Megjelöli a gépies, hivataloskodó fordulatokat, és mindegyikhez javaslatot ad.

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

Bemenet lehet `.txt`, `.md` és `.docx` fájl. A Markdown-kódrészleteket kihagyja. A `.docx` fájlból csak a törzsszöveget olvassa (lábjegyzetet, fejlécet nem), és a sorszám ilyenkor a kinyert szöveg sorára vonatkozik, nem a Word oldalára.

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

A hely `.txt` és `.md` fájlnál a sor száma, `.docx` fájlnál a nem üres bekezdés sorszáma. Minta: [peldak/minta_utmutato.md](peldak/minta_utmutato.md).

### Kapcsolók

| Kapcsoló | Mire való |
|---|---|
| `--szint info\|figyelem` | Csak a legalább ilyen szintű találatok (alapértelmezés: `info`) |
| `--kihagy a,b` | A felsorolt szabályok kihagyása |
| `--json` | JSON-kimenet más programnak |
| `--utmutato` | Javítási útmutató Markdown formában |
| `--kimenet FÁJL` | A kimenet fájlba kerül a képernyő helyett |
| `--szigoru` | 1-es kilépési kód, ha van találat (például CI-ben) |
| `--szabalyok` | A szabályok listája leírással |

## Szabályok

| Azonosító | Szint | Mit jelöl |
|---|---|---|
| `kerul-asra` | figyelem | „megállapításra került”, „kerül megvalósításra” |
| `funkcioige` | figyelem | „elvégzi az ellenőrzést”, „lehetőséget biztosít” |
| `toltelek` | figyelem | „Fontos megjegyezni, hogy”, „összességében elmondható” |
| `felnagyitas` | figyelem | „kulcsfontosságú”, „döntő jelentőségű” |
| `reklamiz` | figyelem | „úttörő”, „egyedülálló”, „innovatív” |
| `sablonos-lezaras` | figyelem | „új lehetőségeket nyit”, „a kihívások ellenére” |
| `homalyos-hivatkozas` | figyelem | „kutatások bizonyítják”, „szakértők szerint” |
| `tudasvagas` | figyelem | „jelenlegi tudásom szerint” |
| `hizelges` | figyelem | „Remek kérdés!” |
| `birtokos-halmozas` | figyelem | „a minőségének javításának lehetőségei” |
| `amely-lanc` | figyelem | három vagy több „amely…” egy mondatban |
| `hivataloskodas` | info | „az adott”, „amennyiben”, „tekintetében” |
| `ovatoskodas` | info | „elképzelhető, hogy esetleg”, „bizonyos mértékben” |
| `nemcsak-hanem` | info | „nemcsak… hanem… is” |
| `nem-hanem-suruseg` | info | két vagy több „nem X, hanem Y” egy bekezdésben |
| `hato-heto-suruseg` | info | három vagy több „-ható/-hető” alak egy bekezdésben |
| `harmas-felsorolas` | info | két vagy több hármas felsorolás egy bekezdésben |
| `felkover-suruseg` | info | négy vagy több félkövér kiemelés egy bekezdésben |
| `hosszu-mondat` | info | 40 szónál hosszabb mondat |
| `idezojel` | info | "egyenes" vagy “angol” idézőjel a magyar „…” helyett |

## Korlátok

A szabályok reguláris kifejezések, nyelvtani elemzés nincs mögöttük. Ebből következik:

- **Téves riasztás:** a végződésre illesztő szabályok (`kerul-asra`, `funkcioige`, `birtokos-halmozas`, `hato-heto-suruseg`) olyan szót is megfoghatnak, amely csak véletlenül végződik ugyanúgy.
- **Kimaradó találat:** a ragozott, közbeékelt vagy szokatlan szórendű változatokat nem mindig ismeri fel.
- **Regiszter:** tudományos és jogi szövegben az `info` szintű találatok nagy része rendben lévő fordulat. Ilyen szövegnél érdemes a `--szint figyelem` kapcsolóval kezdeni.

A találat ezért kérdés az írónak, és nem hiba.

## Tesztek

```bash
python3 -m unittest discover -s tests
```

## Források

A szabályok kiindulópontja a [hungarian-humanizer](https://github.com/ngdgabi/bencium-marketplace/tree/main/hungarian-humanizer) mintalistája (bencium.io), amely a [Hakku/finnish-humanizer](https://github.com/Hakku/finnish-humanizer) (MIT) magyar adaptációja. A minták megfogalmazása és a kód saját.

## Licenc

MIT, lásd [LICENSE](LICENSE).
