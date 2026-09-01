import unittest

from scripts.validate_rail_result_schema import RUN_LOAD_SCHEMA_PATH, main


class ValidateRailResultSchemaTests(unittest.TestCase):
    def test_guard_covers_every_published_rail_contract(self) -> None:
        main()

        self.assertTrue(RUN_LOAD_SCHEMA_PATH.exists())


if __name__ == "__main__":
    unittest.main()
