"""
Script de migración para agregar provider_name_snapshot y provider_rfc_snapshot
a movimientos existentes que tienen purchase_order_id pero no provider_id.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Cargar variables de entorno
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


async def migrate_provider_snapshots():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("=" * 60)
    print("MIGRACIÓN: Agregar snapshots de proveedor a movimientos")
    print("=" * 60)

    pos = await db.purchase_orders.find(
        {
            "status": {"$in": ["approved_for_payment", "partially_approved"]},
            "vendor_name": {"$exists": True, "$ne": None, "$ne": ""},
        },
        {"_id": 0, "id": 1, "vendor_name": 1, "vendor_rfc": 1, "folio": 1, "external_id": 1},
    ).to_list(10000)

    po_map = {po["id"]: po for po in pos}
    print(f"\n✓ Encontradas {len(po_map)} OC con proveedor\n")

    movements = await db.movements.find(
        {
            "purchase_order_id": {"$ne": None, "$exists": True},
            "$or": [
                {"provider_id": None},
                {"provider_id": {"$exists": False}},
                {"provider_name_snapshot": {"$exists": False}},
                {"provider_name_snapshot": None},
            ],
        },
        {"_id": 0, "id": 1, "purchase_order_id": 1, "provider_name_snapshot": 1},
    ).to_list(10000)

    print(f"✓ Encontrados {len(movements)} movimientos candidatos para actualizar\n")

    if len(movements) == 0:
        print("✓ No hay movimientos que migrar. Todo está actualizado.")
        client.close()
        return

    updated = 0
    skipped = 0

    for mov in movements:
        po_id = mov.get("purchase_order_id")
        if not po_id or po_id not in po_map:
            skipped += 1
            continue

        po = po_map[po_id]
        vendor_name = (po.get("vendor_name") or "").strip()
        vendor_rfc = (po.get("vendor_rfc") or "").strip().upper()

        if not vendor_name:
            skipped += 1
            continue

        await db.movements.update_one(
            {"id": mov["id"]},
            {
                "$set": {
                    "provider_name_snapshot": vendor_name,
                    "provider_rfc_snapshot": vendor_rfc or None,
                }
            },
        )
        updated += 1
        if updated % 50 == 0:
            print(f"  Procesados {updated} movimientos...")

    print("\n" + "=" * 60)
    print("MIGRACIÓN COMPLETADA")
    print("=" * 60)
    print(f"✓ Movimientos actualizados: {updated}")
    print(f"✓ Movimientos omitidos: {skipped}")
    print("=" * 60)

    sample = await db.movements.find(
        {"provider_name_snapshot": {"$ne": None}},
        {"_id": 0, "id": 1, "provider_name_snapshot": 1, "provider_rfc_snapshot": 1},
    ).limit(5).to_list(5)

    if sample:
        print("\nMuestra de movimientos actualizados:")
        for i, s in enumerate(sample, 1):
            print(f"  {i}. {s.get('provider_name_snapshot')} (RFC: {s.get('provider_rfc_snapshot') or 'N/A'})")

    client.close()


if __name__ == "__main__":
    asyncio.run(migrate_provider_snapshots())
