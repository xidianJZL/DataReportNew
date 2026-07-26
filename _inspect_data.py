"""快速了解测试数据的结构"""
import pandas as pd
import os

p = r"d:\code\myproject\ProductToolkit\DataReportNew\cn_ecommerce_orders_test.xlsx"
print(f"File: {p}")
print(f"Size: {os.path.getsize(p)} bytes")
print()
df = pd.read_excel(p)
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\nDtypes:\n{df.dtypes}")
print(f"\nFirst 3 rows:")
print(df.head(3).to_string())
print(f"\nLast 3 rows:")
print(df.tail(3).to_string())
print(f"\nBasic stats (numeric):")
print(df.describe().to_string())
print(f"\nNull counts:")
print(df.isna().sum().to_string())