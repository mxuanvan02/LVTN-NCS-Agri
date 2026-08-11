import pandas as pd
import numpy as np
import os

print("Generating weather-conditioned synthetic LoRaWAN packet loss trace for Smart Agriculture...")
# This script generates a synthetic packet-status trace from weather-conditioned heuristics.
# It should not be described as an empirical field-measured LoRa trace unless measured packet logs are added.
# Based on empirical LoRaWAN studies, packet loss can correlate with environmental factors such as rain,
# humidity, and canopy attenuation. We approximate this by increasing burst loss when sudden temperature
# drops occur, plus a baseline path-loss.

weather_path = os.path.join(os.path.dirname(__file__), 'vietnam_mekong_weather.csv')
if os.path.exists(weather_path):
    df_weather = pd.read_csv(weather_path)
    temps = df_weather['temp_c'].values[:300]
else:
    temps = np.full(300, 28.0)

np.random.seed(42)
trace = []
for i in range(len(temps)):
    # Baseline dropout for LoRa in dense foliage: ~10%
    base_drop_prob = 0.10 
    
    # If temperature drops sharply (rain/storm), foliage gets wet -> attenuation spikes
    if i > 0 and (temps[i-1] - temps[i]) > 2.0:
        drop_prob = 0.70 # Severe bursty loss during rain
    else:
        drop_prob = base_drop_prob
        
    # Markov chain smoothing to simulate burstiness of wireless channel
    if i > 0 and trace[-1] == 0: # If previous packet was lost
        drop_prob = min(0.9, drop_prob + 0.4) # Higher chance to stay in bad state
        
    # 1 = Success, 0 = Loss
    packet_status = 1 if np.random.rand() > drop_prob else 0
    trace.append(packet_status)

df_trace = pd.DataFrame({'packet_status': trace})
out_path = os.path.join(os.path.dirname(__file__), 'synthetic_weather_conditioned_lora_trace.csv')
df_trace.to_csv(out_path, index=False)
print(f"Generated weather-conditioned synthetic trace (300 hours) with {(1.0 - np.mean(trace))*100:.1f}% overall packet loss to {out_path}")
