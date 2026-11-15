# -*- coding: utf-8 -*-
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import stiluslint  # noqa: E402


def szabalyok(szoveg, **kw):
    return [t["szabaly"] for t in stiluslint.ellenoriz(szoveg, **kw)]


class KifejezesSzabalyok(unittest.TestCase):
    def test_kerul_asra(self):
        self.assertIn("kerul-asra", szabalyok("A vizsgálat során megállapításra került a hiba."))
        self.assertIn("kerul-asra", szabalyok("A terv jövőre kerül megvalósításra."))

    def test_funkcioige(self):
        self.assertIn("funkcioige", szabalyok("A rendszer elvégzi az adatok ellenőrzését."))
        self.assertIn("funkcioige", szabalyok("Lehetőséget biztosít a kezelésre."))

    def test_toltelek(self):
        self.assertIn("toltelek", szabalyok("Fontos megjegyezni, hogy a piac változik."))
        self.assertIn("toltelek", szabalyok("Összességében elmondható, hogy bevált."))

    def test_felnagyitas_es_reklamiz(self):
        t = szabalyok("Kulcsfontosságú és úttörő megoldás.")
        self.assertIn("felnagyitas", t)
        self.assertIn("reklamiz", t)

    def test_homalyos_hivatkozas(self):
        self.assertIn("homalyos-hivatkozas", szabalyok("Kutatások bizonyítják, hogy működik."))

    def test_nemcsak_hanem(self):
        self.assertIn("nemcsak-hanem", szabalyok("Nemcsak gyors, hanem olcsó is."))

    def test_birtokos_halmozas(self):
        self.assertIn(
            "birtokos-halmozas",
            szabalyok("A termék minőségének javításának lehetőségei adottak."),
        )

    def test_tiszta_szoveg_nem_jelez(self):
        self.assertEqual(szabalyok("A csapat tegnap átnézte a kódot. Két hibát talált."), [])


class SzerkezetiSzabalyok(unittest.TestCase):
    def test_hosszu_mondat(self):
        mondat = " ".join(["szó"] * 45) + "."
        self.assertIn("hosszu-mondat", szabalyok(mondat))
        self.assertNotIn("hosszu-mondat", szabalyok(" ".join(["szó"] * 20) + "."))

    def test_amely_lanc(self):
        s = "A csapat, amely a projektért felel, amely támogatást kapott, amelyre pályázni kellett, végzett."
        self.assertIn("amely-lanc", szabalyok(s))
        self.assertNotIn("amely-lanc", szabalyok("A csapat, amely felel érte, végzett."))

    def test_nem_hanem_suruseg_bekezdesenkent(self):
        egy = "Nem a hitet vizsgálom, hanem a vállalást."
        self.assertNotIn("nem-hanem-suruseg", szabalyok(egy))
        ketto = egy + " Nem a tagságot nézem, hanem a viszonyt."
        self.assertIn("nem-hanem-suruseg", szabalyok(ketto))
        kulon = egy + "\n\n" + "Nem a tagságot nézem, hanem a viszonyt."
        self.assertNotIn("nem-hanem-suruseg", szabalyok(kulon))

    def test_hato_heto_suruseg(self):
        s = "Megállapítható a hiba. Az ok értelmezhető. A hatás kimutatható."
        self.assertIn("hato-heto-suruseg", szabalyok(s))

    def test_harmas_felsorolas_neveket_kihagy(self):
        koznevek = "Gyors, olcsó és megbízható. Javítja, fejleszti és optimalizálja."
        self.assertIn("harmas-felsorolas", szabalyok(koznevek))
        nevek = "Lásd Metz, Kruikemeier és Lecheler munkáját, továbbá Alston, Audi és McKaughan írásait."
        self.assertNotIn("harmas-felsorolas", szabalyok(nevek))

    def test_idezojel(self):
        self.assertIn("idezojel", szabalyok('Azt mondta: "holnap jövök".'))
        self.assertNotIn("idezojel", szabalyok("Azt mondta: „holnap jövök”."))

    def test_kodreszlet_kimarad(self):
        self.assertEqual(szabalyok('Futtasd: `echo "úttörő"` és kész.'), [])
        self.assertEqual(szabalyok('```\nprint("kulcsfontosságú")\n```\n'), [])


