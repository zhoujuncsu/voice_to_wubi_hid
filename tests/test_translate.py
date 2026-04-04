from __future__ import annotations

import json
import os
import tempfile
import unittest

from voice_to_wubi_hid.formatters import tokens_to_keystrokes
from voice_to_wubi_hid.translate.wubi import WubiSingleCharTranslator


class TestWubiSingleCharTranslator(unittest.TestCase):
    def test_single_char_and_corrections(self):
        with tempfile.TemporaryDirectory() as td:
            dict_path = os.path.join(td, "wubi.json")
            corr_path = os.path.join(td, "corrections.json")
            with open(dict_path, "w", encoding="utf-8") as f:
                json.dump({"你": "wq", "好": "vn", "你好": "xxxx"}, f, ensure_ascii=False)
            with open(corr_path, "w", encoding="utf-8") as f:
                json.dump({"好": "zz"}, f, ensure_ascii=False)

            tr = WubiSingleCharTranslator(dict_path, corr_path)
            tokens = tr.text_to_tokens("你好A，？")
            self.assertEqual([t.code for t in tokens], ["wq", "zz", "A", ",", "?"])

            ks = tokens_to_keystrokes(tokens, commit_key=" ")
            self.assertEqual(ks, "wq zz A,?") 


if __name__ == "__main__":
    unittest.main()

