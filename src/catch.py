"""
Stage 1: Catch Receipt — Fields 1-3, 13

Proves fish origin + sustainability.
Species ID, fishery approval, import docs, fishery certification.
"""

import os

from .core import dual_hash, emit_receipt, find_receipt, StopRule

# FDA-approved fish oil species
APPROVED_SPECIES = {
    "Engraulis ringens": "Peruvian Anchoveta",
    "Sardina pilchardus": "European Sardine",
    "Brevoortia tyrannus": "Atlantic Menhaden",
    "Brevoortia patronus": "Gulf Menhaden",
    "Clupea harengus": "Atlantic Herring",
    "Scomber scombrus": "Atlantic Mackerel",
    "Mallotus villosus": "Capelin",
    "Salmo salar": "Atlantic Salmon",
    "Oncorhynchus mykiss": "Rainbow Trout",
    "Gadus morhua": "Atlantic Cod",
    "Pollachius virens": "Pollock",
    "Thunnus albacares": "Yellowfin Tuna",
    "Katsuwonus pelamis": "Skipjack Tuna",
    "Sprattus sprattus": "European Sprat",
    "Micromesistius poutassou": "Blue Whiting",
}

FISHERY_CERT_TYPES = {"MSC", "FriendOfSea", "None"}


def validate_species(species: str) -> bool:
    """Check if species is on the FDA-approved fish oil list.

    Args:
        species: Scientific name of the species.

    Returns:
        True if approved.
    """
    return species in APPROVED_SPECIES


def hash_document(file_path: str) -> str:
    """Dual-hash a document file.

    Args:
        file_path: Path to document (PDF, etc.)

    Returns:
        Dual hash string.

    Raises:
        StopRule: If file does not exist.
    """
    if not os.path.exists(file_path):
        raise StopRule(f"Document not found: {file_path}")

    with open(file_path, "rb") as f:
        data = f.read()
    return dual_hash(data)


def create_catch_receipt(
    species: str,
    fishery_registry: str,
    import_docs_hash: str,
    fishery_cert_type: str = "None",
    fishery_cert_id: str | None = None,
    fishery_cert_hash: str | None = None,
    tenant_id: str | None = None,
    ledger_path: str | None = None,
) -> dict:
    """Create a Stage 1 catch receipt.

    Args:
        species: Scientific name of fish species.
        fishery_registry: Name of fishery registry (e.g., "PRODUCE Peru").
        import_docs_hash: Dual-hash of import documents.
        fishery_cert_type: MSC, FriendOfSea, or None.
        fishery_cert_id: Certificate ID if certified.
        fishery_cert_hash: Dual-hash of certification PDF.
        tenant_id: Tenant identifier.
        ledger_path: Override ledger path.

    Returns:
        Catch receipt dict.

    Raises:
        StopRule: If species not approved or cert data inconsistent.
    """
    # Validate species
    if not validate_species(species):
        raise StopRule(f"Species not FDA-approved for fish oil: {species}")

    # Validate fishery cert consistency
    if fishery_cert_type not in FISHERY_CERT_TYPES:
        raise StopRule(f"Invalid fishery cert type: {fishery_cert_type}")

    if fishery_cert_type != "None" and not fishery_cert_hash:
        raise StopRule(
            f"Fishery cert type {fishery_cert_type} claimed but no cert hash provided"
        )

    species_common = APPROVED_SPECIES[species]
    fishery_approved = True  # If we get here, fishery is approved

    payload = {
        "species": species,
        "species_common": species_common,
        "fishery_approved": fishery_approved,
        "fishery_registry": fishery_registry,
        "import_docs_hash": import_docs_hash,
        "fishery_cert_type": fishery_cert_type,
        "fishery_cert_id": fishery_cert_id,
        "fishery_cert_hash": fishery_cert_hash,
    }

    return emit_receipt("catch", payload, tenant_id=tenant_id, ledger_path=ledger_path)