class Helyek(unittest.TestCase):
    def test_sor_es_oszlop(self):
        t = stiluslint.ellenoriz("Első sor.\nItt egy úttörő ötlet.")
        self.assertEqual((t[0]["sor"], t[0]["oszlop"]), (2, 9))

    def test_kihagy(self):
        self.assertEqual(szabalyok("Úttörő ötlet.", kihagy=["reklamiz"]), [])

    def test_osszesites(self):
        szoveg = "Úttörő ötlet. Kulcsfontosságú lépés."
        o = stiluslint.osszesites(szoveg, stiluslint.ellenoriz(szoveg))
        self.assertEqual(o["szavak"], 4)
        self.assertEqual(o["talalatok"], 2)
        self.assertEqual(o["ezer_szora"], 500.0)


class Parancssor(unittest.TestCase):
    def _futtat(self, argumentumok):
        ki = io.StringIO()
        with redirect_stdout(ki):
            kod = stiluslint.main(argumentumok)
        return kod, ki.getvalue()

    def test_json_es_szigoru(self):
        with tempfile.TemporaryDirectory() as d:
            ut = os.path.join(d, "a.txt")
            with open(ut, "w", encoding="utf-8") as f:
                f.write("Fontos megjegyezni, hogy ez úttörő.\n")
            kod, ki = self._futtat([ut, "--json", "--szigoru"])
            self.assertEqual(kod, 1)
            adat = json.loads(ki)
            self.assertEqual(adat[0]["osszesites"]["talalatok"], 2)
            kod, _ = self._futtat([ut])
            self.assertEqual(kod, 0)

    def test_szint_szuro(self):
        with tempfile.TemporaryDirectory() as d:
            ut = os.path.join(d, "a.txt")
            with open(ut, "w", encoding="utf-8") as f:
                f.write("Amennyiben esik, maradunk.\n")
            _, ki = self._futtat([ut, "--json", "--szint", "figyelem"])
            self.assertEqual(json.loads(ki)[0]["talalatok"], [])

    def test_docx(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>Első bekezdés.</w:t></w:r></w:p>"
            '<w:p><w:r><w:t xml:space="preserve">Ez egy </w:t></w:r><w:r><w:t>úttörő ötlet.</w:t></w:r></w:p>'
            "</w:body></w:document>"
        )
        with tempfile.TemporaryDirectory() as d:
            ut = os.path.join(d, "a.docx")
            with zipfile.ZipFile(ut, "w") as z:
                z.writestr("word/document.xml", xml)
            self.assertEqual(stiluslint.beolvas(ut), "Első bekezdés.\n\nEz egy úttörő ötlet.")
            _, ki = self._futtat([ut, "--json"])
            self.assertEqual(json.loads(ki)[0]["talalatok"][0]["sor"], 3)


