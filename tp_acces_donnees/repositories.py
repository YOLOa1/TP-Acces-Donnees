from __future__ import annotations

import csv
import os
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

from .models import WorkOrder


class DuplicateReferenceError(ValueError):
    pass


class UnknownReferenceError(KeyError):
    pass


class WorkOrderRepository(Protocol):
    def list_all(self) -> list[WorkOrder]: ...
    def get(self, ref_of: str) -> WorkOrder | None: ...
    def add(self, order: WorkOrder) -> None: ...
    def update(self, original_ref: str, order: WorkOrder) -> None: ...
    def delete(self, ref_of: str) -> None: ...


class TextRepository:
    fieldnames = ["ref_of", "ref_piece", "ref_client", "quantity", "end_date"]

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def list_all(self) -> list[WorkOrder]:
        with self.path.open("r", encoding="utf-8", newline="") as stream:
            return [WorkOrder.from_mapping(row) for row in csv.DictReader(stream, delimiter="\t")]

    def get(self, ref_of: str) -> WorkOrder | None:
        key = ref_of.strip()
        return next((order for order in self.list_all() if order.ref_of == key), None)

    def add(self, order: WorkOrder) -> None:
        orders = self.list_all()
        if any(item.ref_of == order.ref_of for item in orders):
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.")
        orders.append(order)
        self._write(orders)

    def update(self, original_ref: str, order: WorkOrder) -> None:
        orders = self.list_all()
        index = next((i for i, item in enumerate(orders) if item.ref_of == original_ref), None)
        if index is None:
            raise UnknownReferenceError(original_ref)
        if order.ref_of != original_ref and any(item.ref_of == order.ref_of for item in orders):
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.")
        orders[index] = order
        self._write(orders)

    def delete(self, ref_of: str) -> None:
        orders = self.list_all()
        remaining = [order for order in orders if order.ref_of != ref_of]
        if len(remaining) == len(orders):
            raise UnknownReferenceError(ref_of)
        self._write(remaining)

    def _write(self, orders: list[WorkOrder]) -> None:
        fd, temp_name = tempfile.mkstemp(prefix=self.path.stem + "_", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.fieldnames, delimiter="\t")
                writer.writeheader()
                writer.writerows(order.as_mapping() for order in orders)
            os.replace(temp_name, self.path)
        except BaseException:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise


class XmlRepository:
    element_names = {
        "ref_of": "Ref_OF",
        "ref_piece": "Ref_Piece",
        "ref_client": "Ref_Client",
        "quantity": "Quantite",
        "end_date": "Date_Livraison",
    }

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def list_all(self) -> list[WorkOrder]:
        root = ET.parse(self.path).getroot()
        orders: list[WorkOrder] = []
        for node in root.findall("Commande"):
            values = {
                field: (node.findtext(tag) or "")
                for field, tag in self.element_names.items()
            }
            orders.append(WorkOrder.from_mapping(values))
        return orders

    def get(self, ref_of: str) -> WorkOrder | None:
        key = ref_of.strip()
        return next((order for order in self.list_all() if order.ref_of == key), None)

    def add(self, order: WorkOrder) -> None:
        orders = self.list_all()
        if any(item.ref_of == order.ref_of for item in orders):
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.")
        orders.append(order)
        self._write(orders)

    def update(self, original_ref: str, order: WorkOrder) -> None:
        orders = self.list_all()
        index = next((i for i, item in enumerate(orders) if item.ref_of == original_ref), None)
        if index is None:
            raise UnknownReferenceError(original_ref)
        if order.ref_of != original_ref and any(item.ref_of == order.ref_of for item in orders):
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.")
        orders[index] = order
        self._write(orders)

    def delete(self, ref_of: str) -> None:
        orders = self.list_all()
        remaining = [order for order in orders if order.ref_of != ref_of]
        if len(remaining) == len(orders):
            raise UnknownReferenceError(ref_of)
        self._write(remaining)

    def _write(self, orders: list[WorkOrder]) -> None:
        root = ET.Element("Commandes")
        for order in orders:
            command = ET.SubElement(root, "Commande")
            values = order.as_mapping()
            for field, tag in self.element_names.items():
                ET.SubElement(command, tag).text = values[field]
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        fd, temp_name = tempfile.mkstemp(prefix=self.path.stem + "_", suffix=".xml", dir=self.path.parent)
        os.close(fd)
        try:
            tree.write(temp_name, encoding="utf-8", xml_declaration=True)
            os.replace(temp_name, self.path)
        except BaseException:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise


