import sys
sys.path.insert(0, '/home/kc/Documents/Ready_LEO_Project')

from dotenv import load_dotenv
load_dotenv()

from agents.bbox_agent import get_bounding_box
import geopandas as gpd
from shapely.geometry import box

bbox = get_bounding_box("North Carolina")
nc_shape = box(bbox['min_lon'], bbox['min_lat'], bbox['max_lon'], bbox['max_lat'])

us_links = gpd.read_file('/home/kc/Documents/Ready_LEO_Project/building_footprints_US_dataset.csv')

index_gdf = gpd.read_file('/home/kc/Documents/Ready_LEO_Project/buildings-with-height-coverage.geojson')
nc_tiles = index_gdf[index_gdf.intersects(nc_shape)]
print(nc_tiles['quadkey'].tolist())

print("Index quadkeys:", nc_tiles['quadkey'].head(5).tolist())
print("Dataset quadkeys:", us_links['QuadKey'].head(5).tolist())