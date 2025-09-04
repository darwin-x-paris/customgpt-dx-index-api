from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

import requests


EXTERNAL_INDUSTRIES_URL = "https://index-webapp-app-l4agj.ondigitalocean.app/api/v1/index/industries"


_CACHE: Optional[Dict] = None
_CACHE_TS: Optional[float] = None
_CACHE_TTL_SECONDS: int = 600


def _load_data() -> Dict:
	"""Fetch and cache industries data from the remote endpoint with TTL caching.

	Attempts GET first; if it fails, falls back to POST with an empty JSON body.
	"""
	global _CACHE, _CACHE_TS
	now = time.time()
	if _CACHE is not None and _CACHE_TS is not None and (now - _CACHE_TS) < _CACHE_TTL_SECONDS:
		return _CACHE  # type: ignore[return-value]

	def _fetch_remote() -> Dict:
		resp = requests.post(EXTERNAL_INDUSTRIES_URL, timeout=15)
		if resp.ok:
			resp.raise_for_status()
			return resp.json()

	data = _fetch_remote()
	_CACHE = data
	_CACHE_TS = now
	return data


def get_industries() -> List[str]:
	"""Return the list of industries (e.g., ["CPG", "BANKING"])."""
	data = _load_data()
	industries = data.get("industries") or []
	return list(industries)


def get_industry_overview(industry: str) -> Optional[Dict]:
	"""Return overview object for an industry from data[]."""
	data = _load_data()
	for item in data.get("data", []):
		if str(item.get("name", "")).upper() == industry.upper():
			return item
	return None


def _get_scores_for_industry(industry: str) -> List[Dict]:
	data = _load_data()
	scores = data.get("scoresData", {})
	return list(scores.get(industry.upper(), []))


def _get_latest_period_for_industry(industry: str) -> Optional[Dict[str, object]]:
	"""Return latest { year: str, month: int } for the given industry, or None."""
	periods = get_available_periods(industry=industry)
	if not periods:
		return None
	return periods[-1]


def _get_latest_period_for_company(company: str) -> Optional[Dict[str, object]]:
	"""Return latest { year: str, month: int } where the company appears, or None."""
	needle = company.strip().lower()
	data = _load_data()
	latest_year: Optional[int] = None
	latest_month: Optional[int] = None
	for _industry_key, entries in (data.get("scoresData", {}) or {}).items():
		for entry in entries:
			name = str(entry.get("company", "")).strip().lower()
			if name != needle:
				continue
			try:
				y = int(str(entry.get("year")))
				m = int(str(entry.get("period")))
			except (TypeError, ValueError):
				continue
			if latest_year is None or (y, m) > (latest_year, latest_month or 0):
				latest_year, latest_month = y, m
	if latest_year is None or latest_month is None:
		return None
	return {"year": str(latest_year), "month": int(latest_month)}


def get_industry_companies(industry: str, year: Optional[str] = None, month: Optional[int] = None) -> List[str]:
	"""Return ranked company names for an industry, ordered by ranking asc.

	Falls back to top_companies names if detailed scores are missing.
	"""
	# Default to latest period if no filters provided
	if year is None and month is None:
		latest = _get_latest_period_for_industry(industry)
		if latest:
			year, month = str(latest["year"]), int(latest["month"])  # type: ignore[index]
	scores = _get_scores_for_industry(industry)
	if not scores:
		return []
	filtered = _filter_entries(scores, year=year, month=month)
	if not filtered:
		return []
	sorted_scores = sorted(filtered, key=lambda r: int(r.get("ranking", 10**9)))
	return [str(entry.get("company", "")).strip() for entry in sorted_scores if entry.get("company")]


def get_company_data(company: str, year: Optional[str] = None, month: Optional[int] = None) -> Optional[Dict]:
	"""Search across all industries and return the first ranking entry for a company.

	Adds an "industry" field to the returned dict.
	"""
	# If no period specified, pick the latest available period for this company
	if year is None and month is None:
		latest = _get_latest_period_for_company(company)
		if latest:
			year, month = str(latest["year"]), int(latest["month"])  # type: ignore[index]
	needle = company.strip().lower()
	data = _load_data()
	for industry_key, entries in (data.get("scoresData", {}) or {}).items():
		for entry in entries:
			name = str(entry.get("company", "")).strip().lower()
			if name == needle and _matches_year_month(entry, year=year, month=month):
				result = _transform_entry(entry)
				result["industry"] = industry_key
				return result
	return None


