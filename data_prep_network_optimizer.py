import pandas as pd

customers = pd.read_csv("optimization_data-main/customers.csv")
suppliers = pd.read_csv("optimization_data-main/suppliers_with_moq.csv")
lanes = pd.read_csv("optimization_data-main/lanes.csv")

df = lanes.merge(suppliers, on="supplier_id")
df = df.merge(customers, on="customer_id")

df = df[df["allowed"] == 1]

df["total_unit_cost"] = df["unit_cost"] + df["ship_cost_per_unit"]

df.to_csv("preprocessed_data/network_flat.csv", index=False)
