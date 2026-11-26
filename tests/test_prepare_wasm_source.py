#!/usr/bin/env python3
"""Keep C literals and token boundaries intact in the prepared source."""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "prepare_wasm_source.py"
SPEC = importlib.util.spec_from_file_location("prepare_wasm_source", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrepareWasmSourceTest(unittest.TestCase):
    def test_prepare_preserves_literal_text_and_comment_separators(self):
        source = r'''const char *message = "a, b != c // text /* text */ \"q\"";
int/* removed */value = 1;
'''

        prepared = MODULE.prepare(source)

        self.assertIn('"a, b != c // text /* text */ \\"q\\""', prepared)
        self.assertIn("int value=1;", prepared)

    def test_prepare_preserves_repeated_literal_whitespace(self):
        source = '#define LABEL "a  b\t c"\nconst char *message = "a  b\t c";\n'

        prepared = MODULE.prepare(source)

        self.assertIn('#define LABEL "a  b\t c"', prepared)
        self.assertIn('"a  b\t c"', prepared)

    def test_prepare_preserves_runtime_error_message(self):
        message = '"hlolli_wg_violin: string must be 0, 1, 2, 3, or 4\\n"'
        self.assertIn(message, MODULE.prepare(f"InitError(csound, {message});\n"))


if __name__ == "__main__":
    unittest.main()
