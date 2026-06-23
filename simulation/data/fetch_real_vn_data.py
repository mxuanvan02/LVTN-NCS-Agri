import pandas as pd
import urllib.request
import json
import os

print("Fetching real historical weather data (ERA5 Reanalysis) for Can Tho, Mekong Delta, Vietnam...")
# Can Tho coordinates: Lat 10.0451, Lon 105.7469
# Fetching May 2023 data (transition to monsoon season, high heat and sudden rains)
url = "https://archive-api.open-meteo.com/v1/archive?latitude=10.0451&longitude=105.7469&start_date=2023-05-01&end_date=2023-05-20&hourly=temperature_2m"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    
temps = data['hourly']['temperature_2m']

# Save next to this script so the pipeline is portable across machines.
data_dir = os.path.dirname(__file__)
os.makedirs(data_dir, exist_ok=True)
df = pd.DataFrame({'temp_c': temps})
# Forward fill any missing values just in case
df['temp_c'] = df['temp_c'].ffill()

out_path = os.path.join(data_dir, 'vietnam_mekong_weather.csv')
df.to_csv(out_path, index=False)
print(f"Successfully downloaded {len(df)} hours of real ERA5 data to {out_path}")
