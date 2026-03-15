"""
Script de migración para agregar provider_name_snapshot y provider_rfc_snapshot
a movimientos existentes que tienen purchase_order_id pero no provider_id.
"""

import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def migrate_provider_snapshots():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("Iniciando migración de snapshots de proveedores...")

    pos = await db.purchase_orders.find(
        {
            "status": {"$in": ["approved_for_payment", "partially_approved"]},
            "vendor_name": {"$exists": True, "$ne": None, "$ne": ""},
        },
        {"_id": 0, "id": 1, "vendor_name": 1, "vendor_rfc": 1},
    ).to_list(10000)

    po_map = {po["id"]: po for po in pos}
    print(f"Encontradas {len(po_map)} OC con proveedor")

    movements = await db.movements.find(
        {
            "$or": [
                {"provider_id": None},
                {"provider_id": {"$exists": False}},
            ],
            "purchase_order_id": {"$ne": None, "$exists": True},
        },
        {"_id": 0, "id": 1, "purchase_order_id": 1},
    ).to_list(10000)

    print(f"Encontrados {len(movements)} movimientos candidatos para actualizar")

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

        if vendor_name:
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
            if updated % 100 == 0:
                print(f"Actualizados {updated} movimientos...")

    print("\nMigración completada:")
    print(f"  - Movimientos actualizados: {updated}")
    print(f"  - Movimientos omitidos: {skipped}")

    client.close()


if __name__ == "__main__":
    asyncio.run(migrate_provider_snapshots())
