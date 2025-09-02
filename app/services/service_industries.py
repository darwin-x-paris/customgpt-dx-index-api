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


def get_industry_companies(industry: str, year: Optional[str] = None, month: Optional[int] = None) -> List[str]:
	"""Return ranked company names for an industry, ordered by ranking asc.

	Falls back to top_companies names if detailed scores are missing.
	"""
	scores = _get_scores_for_industry(industry)
	if scores:
		filtered = _filter_entries(scores, year=year, month=month)
		sorted_scores = sorted(filtered if filtered else scores, key=lambda r: int(r.get("ranking", 10**9)))
		return [str(entry.get("company", "")).strip() for entry in sorted_scores if entry.get("company")]


def get_company_data(company: str, year: Optional[str] = None, month: Optional[int] = None) -> Optional[Dict]:
	"""Search across all industries and return the first ranking entry for a company.

	Adds an "industry" field to the returned dict.
	"""
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


def get_companies_data(company_list: List[str], industry: Optional[str] = None, year: Optional[str] = None, month: Optional[int] = None) -> Dict[str, Optional[Dict]]:
	"""Return a mapping of company name to company data.

	If industry is provided, the search is restricted to that industry.
	"""
	results: Dict[str, Optional[Dict]] = {}
	if not company_list:
		return results

	if industry:
		entries = _filter_entries(_get_scores_for_industry(industry), year=year, month=month) or _get_scores_for_industry(industry)
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
	entries = _get_scores_for_industry(industry)
	entries = _filter_entries(entries, year=year, month=month) or entries
	if not entries:
		return None
	entries_sorted = sorted(entries, key=lambda r: int(r.get("ranking", 10**9)))
	if rank > len(entries_sorted):
		return None
	result = _transform_entry(entries_sorted[rank - 1])
	result["industry"] = industry.upper()
	return result


def search_companies(query: str, limit: int = 25, year: Optional[str] = None, month: Optional[int] = None) -> List[Dict[str, str]]:
	"""Case-insensitive substring search across company names.

	Returns a list of { company, industry, ranking } items.
	"""
	q = query.strip().lower()
	if not q:
		return []
	data = _load_data()
	results: List[Dict[str, str]] = []
	for industry_key, entries in (data.get("scoresData", {}) or {}).items():
		for entry in entries:
			name = str(entry.get("company", ""))
			if q in name.lower() and _matches_year_month(entry, year=year, month=month):
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
	entries = _get_scores_for_industry(industry)
	entries = _filter_entries(entries, year=year, month=month) or entries
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

