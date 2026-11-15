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


if __name__ == "__main__":
    unittest.main()
