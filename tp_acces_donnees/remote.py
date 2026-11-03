from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class RemoteDatabaseError(RuntimeError):
    pass


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
_SIMPLE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PyodbcModule(Protocol):
    def connect(self, connection_string: str, **kwargs: Any) -> Any: ...


def load_pyodbc() -> PyodbcModule:
    try:
        import pyodbc  # type: ignore
    except ImportError as exc:
        raise RemoteDatabaseError(
            "Le module pyodbc n'est pas installe. Executez : "
            "python -m pip install -r requirements-remote.txt"
        ) from exc
    return pyodbc


def validate_identifier(value: str) -> str:
    value = value.strip()
    if not _IDENTIFIER.fullmatch(value):
        raise RemoteDatabaseError("Nom de table invalide. Utilisez uniquement lettres, chiffres, '_' et un schema optionnel.")
    return ".".join(f"[{part}]" for part in value.split("."))


@dataclass(slots=True)
class RemoteConfig:
    dsn: str = ""
    driver: str = "ODBC Driver 17 for SQL Server"
    server: str = "PCAGILAPROD22"
    database: str = "TP_IP"
    user: str = "TPauto"
    password: str = ""

    @classmethod
    def local_simulation(cls) -> "RemoteConfig":
        return cls(
            dsn="",
            driver="ODBC Driver 17 for SQL Server",
            server=r"(localdb)\MSSQLLocalDB",
            database="TP_IP_Local",
            user="",
            password="",
        )

    def connection_string(self, database: str | None = None) -> str:
        if self.dsn.strip():
            parts = [f"DSN={self.dsn.strip()}"]
        else:
            parts = [f"DRIVER={{{self.driver.strip()}}}", f"SERVER={self.server.strip()}"]
        selected_database = self.database.strip() if database is None else database.strip()
        if selected_database:
            parts.append(f"DATABASE={selected_database}")
        if self.user.strip():
            parts.extend((f"UID={self.user.strip()}", f"PWD={self.password}"))
        else:
            parts.append("Trusted_Connection=yes")
        parts.extend(("APP=TP1 Acces aux donnees", "Encrypt=no", "TrustServerCertificate=yes"))
        return ";".join(parts) + ";"


