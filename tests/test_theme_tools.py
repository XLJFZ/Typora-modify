"""Regression tests for dependency validation, generation, and browser sampling."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_computed as audit
import build_themes as builder
from theme_dependencies import check_imports
from playwright.sync_api import sync_playwright


class Dependencies(unittest.TestCase):
    def test_partial_only_allows_night_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'theme.css'
            path.write_text('@import "night/token.css";\n@import "pdf-white.css";', encoding='utf-8')
            missing, skipped = check_imports(path, True)
            self.assertEqual(len(missing), 1)
            self.assertTrue(missing[0].endswith('pdf-white.css'))
            self.assertEqual(len(skipped), 1)
            self.assertEqual(len(check_imports(path)[0]), 2)

    def test_recursive_import_and_comment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'theme.css'
            path.write_text('/* @import "ignored.css"; */ @import url("child.css");', encoding='utf-8')
            (path.parent / 'child.css').write_text('@import "missing.css";', encoding='utf-8')
            self.assertEqual(len(check_imports(path)[0]), 1)


class Generation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.base = self.directory / 'night.css'
        self.source = '''@import url( 'night/sourcemode.dark.css' );
:root { --text-color: #b8bfc6; }
mark { background: #c8c90f; }
'''
        self.source += '\n'.join('.fixture%d {%s}' % (i, old) for i, (old, new) in enumerate(builder.FIXES))
        self.base.write_text(self.source, encoding='utf-8')
        self.previous = builder.BASE, builder.OUT_DIR
        builder.BASE, builder.OUT_DIR = str(self.base), str(self.directory)
        self.addCleanup(self.restore)

    def restore(self):
        builder.BASE, builder.OUT_DIR = self.previous

    def test_import_format_and_all_variants(self):
        for variant in builder.VARIANTS:
            with contextlib.redirect_stdout(io.StringIO()):
                path, content = builder.build(variant)
            self.assertIn('@import "pdf-white.css";', content)
            self.assertIn('color: #0f0f0f;', content)
            self.assertFalse(Path(path).exists(), 'Validation must not write files')

    def test_missing_required_rule_fails_before_write(self):
        self.base.write_text(self.source.replace(builder.FIXES[0][0], ''), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Required replacements'):
            builder.build('standard')
        self.assertFalse((self.directory / 'pure-black.css').exists())

    def test_missing_import_fails(self):
        self.base.write_text(self.source.replace('night/sourcemode.dark.css', 'other.css'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'sourcemode import'):
            builder.build('standard')

    def test_pdf_updated_unless_explicitly_preserved(self):
        output = self.directory / 'output'
        output.mkdir()
        pdf = output / 'pdf-white.css'
        pdf.write_text('custom', encoding='utf-8')
        command = [sys.executable, str(ROOT / 'scripts/build_themes.py'), '-t', str(self.directory), '-o', str(output)]
        subprocess.run(command + ['--keep-pdf-white'], check=True, capture_output=True)
        self.assertEqual(pdf.read_text(encoding='utf-8'), 'custom')
        subprocess.run(command, check=True, capture_output=True)
        self.assertEqual(pdf.read_bytes(), (ROOT / 'themes/pdf-white.css').read_bytes())


class BrowserSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        try:
            channel = os.environ.get('THEME_TEST_BROWSER', 'chromium')
            cls.browser = cls.pw.chromium.launch(channel=None if channel == 'chromium' else channel, headless=True)
        except Exception:
            cls.pw.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def test_all_matches_and_ancestor_alpha(self):
        page = self.browser.new_page()
        try:
            page.set_content('''<body style="background:black"><div style="background:rgb(100,100,100)">
              <p style="color:black;background:rgba(255,255,255,.5)">first</p>
              <p style="color:black">second</p></div></body>''')
            rows = page.evaluate(audit.JS, [('p', 'paragraph')])
            self.assertEqual(len(rows), 2)
            self.assertAlmostEqual(rows[0]['bg'][0], 177.5)
            self.assertEqual(rows[1]['bg'], [100, 100, 100])
            self.assertEqual(rows[0]['parentBg'], [100, 100, 100])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.report('screen', rows), 1)
        finally:
            page.close()

    def test_partial_stylesheet_with_missing_imports_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            css = Path(directory) / 'theme.css'
            css.write_text('@import "night/missing.css"; body { background: black; color: white; } a { color: white; }', encoding='utf-8')
            command = [sys.executable, str(ROOT / 'scripts/audit_computed.py'), '--css', str(css),
                       '--browser', os.environ.get('THEME_TEST_BROWSER', 'chromium'), '--media', 'screen',
                       '--allow-missing-night']
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PARTIAL', result.stdout)
            with self.assertRaisesRegex(ValueError, 'Missing CSS imports'):
                audit.run('screen', css, 'chromium')

    def test_typora_pdf_container_font_in_both_media(self):
        page = self.browser.new_page()
        try:
            page.set_content('<body><div id="write"><h1>标题</h1><p>正文</p><code>code</code></div></body>')
            page.add_style_tag(content=builder.SCREEN_EXTRA + builder.PRINT_SERIF_EXTRA)
            family = lambda selector: page.locator(selector).evaluate('(el) => getComputedStyle(el).fontFamily')
            editor_text, editor_title, editor_code = family('p'), family('h1'), family('code')
            self.assertNotIn('SimSun', editor_text)
            page.locator('body').evaluate("el => el.classList.add('typora-print')")
            for media in ('screen', 'print'):
                page.emulate_media(media=media)
                self.assertTrue(family('p').startswith('SimSun'))
                self.assertEqual(family('h1'), editor_title)
                self.assertEqual(family('code'), editor_code)
        finally:
            page.close()

    def test_missing_element_fails_without_unpack_error(self):
        page = self.browser.new_page()
        try:
            page.set_content('<p>test</p>')
            rows = page.evaluate(audit.JS, [('#missing', 'required')])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.report('screen', rows), 1)
        finally:
            page.close()


if __name__ == '__main__':
    unittest.main()
