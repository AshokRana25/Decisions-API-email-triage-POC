"""Streamlit AppTest exercises widgets without a browser or paid API calls."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

UI_AVAILABLE = importlib.util.find_spec("streamlit") is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(UI_AVAILABLE, "Install requirements.txt for UI tests")
class UITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
        self.assertFalse(app.exception)
        return app

    def test_mock_click_and_change_input_clear_stale_result(self):
        app = self.app()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("technical-review", app.success[0].value)
        app.text_area[0].set_value("No action needed.").run()
        self.assertFalse(app.success)
        app.button[0].click().run()
        self.assertIn("fyi-review", app.success[0].value)

    def test_scenario_switch_and_repeat_click(self):
        app = self.app()
        app.selectbox[0].select(8).run()
        app.button[0].click().run()
        self.assertIn("manual-review", app.success[0].value)
        app.button[0].click().run()
        self.assertIn("manual-review", app.success[0].value)
        self.assertFalse(app.exception)
        app.selectbox[0].select(0).run()
        self.assertFalse(app.success)

    def test_live_is_disabled_until_explicit_consent_and_resets_on_edits(self):
        app = self.app()
        with patch("triage.providers.OpenAIProvider.__init__", side_effect=AssertionError("No live call expected")):
            app.radio[0].set_value("OpenAI API").run()
            self.assertTrue(app.button[0].disabled)
            app.checkbox[0].check().run()
            self.assertFalse(app.button[0].disabled)
            app.text_area[0].set_value("A different synthetic email.").run()
            self.assertFalse(app.checkbox[0].value)
            self.assertTrue(app.button[0].disabled)
        self.assertFalse(app.exception)

    def test_consent_fingerprint_has_unambiguous_data_boundaries(self):
        app = self.app()
        app.radio[0].set_value("OpenAI API").run()
        app.text_input[0].set_value("A\0B")
        app.text_area[0].set_value("C").run()
        app.checkbox[0].check().run()
        self.assertFalse(app.button[0].disabled)
        app.text_input[0].set_value("A")
        app.text_area[0].set_value("B\0C").run()
        self.assertFalse(app.checkbox[0].value)
        self.assertTrue(app.button[0].disabled)

    def test_live_missing_key_shows_sanitized_error(self):
        app = self.app()
        app.radio[0].set_value("OpenAI API").run()
        app.checkbox[0].check().run()
        with patch.dict("os.environ", {}, clear=True):
            app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("missing api key", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