class RemoteDatabaseClient:
    def __init__(self, config: RemoteConfig):
        self.config = config

    def _ensure_localdb_started(self) -> None:
        if self.config.dsn.strip() or "(localdb)" not in self.config.server.lower():
            return
        instance = self.config.server.rsplit("\\", 1)[-1].strip()
        executable = shutil.which("SqlLocalDB.exe") or shutil.which("sqllocaldb")
        if executable is None:
            for version in ("170", "160", "150", "140", "130", "120", "110"):
                candidate = Path(r"C:\Program Files\Microsoft SQL Server") / version / "Tools" / "Binn" / "SqlLocalDB.exe"
                if candidate.exists():
                    executable = str(candidate)
                    break
        if executable is None:
            raise RemoteDatabaseError(
                "SQL Server LocalDB est introuvable. Installez SQL Server Express LocalDB."
            )
        result = subprocess.run(
            [executable, "start", instance],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise RemoteDatabaseError(f"Impossible de demarrer LocalDB : {details}")

    def fetch_table(self, table: str, limit: int = 200) -> tuple[list[str], list[tuple[Any, ...]]]:
        safe_table = validate_identifier(table)
        pyodbc = load_pyodbc()
        self._ensure_localdb_started()

        try:
            connection = pyodbc.connect(self.config.connection_string(), timeout=5, autocommit=True)
            try:
                cursor = connection.cursor()
                cursor.execute(f"SELECT TOP {int(limit)} * FROM {safe_table}")
                columns = [column[0] for column in cursor.description]
                rows = [tuple(row) for row in cursor.fetchmany(limit)]
                return columns, rows
            finally:
                connection.close()
        except Exception as exc:
            raise RemoteDatabaseError(f"Connexion ou lecture impossible : {exc}") from exc

    def test_connection(self) -> tuple[str, str]:
        pyodbc = load_pyodbc()
        self._ensure_localdb_started()
        try:
            connection = pyodbc.connect(self.config.connection_string(), timeout=5, autocommit=True)
            try:
                row = connection.cursor().execute("SELECT @@SERVERNAME, DB_NAME()").fetchone()
                return str(row[0]), str(row[1])
            finally:
                connection.close()
        except Exception as exc:
            raise RemoteDatabaseError(f"Connexion impossible : {exc}") from exc

    def initialize_local_simulation(self) -> dict[str, int]:
        """Cree la base SQL Server LocalDB et insere des donnees de demonstration."""
        if self.config.dsn.strip() or "(localdb)" not in self.config.server.lower():
            raise RemoteDatabaseError(
                "L'initialisation est limitee a SQL Server LocalDB pour eviter de modifier un serveur distant."
            )
        database = self.config.database.strip()
        if not _SIMPLE_IDENTIFIER.fullmatch(database):
            raise RemoteDatabaseError("Le nom de la base locale est invalide.")

        pyodbc = load_pyodbc()
        self._ensure_localdb_started()
        try:
            master = pyodbc.connect(self.config.connection_string(database="master"), timeout=10, autocommit=True)
            try:
                master.cursor().execute(
                    f"IF DB_ID(N'{database}') IS NULL CREATE DATABASE [{database}]"
                )
            finally:
                master.close()

            connection = pyodbc.connect(self.config.connection_string(), timeout=10, autocommit=True)
            try:
                cursor = connection.cursor()
                statements = (
                    """
                    IF OBJECT_ID(N'dbo.Operateur_Tab', N'U') IS NULL
                    CREATE TABLE dbo.Operateur_Tab (
                        id_operateur INT IDENTITY(1,1) PRIMARY KEY,
                        matricule NVARCHAR(20) NOT NULL UNIQUE,
                        nom NVARCHAR(60) NOT NULL,
                        prenom NVARCHAR(60) NOT NULL,
                        poste NVARCHAR(80) NOT NULL
                    )
                    """,
                    """
                    IF OBJECT_ID(N'dbo.Machine_Tab', N'U') IS NULL
                    CREATE TABLE dbo.Machine_Tab (
                        id_machine INT IDENTITY(1,1) PRIMARY KEY,
                        reference NVARCHAR(20) NOT NULL UNIQUE,
                        designation NVARCHAR(100) NOT NULL,
                        etat NVARCHAR(30) NOT NULL
                    )
                    """,
                    """
                    IF OBJECT_ID(N'dbo.Piece_Tab', N'U') IS NULL
                    CREATE TABLE dbo.Piece_Tab (
                        ref_piece NVARCHAR(10) PRIMARY KEY,
                        designation NVARCHAR(100) NOT NULL,
                        famille NVARCHAR(50) NOT NULL
                    )
                    """,
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.Operateur_Tab)
                    INSERT INTO dbo.Operateur_Tab(matricule, nom, prenom, poste) VALUES
                        (N'OP001', N'Alami', N'Sara', N'Conductrice de ligne'),
                        (N'OP002', N'Benali', N'Youssef', N'Technicien maintenance'),
                        (N'OP003', N'Idrissi', N'Meryem', N'Controleuse qualite')
                    """,
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.Machine_Tab)
                    INSERT INTO dbo.Machine_Tab(reference, designation, etat) VALUES
                        (N'MACH01', N'Tour numerique', N'Disponible'),
                        (N'MACH02', N'Fraiseuse CNC', N'En production'),
                        (N'MACH03', N'Poste de controle', N'Maintenance')
                    """,
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.Piece_Tab)
                    INSERT INTO dbo.Piece_Tab(ref_piece, designation, famille) VALUES
                        (N'PieceX', N'Axe principal', N'Usinage'),
                        (N'PieceY', N'Support moteur', N'Assemblage'),
                        (N'PieceZ', N'Bride de fixation', N'Usinage')
                    """,
                )
                for statement in statements:
                    cursor.execute(statement)
                return {
                    "operateurs": int(cursor.execute("SELECT COUNT(*) FROM dbo.Operateur_Tab").fetchone()[0]),
                    "machines": int(cursor.execute("SELECT COUNT(*) FROM dbo.Machine_Tab").fetchone()[0]),
                    "pieces": int(cursor.execute("SELECT COUNT(*) FROM dbo.Piece_Tab").fetchone()[0]),
                }
            finally:
                connection.close()
        except RemoteDatabaseError:
            raise
        except Exception as exc:
            raise RemoteDatabaseError(f"Initialisation de la simulation impossible : {exc}") from exc

