from pathlib import Path

from tp_acces_donnees.models import WorkOrder
from tp_acces_donnees.repositories import SQLiteRepository, TextRepository, XmlRepository


def main() -> None:
    data = Path(__file__).resolve().parent / "data"
    orders = [
        WorkOrder.from_strings("OF123", "PieceX", "ClientA", 10, "2023-01-15"),
        WorkOrder.from_strings("OF456", "PieceY", "ClientB", 20, "2023-02-28"),
    ]
    repositories = [
        TextRepository(data / "ordres.txt"),
        XmlRepository(data / "ordres.xml"),
        SQLiteRepository(data / "bdlocale.sqlite3"),
    ]
    for repository in repositories:
        existing = {order.ref_of for order in repository.list_all()}
        for order in orders:
            if order.ref_of not in existing:
                repository.add(order)
    print(f"Donnees initialisees dans {data}")


if __name__ == "__main__":
    main()