class UjMagyarSzabalyok(unittest.TestCase):
    def test_valo_torteno(self):
        self.assertIn("valo-torteno", szabalyok("A megközelítésekhez való kapcsolás nehéz."))
        self.assertNotIn("valo-torteno", szabalyok("A politikushoz való viszony változott."))

    def test_fonevesites_suruseg(self):
        s = ("Az elsajátítási viszony fogalmi elkülönítésével, belső különbségeinek rendszerezésével "
             "és más megközelítésekhez való kapcsolásával kívánok hozzájárulni a vizsgálathoz.")
        t = szabalyok(s)
        self.assertIn("fonevesites-suruseg", t)
        self.assertIn("kivan-ige", t)
        self.assertNotIn("fonevesites-suruseg", szabalyok("A vallás kérdése más, mint a tudás kérdése és az írás."))

    def test_terjengos_es_letige(self):
        t = szabalyok("Annak érdekében, hogy működjön, a modul eszközként szolgál, és fontos szerepet játszik.")
        self.assertIn("terjengos-kotoszo", t)
        self.assertIn("letige-kerules", t)

    def test_altal_es_nevmas(self):
        self.assertIn("altal-szerkezet", szabalyok("A személy által vállalt viszony tartós."))
        self.assertIn("nevmas-tulzas", szabalyok("Ez egy olyan eszköz, amely gyorsít."))

    def test_hivataloskodo_e_nevmas(self):
        self.assertIn("hivataloskodas", szabalyok("E szempont elkülönítése hasznos."))
        self.assertNotIn("hivataloskodas", szabalyok("Tudod-e, hogy esik?"))

    def test_mondatkezdo_szabalyok(self):
        self.assertIn("osszegzo-nyito", szabalyok("Jó lett. Összességében a terv bevált."))
        s = "Emellett olcsó. Továbbá gyors. A többi rendben."
        self.assertIn("atvezeto-suruseg", szabalyok(s))
        self.assertNotIn("atvezeto-suruseg", szabalyok("Emellett olcsó. A többi rendben."))

    def test_chatbot_es_emoji(self):
        t = szabalyok("Remélem, ez segít! 🚀")
        self.assertIn("chatbot-nyom", t)
        self.assertIn("emoji", t)

    def test_egyhangu_ritmus(self):
        mondat = "Ez a mondat pontosan tizenkét szóból áll, hogy a ritmus egyhangú legyen itt. "
        self.assertIn("egyhangu-ritmus", szabalyok(mondat * 4))
        vegyes = mondat * 3 + "Rövid ez."
        self.assertNotIn("egyhangu-ritmus", szabalyok(vegyes))


class Angol(unittest.TestCase):
    def sz(self, szoveg):
        return [t["szabaly"] for t in stiluslint.ellenoriz(szoveg, nyelv="en")]

    def test_kifejezesek(self):
        esetek = {
            "filler": "It is important to note that the market changed.",
            "wordy": "We did this in order to save time.",
            "inflated": "The method plays a crucial role in the field.",
            "promo": "A groundbreaking platform.",
            "buzzword": "We delve into the topic.",
            "copula-avoidance": "The library serves as a hub.",
            "ing-tail": "Sales rose, highlighting the strength of the brand.",
            "vague-attribution": "Studies show that it works.",
            "generic-conclusion": "The field continues to evolve.",
            "summary-opener": "It works. In conclusion, we are done.",
            "knowledge-cutoff": "As of my last update, prices rose.",
            "chatbot-residue": "I hope this helps!",
            "nominalisation": "They conducted an analysis of the data.",
            "rhetorical-fragment": "The result? Chaos.",
            "hedging": "This could potentially help.",
            "not-only-but": "It is not only fast but also cheap.",
        }
        for az, szoveg in esetek.items():
            self.assertIn(az, self.sz(szoveg), az)

    def test_tiszta_szoveg(self):
        self.assertEqual(self.sz("The team reviewed the code yesterday. They found two bugs."), [])

    def test_surusegek(self):
        self.assertIn("transition-density", self.sz("Moreover, it is cheap. Furthermore, it is fast."))
        self.assertNotIn("transition-density", self.sz("Moreover, it is cheap. It is fast."))
        passziv = "The data were collected. The files were stored. The labels were checked. The results were saved."
        self.assertIn("passive-density", self.sz(passziv))
        self.assertIn("triad-density", self.sz("Fast, cheap, and reliable. Design, build, and maintain."))
        self.assertNotIn("triad-density", self.sz("See Alston, Audi, and McKaughan; also Metz, Kruikemeier, and Lecheler."))
        self.assertIn("long-sentence", self.sz(" ".join(["word"] * 45) + "."))

    def test_nyelvfelismeres(self):
        self.assertEqual(stiluslint.nyelv_felismer("The team reviewed the code and found that it was fine."), "en")
        self.assertEqual(stiluslint.nyelv_felismer("A csapat átnézte a kódot, és nem talált hibát."), "hu")

    def test_angol_utmutato_es_aliasok(self):
        with tempfile.TemporaryDirectory() as d:
            be = os.path.join(d, "a.txt")
            ki = os.path.join(d, "guide.md")
            with open(be, "w", encoding="utf-8") as f:
                f.write("It is important to note that the tool is groundbreaking.\n")
            kepernyo = io.StringIO()
            with redirect_stdout(kepernyo):
                kod = stiluslint.main([be, "--guide", "--output", ki, "--level", "fix", "--strict"])
            self.assertEqual(kod, 1)
            with open(ki, encoding="utf-8") as f:
                u = f.read()
            self.assertIn("# Revision guide:", u)
            self.assertIn("**How to fix it:**", u)
            self.assertIn("- line 1: 'It is important to note that'", u)
            self.assertIn("**Line 1**", u)

    def test_json_nyelv_mezo(self):
        with tempfile.TemporaryDirectory() as d:
            be = os.path.join(d, "a.txt")
            with open(be, "w", encoding="utf-8") as f:
                f.write("The team reviewed the code and it was fine.\n")
            ki = io.StringIO()
            with redirect_stdout(ki):
                stiluslint.main([be, "--json"])
            self.assertEqual(json.loads(ki.getvalue())[0]["nyelv"], "en")


