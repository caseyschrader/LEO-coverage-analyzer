import pandas as pd

df = pd.read_csv('/home/kc/Documents/Ready_LEO_Project/dataset-links.csv')

df = df[df['Location'] == 'UnitedStates']

df.to_csv('building_footprints_US_dataset.csv', index=False)

