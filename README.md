# NOAA-GHCN

[![PyPI version](https://badge.fury.io/py/noaa-ghcn.svg)](https://badge.fury.io/py/noaa-ghcn)
![versions](https://img.shields.io/pypi/pyversions/noaa-ghcn.svg)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A package to search and retrieve data from the National Oceanic and Atmospheric Administration (NOAA) Global Historical Climatology Network Daily (GHCN-D) [dataset](https://registry.opendata.aws/noaa-ghcn/) hosted on [Amazon AWS S3.](https://noaa-ghcn-pds.s3.amazonaws.com/index.html)

## Installation

Install with pip
```
pip install noaa-ghcn
```

## Usage

Import and initialize the `GHCN` class

```
>>> from noaa_ghcn import GHCN
>>> ghcn = GHCN()
>>> ghcn
NOAA Global Historical Climatology Network Daily (GHCN-D): 129,657 stations, 765,719 inventory records
```

When initialized for the first time, the station and inventory data files will automatically be downloaded to the package data directory. If the data files already exist, the timestamps are checked and the user will be asked if they optionally want to update the data.

### Available functionality

The available attributes and methods are:
```
ghcn.elements
ghcn.stations
ghcn.inventory
ghcn.filter_stations()
ghcn.filter_inventory()
ghcn.load_data()
```

> [!NOTE]
> The units have been standardized compared to the original data such that downloaded data has one of the following units: degrees, mm, degrees C, percent, minutes, hPa, cm


### Parameters/Elements
All the available parameters (elements) can be listed with
```
>>> ghcn.elements
The five core elements are:
PRCP = Precipitation (mm)
SNOW = Snowfall (mm)
...
```

### Stations
All stations are accessible as a Pandas.DataFrame
```
>>> ghcn.stations.head(3)
            ID  LATITUDE  LONGITUDE ELEVATION                   NAME STATE GSN FLAG  HCN/CRN FLAG  WMO ID                  geometry
0  ACW00011604   17.1167   -61.7833      10.1  ST JOHNS COOLIDGE FLD   NaN      NaN           NaN     NaN  POINT (-61.7833 17.1167)
1  ACW00011647   17.1333   -61.7833      19.2               ST JOHNS   NaN      NaN           NaN     NaN  POINT (-61.7833 17.1333)
2  AE000041196   25.3330    55.5170      34.0    SHARJAH INTER. AIRP   NaN      GSN       41196.0     NaN     POINT (55.517 25.333)
```

### Inventory
The inventory (which elements are available for each station and timeframe) is also accessible as a Pandas.DataFrame
```
>>> ghcn.inventory.head(3)
            ID  LATITUDE  LONGITUDE ELEMENT  FIRSTYEAR  LASTYEAR                  geometry
0  ACW00011604   17.1167   -61.7833    TMAX       1949      1949  POINT (-61.7833 17.1167)
1  ACW00011604   17.1167   -61.7833    TMIN       1949      1949  POINT (-61.7833 17.1167)
2  ACW00011604   17.1167   -61.7833    PRCP       1949      1949  POINT (-61.7833 17.1167)
```

### Filter Stations
Stations can be filtered by a list of station `'ID'`
```
>>> ghcn.filter_stations(station_ids=['AE000041196', 'AFM00040938'])
            ID  LATITUDE  LONGITUDE ELEVATION                 NAME STATE GSN FLAG  HCN/CRN FLAG  WMO ID               geometry
2  AE000041196    25.333     55.517      34.0  SHARJAH INTER. AIRP   NaN      GSN       41196.0     NaN  POINT (55.517 25.333)
7  AFM00040938    34.210     62.228     977.2                HERAT   NaN      NaN       40938.0     NaN   POINT (62.228 34.21)
```

Or filtered by a `shapely.Geometry` (assumes geometry is in `EPSG:4326` / `WGS 84` coordinates)
```
>>> import shapely
>>> my_stations = ghcn.filter_stations(geometry=shapely.box(-10.7, 51.3, -5.3, 55.6))
>>> my_stations.head(3)
                ID  LATITUDE  LONGITUDE ELEVATION                  NAME STATE GSN FLAG  HCN/CRN FLAG  WMO ID                  geometry
33480  EI000003953   51.9394   -10.2219       9.0  VALENTIA OBSERVATORY   NaN      GSN        3953.0     NaN  POINT (-10.2219 51.9394)
33481  EI000003965   53.0903    -7.8764      70.0                  BIRR   NaN      NaN        3965.0     NaN   POINT (-7.8764 53.0903)
33482  EI000003969   53.3639    -6.3192      49.0   DUBLIN PHOENIX PARK   NaN      NaN        3969.0     NaN   POINT (-6.3192 53.3639)
```

### Filter Inventory
The inventory can be filtered for given stations, geometry (bounding box), elements and dates. The filtered dataframe has columns of `start_date` and `end_date` that correspond to the available data for each station and element.
```
>>> import datetime as dt
>>> inventory_subset = ghcn.filter_inventory(station_ids=['AE000041196', 'AFM00040938'], start_date= dt.datetime(2020, 2, 3), end_date=dt.datetime(2024, 11, 27))
>>> inventory_subset
             ID  LATITUDE  LONGITUDE ELEMENT  FIRSTYEAR  LASTYEAR               geometry start_date   end_date
18  AE000041196    25.333     55.517    TMAX       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
19  AE000041196    25.333     55.517    TMIN       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
20  AE000041196    25.333     55.517    PRCP       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
39  AFM00040938    34.210     62.228    TMAX       1973      2020   POINT (62.228 34.21) 2020-03-21 2020-12-31
40  AFM00040938    34.210     62.228    TMIN       1973      2020   POINT (62.228 34.21) 2020-03-21 2020-12-31
41  AFM00040938    34.210     62.228    PRCP       2014      2021   POINT (62.228 34.21) 2020-03-21 2021-12-31
42  AFM00040938    34.210     62.228    SNWD       1982      2021   POINT (62.228 34.21) 2020-03-21 2021-12-31
```

This subset of the inventory can be further refined before retrieving data, e.g. removing stations/elements that have too few data
```
# Only include elements that have at least 1 year of data
>>> idx = inventory_subset['end_date'].sub(inventory_subset['start_date']).dt.days > 365
>>> inventory_subset = inventory_subset.loc[idx]
>>> inventory_subset
             ID  LATITUDE  LONGITUDE ELEMENT  FIRSTYEAR  LASTYEAR               geometry start_date   end_date
18  AE000041196    25.333     55.517    TMAX       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
19  AE000041196    25.333     55.517    TMIN       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
20  AE000041196    25.333     55.517    PRCP       1944      2025  POINT (55.517 25.333) 2020-03-21 2024-11-27
41  AFM00040938    34.210     62.228    PRCP       2014      2021   POINT (62.228 34.21) 2020-03-21 2021-12-31
42  AFM00040938    34.210     62.228    SNWD       1982      2021   POINT (62.228 34.21) 2020-03-21 2021-12-31
```

### Downloading Data
Using the inventory dataframe, the daily station data can be downloaded
```
>>> df = ghcn.load_data(inventory_subset)
Downloading data: 100%|█████████████████████████████| 5/5 [00:00<00:00,  9.18file/s]
>>> df.head()
            ID       DATE  DATA_VALUE M_FLAG Q_FLAG S_FLAG OBS_TIME ELEMENT
0  AE000041196 2020-03-24        23.8   None   None      S     None    TMAX
1  AE000041196 2020-03-25        25.1   None   None      S     None    TMAX
2  AE000041196 2020-03-26        27.7   None   None      S     None    TMAX
3  AE000041196 2020-03-27        31.5   None   None      S     None    TMAX
4  AE000041196 2020-03-28        34.5   None   None      S     None    TMAX
```

## Development

Clone the repo and install the package with the `dev` environment. This project uses [Pixi](https://pixi.sh/) to manage dependencies, which should be installed first.

```bash
git clone https://github.com/colinahill/noaa-ghcn.git
cd noaa-ghcn
pixi install -e dev
pixi shell -e dev
```
