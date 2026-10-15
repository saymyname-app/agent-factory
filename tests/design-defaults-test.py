#!/usr/bin/env python3
"""Default design checks on a disposable React/TypeScript repository."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "default-standards/react-typescript"
DESIGN = CODE / "design"


class DesignDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.parent = Path(cls.temp.name)
        cls.base = cls.parent / "base"
        (cls.base / "src/theme").mkdir(parents=True)
        (cls.base / "bin").mkdir()
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(CODE / name, cls.base / name)
        (cls.base / "src/domain").mkdir(exist_ok=True)
        for name in ("add.ts", "add.test.ts"):
            shutil.copyfile(CODE / "src/domain" / name, cls.base / "src/domain" / name)
        shutil.copyfile(DESIGN / "src/theme/tokens.css", cls.base / "src/theme/tokens.css")
        for name in ("check-design-tokens", "check-design-css", "check-design-source.mjs"):
            shutil.copyfile(DESIGN / "bin" / name, cls.base / "bin" / name)
        cls.container = not (shutil.which("node") and shutil.which("npm"))
        install = cls.run_in(cls.base, ["npm", "ci"])
        if install.returncode:
            raise RuntimeError(f"npm ci failed: {install.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_in(cls, directory, command):
        if cls.container:
            relative = directory.relative_to(cls.parent).as_posix()
            command = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                       "-e", "npm_config_cache=/tmp/npm-cache", "-v", f"{cls.parent}:/fixture",
                       "-w", f"/fixture/{relative}", "node:22", *command]
        return subprocess.run(command, cwd=directory, text=True, capture_output=True)

    def setUp(self):
        self.case = self.parent / self.id().rsplit(".", 1)[-1]
        shutil.copytree(self.base, self.case, ignore=shutil.ignore_patterns("node_modules"))
        (self.case / "node_modules").symlink_to("../base/node_modules", target_is_directory=True)

    def check(self, command):
        return self.run_in(self.case, command)

    def test_clean_theme_and_source_pass(self):
        for command in (["python3", "bin/check-design-tokens"], ["python3", "bin/check-design-css"],
                        ["node", "bin/check-design-source.mjs"]):
            result = self.check(command)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_low_contrast_is_refused(self):
        path = self.case / "src/theme/tokens.css"
        path.write_text(path.read_text().replace("--color-text: #1b1b1b", "--color-text: #eeeeee"))
        result = self.check(["python3", "bin/check-design-tokens"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("contraste text/background", result.stderr)

    def test_missing_reduced_motion_is_refused(self):
        path = self.case / "src/theme/tokens.css"
        path.write_text(path.read_text().replace("@media (prefers-reduced-motion: reduce)", "@media screen"))
        result = self.check(["python3", "bin/check-design-tokens"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("réduction des animations", result.stderr)

    def test_new_duration_requires_reduced_motion(self):
        path = self.case / "src/theme/tokens.css"
        path.write_text(path.read_text().replace("--duration-fast: 150ms;", "--duration-fast: 150ms; --duration-extra: 2s;"))
        result = self.check(["python3", "bin/check-design-tokens"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("réduction des animations", result.stderr)

    def test_missing_dark_role_is_refused(self):
        path = self.case / "src/theme/tokens.css"
        path.write_text(path.read_text().replace("  --color-surface: #1d2933;", ""))
        result = self.check(["python3", "bin/check-design-tokens"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("rôles", result.stderr)

    def test_surface_contrast_is_checked(self):
        path = self.case / "src/theme/tokens.css"
        path.write_text(path.read_text().replace("--color-surface: #f5f7fb", "--color-surface: #2b2b2b"))
        result = self.check(["python3", "bin/check-design-tokens"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("contraste text/surface", result.stderr)

    def test_css_literal_is_refused(self):
        (self.case / "src/card.css").write_text(".card { color: red; margin: 8px; }\n")
        result = self.check(["python3", "bin/check-design-css"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("src/card.css:1", result.stderr)

    def test_css_named_svg_and_border_colors_are_refused(self):
        (self.case / "src/card.css").write_text(".icon { fill: tomato; stroke: rebeccapurple; border: solid red; }\n")
        result = self.check(["python3", "bin/check-design-css"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("src/card.css:1", result.stderr)

    def test_css_color_mixed_with_theme_variable_is_refused(self):
        (self.case / "src/card.css").write_text(".card { background: linear-gradient(red, var(--color-accent)); }\n")
        result = self.check(["python3", "bin/check-design-css"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("src/card.css:1", result.stderr)

    def test_jsx_text_is_refused(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <p>{"Hello"}</p>; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("texte affiché en dur", result.stderr)

    def test_conditional_jsx_text_is_refused(self):
        (self.case / "src/Bad.tsx").write_text("export function Bad({ ready }: { ready: boolean }) { return <p>{ready ? 'Prêt' : 'Attente'}</p>; }\n")
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("texte affiché en dur", result.stderr)

    def test_component_label_is_refused(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <Button label="Enregistrer" />; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("texte label en dur", result.stderr)

    def test_jsx_expression_attribute_text_is_refused(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <><Button label={"Enregistrer"} /><img alt={"Logo"} /></>; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("texte label en dur", result.stderr)
        self.assertIn("texte alt en dur", result.stderr)

    def test_string_call_in_jsx_is_refused(self):
        (self.case / "src/Bad.tsx").write_text("export function Bad() { return <p>{String('Bonjour')}</p>; }\n")
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("texte affiché en dur", result.stderr)

    def test_button_and_input_need_accessible_names(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <><button /><input /></>; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("bouton sans nom accessible", result.stderr)
        self.assertIn("champ sans libellé accessible", result.stderr)

    def test_html_label_associated_with_input_passes(self):
        (self.case / "src/Good.tsx").write_text("export function Good() { return <><label htmlFor=\"email\">{t('email')}</label><input id=\"email\" /></>; }\n")
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertEqual(0, result.returncode, result.stderr)

    def test_button_with_nested_content_passes(self):
        (self.case / "src/Good.tsx").write_text("export function Good() { return <button><span>{t('save')}</span></button>; }\n")
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertEqual(0, result.returncode, result.stderr)

    def test_missing_alt_is_refused(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <img src="/logo.svg" />; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("image sans alt", result.stderr)

    def test_inline_style_is_refused(self):
        (self.case / "src/Bad.tsx").write_text('export function Bad() { return <div style={{ margin: 8 }} />; }\n')
        result = self.check(["node", "bin/check-design-source.mjs"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("style inline interdit", result.stderr)


if __name__ == "__main__":
    unittest.main()
