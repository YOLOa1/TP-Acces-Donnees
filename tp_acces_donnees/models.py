from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Any


class ValidationError(ValueError):
    """Erreur de validation lisible par l'utilisateur."""


@dataclass(frozen=True, slots=True)
class WorkOrder:
    ref_of: str
    ref_piece: str
    ref_client: str
    quantity: int
    end_date: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref_of", self.ref_of.strip())
        object.__setattr__(self, "ref_piece", self.ref_piece.strip())
        object.__setattr__(self, "ref_client", self.ref_client.strip())

        if not self.ref_of:
            raise ValidationError("La reference de l'OF est obligatoire.")
        if not self.ref_piece:
            raise ValidationError("La reference de la piece est obligatoire.")
        if len(self.ref_piece) > 10:
            raise ValidationError("La reference piece ne doit pas depasser 10 caracteres.")
        if not self.ref_client:
            raise ValidationError("La reference du client est obligatoire.")
        if len(self.ref_client) > 30:
            raise ValidationError("La reference client ne doit pas depasser 30 caracteres.")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise ValidationError("La quantite doit etre un entier.")
        if self.quantity <= 0:
            raise ValidationError("La quantite doit etre strictement positive.")
        if not isinstance(self.end_date, date):
            raise ValidationError("La date de fin est invalide.")

    @classmethod
    def from_strings(
        cls,
        ref_of: str,
        ref_piece: str,
        ref_client: str,
        quantity: str | int,
        end_date: str | date,
    ) -> "WorkOrder":
        try:
            parsed_quantity = int(quantity)
        except (TypeError, ValueError) as exc:
            raise ValidationError("La quantite doit etre un entier.") from exc

        if isinstance(end_date, date):
            parsed_date = end_date
        else:
            try:
                parsed_date = date.fromisoformat(str(end_date).strip())
            except (TypeError, ValueError) as exc:
                raise ValidationError("La date doit respecter le format AAAA-MM-JJ.") from exc

        return cls(ref_of, ref_piece, ref_client, parsed_quantity, parsed_date)

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "WorkOrder":
        return cls.from_strings(
            str(row["ref_of"]),
            str(row["ref_piece"]),
            str(row["ref_client"]),
            row["quantity"],
            row["end_date"],
        )

    def as_mapping(self) -> dict[str, str]:
        return {
            "ref_of": self.ref_of,
            "ref_piece": self.ref_piece,
            "ref_client": self.ref_client,
            "quantity": str(self.quantity),
            "end_date": self.end_date.isoformat(),
        }

