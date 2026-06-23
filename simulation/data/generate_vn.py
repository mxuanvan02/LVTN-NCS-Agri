import pandas as pd
import numpy as np
import os

np.random.seed(2026)
hours = 300
time = np.arange(hours)

# Simulate Mekong Delta climate: Base 28C, diurnal swing 5C
temp = 28.0 + 5.0 * np.sin(2 * np.pi * (time - 6) / 24.0)

# Inject Bursty Monsoon Rains (Sudden temperature drops in the afternoon)
for i in range(hours):
    hour_of_day = i % 24
    if hour_of_day in [14, 15, 16, 17] and np.random.rand() > 0.6:
        temp[i] -= np.random.uniform(4.0, 8.0) # Sudden drop of 4-8 degrees

# Add sensor noise
temp += np.random.normal(0, 0.5, hours)

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(_DATA_DIR, exist_ok=True)
df = pd.DataFrame({'temp_c': temp})
out_path = os.path.join(_DATA_DIR, 'vietnam_mekong_weather.csv')
df.to_csv(out_path, index=False)
print(f"Generated realistic Mekong Delta dataset at: {out_path}")
