import boto3
from botocore.client import Config
from botocore import UNSIGNED
from pathlib import Path
import datetime as dt
import pandas as pd
import geopandas as gpd
import shapely
import typing as T
import numpy as np
import concurrent.futures
import pyarrow.parquet as pq
import io
from tqdm import tqdm


class GHCN:

	def __init__(self):
		
		self._bucket = 'noaa-ghcn-pds'
		self._region_name = 'us-east-1'
		self._s3 = self._connect_to_s3()

		self._data_dir = Path(__file__).parent.parent / 'data'

		self._stations_filename = 'ghcnd-stations.txt'
		self._stations_filepath = self._data_dir / self._stations_filename
		self._stations_lastmodified = None
			
		self._inventory_filename = 'ghcnd-inventory.txt'
		self._inventory_filepath = self._data_dir / self._inventory_filename
		self._inventory_lastmodified = None
		
		self._check_stations_file()
		self._check_inventory_file()

		self._load_elements()
		self.stations = self._load_stations()
		self.inventory = self._load_inventory()

	def __repr__(self):
		return (
			'NOAA Global Historical Climatology Network Daily (GHCN-D): ' +
			f'{self.stations.shape[0]:,} stations, {self.inventory.shape[0]:,} inventory records'
			)
	
	@property
	def elements(self):
		print(self._elements)

	def filter_stations(
			self,
			station_ids: T.List[str] = None,
			geometry: shapely.geometry = None
			):
		boolean_arrays = []

		# Filter by station IDs
		if station_ids:
			boolean_arrays.append(self.stations['ID'].isin(station_ids))

		# Filter by intersection with the geometry
		if geometry:
			boolean_arrays.append(self.stations.intersects(geometry))
		
		return self._boolean_index(self.stations, boolean_arrays)

	def filter_inventory(
			self,
			station_ids: T.List[str] = None,
			start_date: dt.datetime = None,
			end_date: dt.datetime = None,
			elements: T.List[str] =['TMAX', 'TMIN', 'PRCP', 'SNOW', 'SNWD'],
			geometry: shapely.geometry = None
			):
		boolean_arrays = []

		# Filter by station IDs
		if station_ids is not None:
			boolean_arrays.append(self.inventory['ID'].isin(station_ids))
		# Filter by element
		if elements is not None:
			boolean_arrays.append(self.inventory['ELEMENT'].isin(elements))
		# Filter by year
		if start_date:
			boolean_arrays.append(self.inventory['LASTYEAR'].ge(start_date.year))
		if end_date:
			boolean_arrays.append(self.inventory['FIRSTYEAR'].le(end_date.year))
		# Filter by intersection with the geometry
		if geometry:
			boolean_arrays.append(self.inventory.intersects(geometry))
		
		inventory_subset = self._boolean_index(self.inventory, boolean_arrays).copy()

		# Create start/end dates for the available data by combining the given dates and the first/last years
		if start_date:
			idx = inventory_subset['FIRSTYEAR'].lt(start_date.year)
			inventory_subset.loc[idx, 'start_date'] = start_date
			inventory_subset.loc[~idx, 'start_date'] = pd.to_datetime(inventory_subset.loc[~idx, 'FIRSTYEAR'], format="%Y")
		else:
			inventory_subset.loc[:, 'start_date'] = pd.to_datetime(inventory_subset['FIRSTYEAR'], format="%Y")
		
		if end_date:
			idx = inventory_subset['LASTYEAR'].lt(end_date.year)
			inventory_subset.loc[idx, 'end_date'] = pd.to_datetime(inventory_subset.loc[idx, 'LASTYEAR'].map(lambda y: f"{y}-12-31"), format='%Y-%m-%d')
			inventory_subset.loc[~idx, 'end_date'] = end_date
		else:
			inventory_subset.loc[:, 'end_date'] = pd.to_datetime(inventory_subset.loc[:, 'LASTYEAR'].map(lambda y: f"{y}-12-31"), format='%Y-%m-%d')
		
		return inventory_subset

	def load_data(
			self,
			inventory_subset: T.Union[pd.DataFrame, gpd.GeoDataFrame],
		):
		file_metadata = []
		for i, row in inventory_subset.iterrows():
			element = row['ELEMENT']
			prefix = f"parquet/by_station/STATION={row['ID']}/ELEMENT={element}/"
			response = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
			file_metadata.append((
				response['Contents'][0]['Key'], # Assume one file per station/element combination
				row['start_date'],
				row['end_date'],
				element,
			))
		df = self._read_parquet_parallel(file_metadata)
		return df

	def _boolean_index(self, df, boolean_arrays: T.List = []):
		if boolean_arrays:
			idx = np.all(boolean_arrays, axis=0)
			return df.iloc[idx]
		else:
			return df

	def _connect_to_s3(self):
		client = boto3.client('s3', region_name=self._region_name, config=Config(signature_version=UNSIGNED))
		client.head_bucket(Bucket=self._bucket)
		return client

	def _check_stations_file(self):
		"""
		Check if the stations file exists. If not, download it. If so, check last update
		time and optionally download a new version.
		"""
		if self._stations_filepath.exists():
			self._stations_lastmodified = self._get_local_file_timestamp(self._stations_filepath)
			remote_timestamp = self._get_remote_file_timestamp(self._stations_filename)
			if remote_timestamp > self._stations_lastmodified:
				n_days = (remote_timestamp - self._stations_lastmodified).days
				update = input(f'Local Station data is {n_days:,} day out of date, update file? <y/N>: ')
				if update.lower() == 'y':
					self._download_stations()
		else:
			print(f'No local Station data available, downloading file...')
			self._download_stations()

	def _download_stations(self):
		print('Downloading stations file...')
		self._s3.download_file(self._bucket, self._stations_filename,  self._stations_filepath)
		self._stations_lastmodified = self._get_local_file_timestamp(self._stations_filepath)

	def _check_inventory_file(self):
		"""
		Check if the inventory file exists. If not, download it. If so, check last update
		time and optionally download a new version.
		"""
		if self._inventory_filepath.exists():
			self._inventory_lastmodified = self._get_local_file_timestamp(self._inventory_filepath)
			remote_timestamp = self._get_remote_file_timestamp(self._inventory_filename)
			if remote_timestamp > self._inventory_lastmodified:
				n_days = (remote_timestamp - self._inventory_lastmodified).days
				update = input(f'Local Inventory data is {n_days:,} day out of date, update file? <y/N>: ')
				if update.lower() == 'y':
					self._download_inventory()
		else:
			print(f'No local Inventory data available, downloading file...')
			self._download_inventory()
			print(self._inventory_filepath.exists(), self._inventory_lastmodified)

	def _download_inventory(self):
		print('Downloading inventory file...')
		self._s3.download_file(self._bucket, self._inventory_filename,  self._inventory_filepath)
		self._inventory_lastmodified = self._get_local_file_timestamp(self._inventory_filepath)

	def _get_remote_file_timestamp(self, filepath):
		response = self._s3.head_object(Bucket=self._bucket, Key=filepath)
		return response["LastModified"]

	def _get_local_file_timestamp(self, filepath):
		t = filepath.stat().st_mtime
		return dt.datetime.fromtimestamp(t, tz=dt.timezone.utc)

	def _load_elements(self):
		self._elements = (self._data_dir / 'elements.txt').read_text()

	def _load_stations(self):
		df = pd.read_fwf(
			self._stations_filepath,
			header=None,
			formatting_info=(0, 11, 13, 20, 22, 30, 32, 37, 39, 40, 42, 71, 73, 75, 77, 79, 81, 85),
			names=['ID', 'LATITUDE', 'LONGITUDE', 'ELEVATION', 'NAME', 'STATE', 'GSN FLAG', 'HCN/CRN FLAG', 'WMO ID']
		)
		# replace missing elevation values with NaN
		df['ELEVATION'] = df['ELEVATION'].replace(-999.9, pd.NA)
		return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['LONGITUDE'], df['LATITUDE']), crs='EPSG:4326')

	def _load_inventory(self):
		df = pd.read_fwf(
			self._inventory_filepath,
			header=None,
			formatting_info=(0, 11, 13, 20, 22, 30, 32, 35, 37, 40, 42, 45),
			names=['ID', 'LATITUDE', 'LONGITUDE', 'ELEMENT', 'FIRSTYEAR', 'LASTYEAR']
		)
		return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['LONGITUDE'], df['LATITUDE']), crs='EPSG:4326')

	def _load_parquet(self, key, start_date, end_date, element):
		"""
		Download a Parquet file from S3 using boto3 and load it with PyArrow.
		Parse and convert data values so all data is type float
		"""
		response = self._s3.get_object(Bucket=self._bucket, Key=key)
		filestream = io.BytesIO(response['Body'].read())

		# Read Parquet file using pyarrow
		table = pq.read_table(filestream)
		df = table.to_pandas()		
		
		df['DATE'] = pd.to_datetime(df['DATE'], format='%Y%m%d')
		df = df.loc[df['DATE'].between(start_date, end_date)]

		# Standardize units
		df['DATA_VALUE'] = self._standardize_units(df['DATA_VALUE'], element)
		df['ELEMENT'] = element

		return df
	
	def _standardize_units(self, series, element):
		
		# Convert string hours and minutes (HHMM) to minutes
		if element in ['FMTM', 'PGTM']:
			
			def hhmm_to_minutes(x):
				s = str(x).zfill(4)
				return int(s[:2]) * 60 + float(s[2:])			

			return series.map(hhmm_to_minutes)

		# Scale by factor 10
		params_scale_factor_10 = [
			'PRCP', 'EVAP', 'MDEV', 'MDPR', 'THIC', 'WESD',
			'WESF', 'TMAX', 'TMIN', 'ADPT', 'AWBT', 'MDTN',
			'MDTX', 'MNPN', 'MXPN', 'TAXN', 'TAVG', 'TOBS',
			'ASLP', 'ASTP', 'AWND', 'WSF1', 'WSF2', 'WSF5',
			'WSFG', 'WSFI', 'WSFM', 'FRGB', 'FRGT', 'FRTH',
			'GAHT',
		] \
		+ [f'SN{a}{b}' for a in range(9) for b in range(1,8)] \
		+ [f'SX{a}{b}' for a in range(9) for b in range(1,8)]

		if element in params_scale_factor_10:
			return series.astype(float).div(10.0)

		return series

	def _read_parquet_parallel(self, file_metadata, max_workers=32):
		"""Reads multiple Parquet files in parallel using ThreadPoolExecutor"""
		with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:			
			dfs = list(
				tqdm(
					executor.map(lambda args: self._load_parquet(*args), file_metadata),
					total=len(file_metadata),
					desc="Downloading data",
					unit="file"
					)
			)
		
		return pd.concat(dfs, ignore_index=True)