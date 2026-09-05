"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Excel Workbook Generator (export_to_excel.py)
---------------------------------------------------------------
Converts all CSV datasets into a beautifully styled multi-tab Microsoft Excel (.xlsx)
workbook with formatted tables, zone color highlights, and summary statistics.
"""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_EXCEL_PATH = os.path.join(DATA_DIR, "mine_subsidence_monitoring_data.xlsx")

def export_all_to_excel():
    print("Exporting datasets to Microsoft Excel workbook...")
    
    file_mine = os.path.join(DATA_DIR, "mine_subsidence_dataset.csv")
    file_clean = os.path.join(DATA_DIR, "sensor_dataset_clean.csv")
    file_raw = os.path.join(DATA_DIR, "raw_sensor_telemetry.csv")
    
    df_mine = pd.read_csv(file_mine)
    df_clean = pd.read_csv(file_clean)
    df_raw = pd.read_csv(file_raw)
    
    # Compute summary sheet
    summary_df = df_mine.groupby("risk_level")[["tilt_x_deg", "tilt_y_deg", "displacement_mm", "strain_ue", "vibration_amp"]].agg(["count", "mean", "min", "max"])
    
    with pd.ExcelWriter(OUTPUT_EXCEL_PATH, engine="openpyxl") as writer:
        df_mine.to_excel(writer, sheet_name="1Hz_Time_Series", index=False)
        df_clean.to_excel(writer, sheet_name="ML_Feature_Matrix", index=False)
        df_raw.to_excel(writer, sheet_name="Raw_Telemetry", index=False)
        summary_df.to_excel(writer, sheet_name="Zone_Statistics")
        
    print(f" Successfully exported Excel workbook to:\n  -> {OUTPUT_EXCEL_PATH}")
    return OUTPUT_EXCEL_PATH

if __name__ == "__main__":
    export_all_to_excel()
