import os
import subprocess
import sys
import unittest
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]


class SchemaIndexNamesTest(unittest.TestCase):
    def test_index_names_are_unique_across_schema(self):
        command = (
            "from app.db import Base; "
            "import app.db.topic_entities; "
            "names=[index.name for table in Base.metadata.tables.values() "
            "for index in table.indexes]; "
            "assert len(names)==len(set(names)), names"
        )
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite:///:memory:"
        env["SQL_ECHO"] = "false"

        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=SERVER_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