class Szabalytar(unittest.TestCase):
    def test_minden_szabaly_teljes(self):
        for ny, lista in stiluslint.NYELVEK.items():
            azonositok = [s.az for s in lista]
            self.assertEqual(len(azonositok), len(set(azonositok)), ny)
            for s in lista:
                self.assertIn(s.szint, stiluslint.SZINTEK, s.az)
                self.assertTrue(s.leiras and s.javaslat and s.cim and s.miert and s.lepesek, s.az)
                self.assertIn("{r}", s.sablon, s.az)
                self.assertTrue(s.mintak or s.kulon, s.az)


class Utmutato(unittest.TestCase):
    def _utmutato(self, szoveg, fajl="a.txt", docx=False):
        t = stiluslint.ellenoriz(szoveg)
        return stiluslint.utmutato(fajl, t, stiluslint.osszesites(szoveg, t), docx)

    def test_minden_szabalyhoz_van_utmutato(self):
        self.assertEqual(set(stiluslint.UTMUTATO), set(stiluslint.SZABALY_LEIRASOK))
        for az, (cim, miert, lepesek, sablon) in stiluslint.UTMUTATO.items():
            self.assertTrue(cim and miert and lepesek, az)
            self.assertIn("{r}", sablon, az)

    def test_tartalom_es_sorrend(self):
        szoveg = "Amennyiben esik, maradunk.\nA hiba megállapításra került. Ez úttörő és páratlan."
        u = self._utmutato(szoveg)
        self.assertIn("# Javítási útmutató: a.txt", u)
        self.assertIn("**Így javítsd:**", u)
        self.assertIn("- 2. sor: „megállapításra került”", u)
        self.assertIn("Nevezd meg a cselekvőt, és írd át igével: „megállapításra került”.", u)
        # a „figyelem” szintű, gyakoribb teendő előzi meg az „info” szintűt
        self.assertLess(u.index("reklámízű jelzőket"), u.index("körülíró"))
        self.assertLess(u.index("körülíró"), u.index("hivataloskodó fordulatokat"))
        # a végighaladás a szöveg sorrendjét követi
        self.assertLess(u.index("**1. sor**"), u.index("**2. sor**"))

    def test_docx_bekezdesszam(self):
        u = self._utmutato("Első bekezdés.\n\nEz egy úttörő ötlet.", "a.docx", docx=True)
        self.assertIn("- 2. bekezdés: „úttörő”", u)

    def test_nincs_talalat(self):
        u = self._utmutato("A csapat tegnap átnézte a kódot.")
        self.assertIn("nem talált megjelölendő fordulatot", u)
        self.assertNotIn("## 1.", u)

    def test_parancssor_kimenet_fajlba(self):
        with tempfile.TemporaryDirectory() as d:
            be = os.path.join(d, "a.txt")
            ki = os.path.join(d, "utmutato.md")
            with open(be, "w", encoding="utf-8") as f:
                f.write("Fontos megjegyezni, hogy ez úttörő.\n")
            kepernyo = io.StringIO()
            with redirect_stdout(kepernyo):
                kod = stiluslint.main([be, "--utmutato", "--kimenet", ki])
            self.assertEqual(kod, 0)
            self.assertEqual(kepernyo.getvalue(), "")
            with open(ki, encoding="utf-8") as f:
                self.assertIn("## 2. Végighaladás a szövegen", f.read())


if __name__ == "__main__":
    unittest.main()
