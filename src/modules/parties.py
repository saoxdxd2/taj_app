"""Shared notion of who the business trades with.

A party is either a registered company (ICE, RC...) or a private
individual. The French labels are the values stored in the database.
"""
from enum import Enum


class PartyType(str, Enum):
    ENTERPRISE = "Entreprise"
    INDIVIDUAL = "Individuel"


def individual_full_name(first_name, last_name) -> str:
    """
    Display name stored in `company_name` for an individual party.

    Keeping it there means every list, combo box and printed document
    continues to show one name without knowing about party types.
    """
    parts = [
        (first_name or "").strip(),
        (last_name or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def as_party_type(value) -> PartyType:
    """Accepts a PartyType or one of the stored French labels."""
    if isinstance(value, PartyType):
        return value
    if value is None:
        return PartyType.ENTERPRISE
    try:
        return PartyType(value)
    except ValueError:
        pass
    try:
        return PartyType[str(value).upper()]
    except KeyError:
        raise ValueError("Party type must be Entreprise or Individuel.")