class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS Piece_Tab (
                    ref_piece TEXT PRIMARY KEY CHECK(length(ref_piece) BETWEEN 1 AND 10)
                );
                CREATE TABLE IF NOT EXISTS Client_Tab (
                    ref_client TEXT PRIMARY KEY CHECK(length(ref_client) BETWEEN 1 AND 30)
                );
                CREATE TABLE IF NOT EXISTS OF_Tab (
                    ref_of TEXT PRIMARY KEY,
                    ref_piece TEXT NOT NULL REFERENCES Piece_Tab(ref_piece),
                    ref_client TEXT NOT NULL REFERENCES Client_Tab(ref_client),
                    nombre_pieces INTEGER NOT NULL CHECK(nombre_pieces > 0),
                    date_fin TEXT NOT NULL
                );
                """
            )

    def list_all(self) -> list[WorkOrder]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT ref_of, ref_piece, ref_client, nombre_pieces, date_fin "
                "FROM OF_Tab ORDER BY ref_of"
            ).fetchall()
        return [
            WorkOrder.from_strings(row["ref_of"], row["ref_piece"], row["ref_client"], row["nombre_pieces"], row["date_fin"])
            for row in rows
        ]

    def get(self, ref_of: str) -> WorkOrder | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT ref_of, ref_piece, ref_client, nombre_pieces, date_fin FROM OF_Tab WHERE ref_of = ?",
                (ref_of.strip(),),
            ).fetchone()
        if row is None:
            return None
        return WorkOrder.from_strings(row["ref_of"], row["ref_piece"], row["ref_client"], row["nombre_pieces"], row["date_fin"])

    @staticmethod
    def _ensure_references(connection: sqlite3.Connection, order: WorkOrder) -> None:
        connection.execute("INSERT OR IGNORE INTO Piece_Tab(ref_piece) VALUES (?)", (order.ref_piece,))
        connection.execute("INSERT OR IGNORE INTO Client_Tab(ref_client) VALUES (?)", (order.ref_client,))

    def add(self, order: WorkOrder) -> None:
        try:
            with self._connection() as connection:
                self._ensure_references(connection, order)
                connection.execute(
                    "INSERT INTO OF_Tab(ref_of, ref_piece, ref_client, nombre_pieces, date_fin) VALUES (?, ?, ?, ?, ?)",
                    (order.ref_of, order.ref_piece, order.ref_client, order.quantity, order.end_date.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.") from exc

    def update(self, original_ref: str, order: WorkOrder) -> None:
        try:
            with self._connection() as connection:
                self._ensure_references(connection, order)
                cursor = connection.execute(
                    "UPDATE OF_Tab SET ref_of=?, ref_piece=?, ref_client=?, nombre_pieces=?, date_fin=? WHERE ref_of=?",
                    (order.ref_of, order.ref_piece, order.ref_client, order.quantity, order.end_date.isoformat(), original_ref),
                )
                if cursor.rowcount == 0:
                    raise UnknownReferenceError(original_ref)
        except sqlite3.IntegrityError as exc:
            raise DuplicateReferenceError(f"L'OF {order.ref_of} existe deja.") from exc

    def delete(self, ref_of: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM OF_Tab WHERE ref_of = ?", (ref_of,))
            if cursor.rowcount == 0:
                raise UnknownReferenceError(ref_of)

