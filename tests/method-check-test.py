#!/usr/bin/env python3
"""D01 T31 (Spec af-wf4w5r §9 and §16, user stories 77 and 78):
bin/method-check on the Factory's own documents and on copies of them.

`table` reads docs/REQUIREMENT_TABLE.md: green when every requirement has a
mechanism and a proof; red, naming the row, when a mechanism is empty, names
no command, or names a command that bin/ does not hold. `register` reads
docs/ADAPTATION_REGISTER.md: green when every deviation of Spec §16 names an
entry that has its reason and the v1.3.1 baseline; red when an entry has no
reason. Both run here on the repository itself, which is what makes a pull
request that breaks either red in CI.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "method-check"
TABLE = Path("docs") / "REQUIREMENT_TABLE.md"
REGISTER = Path("docs") / "ADAPTATION_REGISTER.md"

# The rows of the table of Spec af-wf4w5r §9, first column.
SPEC_REQUIREMENTS = [
    "Ticket démontrable sur le produit",
    "Critères observables et gelés",
    "Rouge avant le code",
    "Tests non affaiblis",
    "Test par interface publique",
    "Le produit marche",
    "Fidélité au prototype",
    "Code conforme à la Spec",
    "Rien de reporté en silence",
    "Assemblé de bout en bout",
    "Méthode de Matt inchangée",
    "Acceptation liée à ce qui a été jugé",
    "Aucun agent ne décide du flux",
]

# The deviations of Spec af-wf4w5r §16, one per sentence, by resolution.
SPEC_DEVIATIONS = {
    ".17": [
        "La formule, et non un humain, déclenche les skills de livraison réservés à l'humain.",
        "Skills distribués par rôle.",
        "Contrôles ajoutés : comparaison au tag, essai de chargement par fournisseur, essai du masquage.",
    ],
    ".8": [
        "Du code avance le graphe, pas un agent orchestrateur.",
        "L'auteur résout les conflits, pas un agent de fusion.",
        "Tickets concurrents décidés à la publication par arêtes et Declared Scope.",
        "Une session neuve juge en fin de Spec à la place de l'humain propriétaire.",
    ],
    ".10": [
        "Ligne de démonstration obligatoire.",
        "Genre de ticket explicite, dont `repair`.",
        "Relecteur de graphe.",
        "Pointeurs posés par la porte.",
        "Contrôle de couverture.",
        "Chemins de périmètre conservés (Matt les interdit dans les tickets).",
        "Vérification mécanique du rouge avant le travail.",
    ],
    ".11": [
        "Prototype Fold fait par l'usine comme première tranche (Matt : repli en session avec humain, avant le découpage).",
        "Ajouts : version figée confirmée, inventaire des états, ancres avec règle de couverture, données par état, contrôle de conformité, référence recopiée dans les tickets.",
    ],
    ".12": [
        "Seams convenus à la planification.",
        "Tests de critère écrits tous d'abord.",
        "Preuve mécanique rouge/vert, gel, amendement borné, k exécutions.",
        "Relecture des tests avant le code.",
        "Preuve mécanique du seam.",
        "Régime propre au prefactoring.",
    ],
    ".9": [
        "Evaluator à la place de la QA humaine.",
        "Lancement du produit par l'auteur et par l'Evaluator.",
        "Tickets de réparation bornés à l'intention approuvée.",
        "Verdict calculé par du code.",
    ],
    ".13": [
        "Revue déclenchée par le flux dans une session distincte.",
        "Revue par ticket en plus de la revue de fin.",
        "Constat bloquant seulement s'il cite sa source.",
        "Réponse « corrigé / contesté » jugée par une seconde session.",
        "Condition d'arrêt.",
        "Troisième vérification sur les tests.",
        "Corrections de fin par tickets `repair`.",
    ],
    ".14": [
        "Sorties structurées.",
        "Handoff obligatoire validé par du code.",
        "Détecteur de report.",
        "Interdiction de déléguer l'écriture.",
        "Borne de reprises.",
        "Arrêts globaux.",
        "Besoins opérateur levés avant le départ.",
    ],
    ".15": [
        "Evidence Record enregistré par outil.",
        "Portes de fin de ticket et de fin de Spec.",
        "Evidence Pack généré par du code.",
        "Borne de 2 tours.",
        "Convoi sans fermeture automatique.",
    ],
    ".16": [
        "Acceptance Session sur le produit lancé.",
        "Owner Finding routé par du code.",
        "Mots de Benjamin enregistrés avec commit et empreinte.",
    ],
    "section 0": [
        "Du code démarre les tickets d'un convoi à la place du Mayor (écart avec le Mayor de Gas City, qui dispatche).",
        "Arrêt sur état inconnu.",
        "Citation obligatoire pour classer « réparé » un constat hors ticket.",
    ],
}

TABLE_HEAD = (
    "# Table\n\n"
    "| Exigence | Mécanisme | Preuve produite |\n"
    "| --- | --- | --- |\n"
)

REGISTER_HEAD = (
    "# Adaptation Register\n\n"
    "## Écarts de la Spec D01 (af-wf4w5r §16) et leurs entrées\n\n"
    "| Résolution | Écart | Entrées |\n"
    "| --- | --- | --- |\n"
)


def entry(number, reason="Une raison.", baseline="mattpocock/skills v1.3.1 : rien."):
    return (
        "\n## AR-%03d — Une adaptation (D01, T99)\n\n"
        "| Champ | Enregistrement |\n"
        "| --- | --- |\n"
        "| Statut | **Adoptée**. |\n"
        "| Baseline | %s |\n"
        "| But | %s |\n"
        "| Adaptation sélectionnée | Un outil. |\n" % (number, baseline, reason)
    )


def run(command, root):
    return subprocess.run(
        [sys.executable, str(CLI), command, "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


class Sandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="af-method-check-")
        self.root = Path(self._tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "bin").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def command(self, name):
        path = self.root / "bin" / name
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)

    def table(self, *rows):
        body = "".join("| %s | %s | %s |\n" % row for row in rows)
        (self.root / TABLE).write_text(TABLE_HEAD + body, encoding="utf-8")

    def register(self, rows, *entries):
        body = "".join("| %s | %s | %s |\n" % row for row in rows)
        (self.root / REGISTER).write_text(
            REGISTER_HEAD + body + "".join(entries), encoding="utf-8"
        )

    def refused(self, result, *named):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        for word in named:
            self.assertIn(word, result.stderr)


class TableOfTheFactory(unittest.TestCase):
    def test_the_table_of_the_factory_is_green(self):
        result = run("table", ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_table_holds_every_row_of_the_spec(self):
        held = [
            cells(line)[0]
            for line in (ROOT / TABLE).read_text(encoding="utf-8").splitlines()
            if line.startswith("|")
        ]
        for requirement in SPEC_REQUIREMENTS:
            self.assertIn(requirement, held)


class TableOnACopy(Sandbox):
    def test_every_requirement_with_mechanism_and_proof_passes(self):
        self.command("porte")
        self.command("garde")
        self.table(
            ("Rouge avant le code", "`./bin/porte red`", "un relevé"),
            ("Le produit marche", "`bin/porte` puis `bin/garde`", "un état"),
        )
        result = run("table", self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_empty_mechanism_is_refused_and_the_row_named(self):
        self.command("porte")
        self.table(
            ("Rouge avant le code", "`bin/porte`", "un relevé"),
            ("Le produit marche", "", "un état"),
        )
        self.refused(run("table", self.root), "Le produit marche")

    def test_a_mechanism_that_names_no_command_is_refused(self):
        self.table(("Le produit marche", "une relecture attentive", "un état"))
        self.refused(run("table", self.root), "Le produit marche")

    def test_a_command_absent_from_the_factory_is_refused_and_named(self):
        self.command("porte")
        self.table(
            ("Rouge avant le code", "`bin/porte`", "un relevé"),
            ("Le produit marche", "`bin/porte` et `bin/renommee`", "un état"),
        )
        result = run("table", self.root)
        self.refused(result, "Le produit marche", "bin/renommee")
        self.assertNotIn("Rouge avant le code", result.stderr)

    def test_an_empty_proof_is_refused_and_the_row_named(self):
        self.command("porte")
        self.table(("Le produit marche", "`bin/porte`", ""))
        self.refused(run("table", self.root), "Le produit marche")

    def test_the_real_table_goes_red_when_a_command_it_cites_is_renamed(self):
        shutil.copy(ROOT / TABLE, self.root / TABLE)
        for path in (ROOT / "bin").iterdir():
            if path.is_file():
                self.command(path.name)
        self.assertEqual(run("table", self.root).returncode, 0)
        (self.root / "bin" / "tdd-step").rename(self.root / "bin" / "tdd-etape")
        self.refused(run("table", self.root), "Rouge avant le code", "bin/tdd-step")

    def test_a_document_without_table_is_refused(self):
        (self.root / TABLE).write_text("# Table\n", encoding="utf-8")
        self.refused(run("table", self.root))

    def test_a_missing_document_is_refused(self):
        self.refused(run("table", self.root))


class RegisterOfTheFactory(unittest.TestCase):
    def test_the_register_of_the_factory_is_green(self):
        result = run("register", ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_deviation_of_the_spec_names_an_entry(self):
        held = set()
        for line in (ROOT / REGISTER).read_text(encoding="utf-8").splitlines():
            row = cells(line) if line.startswith("|") else []
            if len(row) == 3 and "AR-" in row[2]:
                held.add((row[0], row[1]))
        for resolution, deviations in SPEC_DEVIATIONS.items():
            for deviation in deviations:
                self.assertIn((resolution, deviation), held)


class RegisterOnACopy(Sandbox):
    def test_every_deviation_with_a_reasoned_entry_passes(self):
        self.register(
            [(".8", "Du code avance le graphe.", "AR-001"),
             (".9", "Verdict calculé par du code.", "AR-001, AR-002")],
            entry(1),
            entry(2),
        )
        result = run("register", self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_entry_without_reason_is_refused_and_named(self):
        self.register(
            [(".8", "Du code avance le graphe.", "AR-001")],
            entry(1),
            entry(2, reason=""),
        )
        self.refused(run("register", self.root), "AR-002")

    def test_a_deviation_without_entry_is_refused_and_named(self):
        self.register([(".8", "Du code avance le graphe.", "")], entry(1))
        self.refused(run("register", self.root), "Du code avance le graphe.")

    def test_a_deviation_naming_an_absent_entry_is_refused(self):
        self.register([(".8", "Du code avance le graphe.", "AR-007")], entry(1))
        self.refused(run("register", self.root), "Du code avance le graphe.", "AR-007")

    def test_an_entry_of_a_deviation_without_the_baseline_is_refused(self):
        self.register(
            [(".8", "Du code avance le graphe.", "AR-001")],
            entry(1, baseline="Gas City 1.4.1 : un dispatcher."),
        )
        self.refused(run("register", self.root), "AR-001", "v1.3.1")

    def test_a_register_without_the_list_of_deviations_is_refused(self):
        (self.root / REGISTER).write_text(
            "# Adaptation Register\n" + entry(1), encoding="utf-8"
        )
        self.refused(run("register", self.root))

    def test_a_missing_register_is_refused(self):
        self.refused(run("register", self.root))


class Usage(unittest.TestCase):
    def test_an_unknown_command_is_a_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "autre"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
