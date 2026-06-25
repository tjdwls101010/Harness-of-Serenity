"""Shared utilities for yfinance wrapper scripts."""

import datetime
import functools
import json
import sys

import pandas as pd


def normalize(obj):
	"""Convert pandas/numpy types to JSON-serializable Python objects."""
	if obj is None:
		return None
	if isinstance(obj, bool):
		return obj
	if isinstance(obj, float):
		if obj != obj:  # NaN check
			return None
		return obj
	if isinstance(obj, (str, int)):
		return obj
	if isinstance(obj, (datetime.datetime, datetime.date)):
		return obj.isoformat()
	if isinstance(obj, pd.Timestamp):
		return obj.isoformat()
	if isinstance(obj, pd.Timedelta):
		return str(obj)
	if isinstance(obj, pd.DataFrame):
		if obj.empty:
			return []
		result = {}
		for col in obj.columns:
			result[str(col)] = {str(idx): normalize(val) for idx, val in obj[col].items()}
		return result
	if isinstance(obj, pd.Series):
		return {str(k): normalize(v) for k, v in obj.items()}
	if isinstance(obj, dict):
		return {str(k): normalize(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [normalize(v) for v in obj]
	if hasattr(obj, "item"):  # numpy scalar
		val = obj.item()
		if isinstance(val, float) and val != val:
			return None
		return val
	return str(obj)


def output_json(data):
	"""Serialize data to JSON and print to stdout."""
	json.dump(normalize(data), sys.stdout, ensure_ascii=False, indent=2)
	print()


def error_json(message, code=1):
	"""Output error as JSON and exit."""
	json.dump({"error": str(message)}, sys.stdout, ensure_ascii=False, indent=2)
	print()
	sys.exit(code)


def output_json_records(data):
	"""Serialize data as JSON records format and print to stdout.

	Converts a pandas DataFrame or dict-of-dicts to records format:
	[{col1: val1, col2: val2}, ...] instead of the default column-oriented format.
	For non-DataFrame inputs, delegates to output_json.
	"""
	if isinstance(data, pd.DataFrame):
		if data.empty:
			json.dump([], sys.stdout, ensure_ascii=False, indent=2)
		else:
			records = [{str(col): normalize(row[col]) for col in data.columns} for _, row in data.iterrows()]
			json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
		print()
	else:
		output_json(data)


def safe_run(func):
	"""Decorator: wrap function in try/except with JSON error output."""

	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except SystemExit:
			raise
		except Exception as e:
			error_json(f"{type(e).__name__}: {e}")

	return wrapper
