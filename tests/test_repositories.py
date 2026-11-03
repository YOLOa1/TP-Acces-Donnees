from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tp_acces_donnees.models import ValidationError, WorkOrder
from tp_acces_donnees.remote import RemoteConfig, RemoteDatabaseError, validate_identifier
from tp_acces_donnees.repositories import DuplicateReferenceError, SQLiteRepository, TextRepository, XmlRepository


class WorkOrderTests(unittest.TestCase):
    def test_validation_and_mapping(self) -> None:
        order = WorkOrder.from_strings(" OF1 ", "P1", "CLIENT", "4", "2026-11-03")
        self.assertEqual(order.ref_of, "OF1")
        self.assertEqual(order.quantity, 4)
        self.assertEqual(order.as_mapping()["end_date"], "2026-11-03")

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            WorkOrder.from_strings("OF1", "PIECE-TROP-LONGUE", "CLIENT", 1, "2026-11-03")
        with self.assertRaises(ValidationError):
            WorkOrder.from_strings("OF1", "P1", "CLIENT", 0, "2026-11-03")
        with self.assertRaises(ValidationError):
            WorkOrder.from_strings("OF1", "P1", "CLIENT", 1, "03/11/2026")


class RepositoryContract:
    repository_class = TextRepository
    filename = "orders.txt"

    def make_repository(self, folder: Path):
        return self.repository_class(folder / self.filename)

    def test_crud_contract(self) -> None:
        # Le bac a sable Windows n'autorise pas SQLite dans son dossier Temp
        # virtuel ; placer les fixtures pres des tests garde le test portable.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            repository = self.make_repository(Path(temp))
            original = WorkOrder.from_strings("OF1", "P1", "C1", 2, "2026-11-03")
            repository.add(original)
            self.assertEqual(repository.get("OF1"), original)
            with self.assertRaises(DuplicateReferenceError):
                repository.add(original)
            changed = WorkOrder.from_strings("OF2", "P2", "C2", 5, "2026-11-04")
            repository.update("OF1", changed)
            self.assertIsNone(repository.get("OF1"))
            self.assertEqual(repository.get("OF2"), changed)
            repository.delete("OF2")
            self.assertEqual(repository.list_all(), [])


class TextRepositoryTests(RepositoryContract, unittest.TestCase):
    repository_class = TextRepository
    filename = "orders.txt"


class XmlRepositoryTests(RepositoryContract, unittest.TestCase):
    repository_class = XmlRepository
    filename = "orders.xml"


class SQLiteRepositoryTests(RepositoryContract, unittest.TestCase):
    repository_class = SQLiteRepository
    filename = "orders.sqlite3"


class RemoteTests(unittest.TestCase):
    def test_connection_string_never_requires_saved_password(self) -> None:
        config = RemoteConfig(dsn="TP_TEST", database="TP_IP", user="TPauto", password="secret")
        self.assertIn("DSN=TP_TEST", config.connection_string())
        self.assertIn("DATABASE=TP_IP", config.connection_string())

    def test_table_identifier_validation(self) -> None:
        self.assertEqual(validate_identifier("dbo.Piece_Tab"), "[dbo].[Piece_Tab]")
        with self.assertRaises(RemoteDatabaseError):
            validate_identifier("Piece_Tab; DROP TABLE Piece_Tab")

    def test_local_simulation_configuration(self) -> None:
        config = RemoteConfig.local_simulation()
        self.assertEqual(config.server, r"(localdb)\MSSQLLocalDB")
        self.assertEqual(config.database, "TP_IP_Local")
        self.assertEqual(config.user, "")
        connection_string = config.connection_string()
        self.assertIn("Trusted_Connection=yes", connection_string)
        self.assertIn(r"SERVER=(localdb)\MSSQLLocalDB", connection_string)


if __name__ == "__main__":
    unittest.main()

