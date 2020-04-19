import unittest
import yaml
# https://www.weather.gov/
# these need to be installed, then included
try:
  from mpl_toolkits.basemap import Basemap
except:
  # !apt-get install libgeos-dev
  # !pip install https://github.com/matplotlib/basemap/archive/master.zip
  # %matplotlib inline
  from mpl_toolkits.basemap import Basemap
import matplotlib.patches as mpatches

import requests_cache
import shutil

#these are included in the standard python library, just need to import them
from pprint import pprint
import os
import logging
import datetime

# These are DataSciencey so Google includes them in the container, just need to import them
import requests
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

#setup logging
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT, filename='mapping.log',level=logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# Constants
earth_radius_major = 6378137.000 # useful for more accurate rendering of Mercator and Lambert projections
earth_radius_minor = 6356752.314

def download_url(url, save_path, chunk_size=128):
    r = requests.get(url, stream=True)
    with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)

def get_latest_shapes(dir, filename, drawbounds=False,
                      urlbase='https://mesonet.agron.iastate.edu/data/gis/shape/4326/us'):
                                 #https://mesonet.agron.iastate.edu/data/gis/shape/4326/us/current_ww.dbf
     for ext in ['dbf', 'shp', 'shx']:
         if not os.path.exists(dir):
             logging.info(f"directory {dir} created")
             os.makedirs(dir)
         url = f'{urlbase}/{filename}.{ext}'
         print(url)
         response = requests.get(url, stream=True)
         with open(f"{dir}/{filename}.{ext}", 'wb') as out_file:
             shutil.copyfileobj(response.raw, out_file)
         del response
         logging.info(f'shapefile fetched {url}')

def drap_map():
    # clat = 35.28  # NC center
    # clon = -79.02
    # wid = 1600000 / 2
    # hgt = 900000 / 2
    res = 'c'  # [c]rude (faster), [l]ow, [h]igh (slower)
    logging.info(f"------------------------")
    get_latest_shapes('IowaEnvMesonet', 'current_ww')
    fig = plt.figure(figsize=(12, 8), dpi=100)
    m = Basemap(llcrnrlon=-119, llcrnrlat=22, urcrnrlon=-64, urcrnrlat=49,
                projection='lcc', lat_1=33, lat_2=45, lon_0=-95,
                resolution=res
                )
    ax = fig.add_subplot(111)
    draw_map_background(m, ax)
    return m, ax

def draw_map_background(m, ax):
    ax.set_facecolor('#E0FFFF')
    m.fillcontinents(color='#FAFAFA', ax=ax, zorder=0)
    m.drawcounties(ax=ax, color="#CCCCCC")
    m.drawstates(ax=ax, color='black')
    m.drawcountries(ax=ax)
    m.drawcoastlines(ax=ax)

def draw_warnings(m, ax):
    pass

def ddraw_shapes(m, ax, dmas=['RALEIGH-DURHAM'], wfos=['RAH']):
    # m.readshapefile('https://github.com/rtphokie/RAHFeb2020SnowEvent/tree/master/dma_2008/DMAs', 'DMAs', ax=ax, drawbounds=False)
    get_latest_shapes(m, 'dma_2008', 'DMAs')
    get_latest_shapes(m, 'w_03mr20', 'w_03mr20')
    get_latest_shapes(m, 'NWS_actual', 'NWS_Actual_polygon', drawbounds=False)

    # m.readshapefile('mygeodata/NWS_Actual-polygon', 'NWS_Actual_polygon', ax=ax, drawbounds=True)
    # https://twitter.com/NWSRaleigh/status/1232344049568354307

    patches = {'0-0.5': [],
               '2-3': [],
               '3-4': [],
               '4-5': [],
               }

    for info, shape in zip(m.NWS_Actual_polygon_info, m.NWS_Actual_polygon):
        if info['Name'] in patches.keys():
            patches[info['Name']].append(Polygon(np.array(shape), True))
    pprint(patches)
    ax.add_collection(PatchCollection(patches['2-3'], edgecolor='k', linewidths=1., zorder=2))
    ax.add_collection(PatchCollection(patches['4-5'], edgecolor='k', alpha=0.5, linewidths=1., zorder=2))
    return
    wfos = []
    for info, shape in zip(m.w_03mr20_info, m.w_03mr20):
        if info['WFO'] in wfos:
            # highlight county warning areas of interest
            # x, y = zip(*shape)
            wfos.append(Polygon(np.array(shape), True))
    ax.add_collection(wfos, edgecolor='k', linewidths=1., zorder=2)

    for info, shape in zip(m.DMAs_info, m.DMAs):
        if info['NAME'] in dmas:
            # highlight DMAs of interest
            x, y = zip(*shape)
            m.plot(x, y, marker=None, color='k')

def main():
    lookup, significance = readconfig()

    fig = plt.figure()
    m, ax = drap_map()
    # m.shadedrelief()

    m.readshapefile("IowaEnvMesonet/current_ww", 'current_ww')

    patches = {}
    issuetimes = []
    for info, shape in zip(m.current_ww_info, m.current_ww):
        key = (info['PHENOM'], info['SIG'])
        issuetimes.append(info['UPDATED'])
        if key not in patches.keys():
            patches[key] = []
        patches[key].append(Polygon(np.array(shape), True))

    legenditems=[]
    legend_labels = {}
    for key in patches.keys():
        phenom, sig = key
        color = lookup[phenom]['colors'][significance[sig].lower()]
        legend_labels[key] = f"{lookup[phenom]['description']} {significance[sig]}"

        if color == 'None':
            raise LookupError(f"need color for {legend_labels[key]}")
        ax.add_collection(PatchCollection(patches[key],
                                          facecolor=f"#{color}",
                                          edgecolor='k',
                                          label=key, alpha=.9,
                                          linewidths=.05, zorder=2))
        legenditems.append(mpatches.Patch(color=f"#{color}", alpha=.9, label=legend_labels[key]
                                          ))

    plt.legend(handles=legenditems,
               bbox_to_anchor=(0,-0.15,1,1), loc='lower left',
               fontsize='x-small',
               ncol=5, fancybox=True, shadow=True)
    plt.title(f'Active Alerts {max(issuetimes)}Z')

    plt.savefig('conus_ww.png', bbox_inches='tight')

def readconfig():
    significance={
        'W': 'Warning',
        'Y': 'Advisory',
        'A': 'Watch',
        'S': 'Statement',
        'F': 'Forecast',
        'O': 'Outlook',
        'N': 'Synopsis',
    }
    with open('ww_colors.yml') as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    return data, significance

class MyTestCase(unittest.TestCase):

    def setUp(self):
        # cache data fetched from URLs for 1 hour
        requests_cache.install_cache('.test_cache', backend='sqlite', expire_after=1500)

    def test_something(self):
        main()

if __name__ == '__main__':
    main()
