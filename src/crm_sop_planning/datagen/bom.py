"""Bill of Materials: how much of each raw material one unit of each
battery product consumes. Recipes scale roughly with capacity_ah (a bigger
battery needs more lead, acid, and casing material), which is what makes
the downstream MRP explosion behave sensibly across the product range.
"""

from __future__ import annotations

import pandas as pd

# Per-Ah-per-cell consumption factors, roughly typical of flooded lead-acid
# construction. Scaled by capacity_ah and a category multiplier (motorcycle
# batteries use thinner plates than industrial ones of the same nominal Ah).
CATEGORY_FACTOR = {
    "Automotive SLI": 1.0,
    "Motorcycle": 0.85,
    "Industrial / UPS": 1.15,
    "Deep-Cycle / Solar": 1.2,
}

FIXED_PER_UNIT = {
    # materials that don't scale with capacity — one casing, one set of
    # terminals, one carton, etc. per unit regardless of size.
    "Terminal Posts (Lead Alloy)": 2.0,
    "Cartons": 1.0,
    "Packaging Film": 1.0,
    "Warning Labels": 1.0,
}

SCALING_PER_AH = {
    "Lead Ingot": 0.028,
    "Lead Oxide": 0.021,
    "Sulfuric Acid": 0.014,
    "Acid Additives": 0.0015,
    "Polypropylene Resin": 0.006,
    "Separator Sheets": 0.02,
    "Calcium Alloy Grids": 0.010,
}

AGM_MATERIAL = "AGM Glass Mat"
AGM_PER_AH = 0.018


def generate_bom(products: pd.DataFrame, raw_materials: pd.DataFrame) -> pd.DataFrame:
    material_id_by_name = dict(zip(raw_materials["material_name"], raw_materials["material_id"]))

    rows = []
    for _, product in products.iterrows():
        factor = CATEGORY_FACTOR[product["category"]]
        ah = product["capacity_ah"]

        for material_name, per_ah in SCALING_PER_AH.items():
            qty = round(per_ah * ah * factor, 5)
            rows.append(
                {
                    "product_id": product["product_id"],
                    "material_id": material_id_by_name[material_name],
                    "qty_per_unit": qty,
                }
            )

        for material_name, qty in FIXED_PER_UNIT.items():
            rows.append(
                {
                    "product_id": product["product_id"],
                    "material_id": material_id_by_name[material_name],
                    "qty_per_unit": qty,
                }
            )

        if "AGM" in product["product_name"]:
            qty = round(AGM_PER_AH * ah, 5)
            rows.append(
                {
                    "product_id": product["product_id"],
                    "material_id": material_id_by_name[AGM_MATERIAL],
                    "qty_per_unit": qty,
                }
            )

    return pd.DataFrame(rows)