def get_company_entries(company: str, year: Optional[str] = None, month: Optional[int] = None) -> List[Dict]:
	"""Return all ranking entries for a company across industries and periods.

	Adds an "industry" field to each returned dict.
	Optionally filters by year and/or month.
	"""
	needle = company.strip().lower()
	data = _load_data()
	results: List[Dict] = []
	for industry_key, entries in (data.get("scoresData", {}) or {}).items():
		for entry in entries:
			name = str(entry.get("company", "")).strip().lower()
			if name == needle and _matches_year_month(entry, year=year, month=month):
				result = _transform_entry(entry)
				result["industry"] = industry_key
				results.append(result)
	return results


def get_companies_data(company_list: List[str], industry: Optional[str] = None, year: Optional[str] = None, month: Optional[int] = None) -> Dict[str, Optional[Dict]]:
	"""Return a mapping of company name to company data.

	If industry is provided, the search is restricted to that industry.
	"""
	results: Dict[str, Optional[Dict]] = {}
	if not company_list:
		return results

	if industry:
		# Default to latest industry period when not provided
		if year is None and month is None:
			latest = _get_latest_period_for_industry(industry)
			if latest:
				year, month = str(latest["year"]), int(latest["month"])  # type: ignore[index]
		entries = _filter_entries(_get_scores_for_industry(industry), year=year, month=month)
		index = {str(e.get("company", "")).strip().lower(): e for e in entries}
		for name in company_list:
			key = name.strip().lower()
			entry = index.get(key)
			if entry:
				val = _transform_entry(entry)
				val["industry"] = industry.upper()
				results[name] = val
			else:
				results[name] = None
		return results

	# Global search
	for name in company_list:
		results[name] = get_company_data(name, year=year, month=month)
	return results


def get_company_nth_rank(rank: int, industry: str, year: Optional[str] = None, month: Optional[int] = None) -> Optional[Dict]:
	"""Return the company ranking entry at position `rank` (1-based) for an industry."""
	if rank <= 0:
		return None
	if year is None and month is None:
		latest = _get_latest_period_for_industry(industry)
		if latest:
			year, month = str(latest["year"]), int(latest["month"])  # type: ignore[index]
	entries = _get_scores_for_industry(industry)
	entries = _filter_entries(entries, year=year, month=month)
	if not entries:
		return None
	entries_sorted = sorted(entries, key=lambda r: int(r.get("ranking", 10**9)))
	if rank > len(entries_sorted):
		return None
	result = _transform_entry(entries_sorted[rank - 1])
	result["industry"] = industry.upper()
	return result


def search_companies(company: str, limit: int = 25, year: Optional[str] = None, month: Optional[int] = None) -> List[Dict[str, str]]:
	"""Case-insensitive substring search across company names.

	Returns a list of { company, industry, ranking } items.
	"""
	company = company.strip().lower()
	if not company:
		return []
	data = _load_data()

	# If no explicit period provided, restrict to the latest period per industry
	latest_by_industry: Dict[str, Optional[Dict[str, object]]] = {}
	if year is None and month is None:
		for industry_key in (data.get("industries") or []):
			latest_by_industry[industry_key] = _get_latest_period_for_industry(industry_key)
	results: List[Dict[str, str]] = []
	for industry_key, entries in (data.get("scoresData", {}) or {}).items():
		for entry in entries:
			name = str(entry.get("company", ""))
			# Determine effective year/month for this industry
			_eff_year: Optional[str]
			_eff_month: Optional[int]
			if year is None and month is None:
				latest = latest_by_industry.get(industry_key)
				_eff_year = str(latest["year"]) if latest else None  # type: ignore[index]
				_eff_month = int(latest["month"]) if latest else None  # type: ignore[index]
			else:
				_eff_year, _eff_month = year, month
			if company in name.lower() and _matches_year_month(entry, year=_eff_year, month=_eff_month):
				results.append({
					"company": name,
					"industry": industry_key,
					"ranking": entry.get("ranking"),
				})
				if len(results) >= limit:
					return results
	return results


def get_industry_rankings(industry: str, limit: Optional[int] = None, offset: int = 0, year: Optional[str] = None, month: Optional[int] = None) -> List[Dict]:
	"""Return sorted ranking entries for an industry with optional pagination.

	Entries are sorted by ascending ranking. If limit is provided, results are sliced
	from offset to offset+limit.
	"""
	if year is None and month is None:
		latest = _get_latest_period_for_industry(industry)
		if latest:
			year, month = str(latest["year"]), int(latest["month"])  # type: ignore[index]
	entries = _get_scores_for_industry(industry)
	entries = _filter_entries(entries, year=year, month=month)
	if not entries:
		return []
	entries_sorted = sorted(entries, key=lambda r: int(r.get("ranking", 10**9)))
	if offset < 0:
		offset = 0
	if limit is None:
		return [dict(_transform_entry(e), industry=industry.upper()) for e in entries_sorted[offset:]]
	end = max(0, offset) + max(0, limit)
	return [dict(_transform_entry(e), industry=industry.upper()) for e in entries_sorted[offset:end]]


def get_top_companies(industry: str) -> List[Dict]:
	"""Return the `top_companies` list from the industry overview, if available."""
	overview = get_industry_overview(industry)
	if not overview:
		return []
	return list(overview.get("top_companies", []) or [])


def get_available_periods(industry: Optional[str] = None) -> List[Dict]:
	"""Return unique available { year, month } combinations.

	If `industry` is provided, the set is restricted to that industry's entries.
	"""
	data = _load_data()
	pairs = set()
	if industry:
		entries = data.get("scoresData", {}).get(industry.upper(), []) or []
		iter_entries = entries
	else:
		iter_entries = []
		for _industry, entries in (data.get("scoresData", {}) or {}).items():
			iter_entries.extend(entries)
	for entry in iter_entries:
		year_val = entry.get("year")
		period_val = entry.get("period")
		if year_val is None or period_val is None:
			continue
		try:
			month_int = int(period_val)
			year_str = str(year_val)
		except (TypeError, ValueError):
			continue
		pairs.add((year_str, month_int))
	# sort chronologically: year asc, month asc
	sorted_pairs = sorted(list(pairs), key=lambda p: (int(p[0]) if str(p[0]).isdigit() else 0, int(p[1])))
	return [{"year": y, "month": m} for (y, m) in sorted_pairs]


def _matches_year_month(entry: Dict, year: Optional[str], month: Optional[int]) -> bool:
	"""Return True if the entry matches the optional year/month filters."""
	if year is not None:
		if str(entry.get("year")) != str(year):
			return False
	if month is not None:
		try:
			if int(entry.get("period")) != int(month):
				return False
		except (TypeError, ValueError):
			return False
	return True


def _filter_entries(entries: List[Dict], year: Optional[str], month: Optional[int]) -> List[Dict]:
	"""Filter entries by optional year and month."""
	if year is None and month is None:
		return entries
	return [e for e in entries if _matches_year_month(e, year, month)]


def _transform_entry(entry: Dict) -> Dict:
	"""Transform a raw entry to API shape: rename 'period' -> 'month'."""
	out = dict(entry)
	if "period" in out:
		out["month"] = out.pop("period")
	return out



def get_discover_schema() -> Dict:
	"""Return live discovery info: industries, inferred schemas, and live examples.

	The payload is built from the current index data. A compact "schema" is
	inferred from live example objects by inspecting their fields and mapping
	Python types to human-friendly strings.
	"""
	data = _load_data()
	industries: List[str] = list(data.get("industries") or [])

	representative_industry: Optional[str] = industries[0] if industries else None

	# Live examples
	overview_example: Optional[Dict] = get_industry_overview(representative_industry) if representative_industry else None
	company_ranking_example: Optional[Dict] = None
	for industry_key, entries in (data.get("scoresData", {}) or {}).items():
		if entries:
			company_ranking_example = dict(_transform_entry(entries[0]), industry=industry_key)
			break
	periods_example: List[Dict] = get_available_periods()

	# Top companies example list
	top_companies_list: List[Dict] = []
	if representative_industry:
		top_companies_list = get_top_companies(representative_industry)
	if not top_companies_list and isinstance(overview_example, dict):
		maybe = overview_example.get("top_companies")
		if isinstance(maybe, list):
			top_companies_list = list(maybe)

	# Per-industry available periods
	periods_by_industry: Dict[str, List[Dict]] = {}
	for ind in industries:
		periods_by_industry[ind] = get_available_periods(industry=ind)

	return {
		"industries": industries,
		"examples": {
			"overview": overview_example,
			"company_ranking": company_ranking_example,
			"top_companies": top_companies_list,
			"periods": periods_example,
			"periods_by_industry": periods_by_industry,
		},
	}
