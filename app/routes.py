from flask import Blueprint, jsonify, request, current_app

from .services.service_industries import (
	get_industries,
	get_industry_companies,
	get_company_data,
	get_company_entries,
	get_companies_data,
	get_company_nth_rank,
	get_industry_rankings,
	get_top_companies,
	get_industry_overview,
	search_companies,
	get_available_periods,
	get_discover_schema,
)


api_bp = Blueprint('api', __name__)


@api_bp.before_request
def _enforce_bearer_token():
	# Allow unauthenticated access to the health check endpoint
	if request.endpoint == 'api.health_check':
		return None
	expected_key = current_app.config.get('API_KEY')
	if not expected_key:
		return jsonify({"error": "Unauthorized"}), 401
	auth_header = request.headers.get('Authorization', '')
	prefix = 'Bearer '
	if not auth_header.startswith(prefix):
		return jsonify({"error": "Unauthorized"}), 401
	provided_key = auth_header[len(prefix):]
	if provided_key != expected_key:
		return jsonify({"error": "Forbidden"}), 403


@api_bp.get('/')
def health_check():
	return "Healthy.", 200



# @api_bp.post('/industries')
# def industries():
# 	request_data = request.get_json(silent=True) or {}
# 	success, payload, status = fetch_industries(request_data)
# 	return jsonify(payload), status


@api_bp.get('/industries')
def api_get_industries():
	return jsonify({"industries": get_industries()}), 200


@api_bp.get('/industry/<string:industry>/companies')
def api_get_industry_companies(industry: str):
	year = request.args.get('year', default=None, type=str)
	month = request.args.get('month', default=None, type=int)
	companies = get_industry_companies(industry, year=year, month=month)
	return jsonify({"industry": industry.upper(), "year": year, "month": month, "companies": companies}), 200


@api_bp.get('/company')
def api_get_company():
	name = request.args.get('name')
	year = request.args.get('year', default=None, type=str)
	month = request.args.get('month', default=None, type=int)
	if not name:
		return jsonify({"error": "Query parameter 'name' is required"}), 400
	# When no year/month filters are specified, return ALL entries for the company
	if year is None and month is None:
		items = get_company_entries(name)
		if not items:
			return jsonify({"error": f"Company not found: {name}"}), 404
		return jsonify({"company": name, "results": items}), 200
	# Otherwise return the single matching entry
	data = get_company_data(name, year=year, month=month)
	if not data:
		return jsonify({"error": f"Company not found: {name}"}), 404
	return jsonify(data), 200


@api_bp.post('/companies')
def api_get_companies():
	body = request.get_json(silent=True) or {}
	current_app.logger.info("POST %s body=%s", request.path, body)
	companies = body.get('companies')
	industry = body.get('industry')
	year = body.get('year')
	month = body.get('month')
	if not isinstance(companies, list) or not all(isinstance(x, str) for x in companies):
		return jsonify({"error": "Request JSON must include 'companies': [string, ...]"}), 400
	if month is not None:
		try:
			month = int(month)
		except (TypeError, ValueError):
			return jsonify({"error": "'month' must be an integer if provided"}), 400
	results = get_companies_data(companies, industry=industry, year=year, month=month)
	return jsonify({"industry": (industry.upper() if industry else None), "year": year, "month": month, "results": results}), 200


@api_bp.get('/industry/<string:industry>/rank/<int:rank>')
def api_get_company_nth_rank(industry: str, rank: int):
	year = request.args.get('year', default=None, type=str)
	month = request.args.get('month', default=None, type=int)
	data = get_company_nth_rank(rank, industry, year=year, month=month)
	if not data:
		return jsonify({"error": "Not found"}), 404
	return jsonify(data), 200


@api_bp.get('/industry/<string:industry>/rankings')
def api_get_industry_rankings(industry: str):
	year = request.args.get('year', default=None, type=str)
	month = request.args.get('month', default=None, type=int)
	try:
		limit = request.args.get('limit', default=None, type=int)
		if limit is not None and limit < 0:
			return jsonify({"error": "'limit' must be >= 0"}), 400
		offset = request.args.get('offset', default=0, type=int)
		if offset < 0:
			return jsonify({"error": "'offset' must be >= 0"}), 400
	except (TypeError, ValueError):
		return jsonify({"error": "Invalid 'limit' or 'offset'"}), 400
	items = get_industry_rankings(industry, limit=limit, offset=offset, year=year, month=month)
	return jsonify({
		"industry": industry.upper(),
		"year": year,
		"month": month,
		"limit": limit,
		"offset": offset,
		"results": items,
	}), 200


@api_bp.get('/industry/<string:industry>/overview')
def api_get_industry_overview(industry: str):
	overview = get_industry_overview(industry)
	if not overview:
		return jsonify({"error": "Industry not found"}), 404
	return jsonify(overview), 200


@api_bp.get('/industry/<string:industry>/top-companies')
def api_get_top_companies(industry: str):
	items = get_top_companies(industry)
	return jsonify({"industry": industry.upper(), "top_companies": items}), 200


@api_bp.get('/search/companies')
def api_search_companies():
	company = request.args.get('company', default=None, type=str)
	limit = request.args.get('limit', default=25, type=int)
	year = request.args.get('year', default=None, type=str)
	month = request.args.get('month', default=None, type=int)
	if not company:
		return jsonify({"error": "Query parameter 'company' is required"}), 400
	if limit <= 0:
		return jsonify({"error": "'limit' must be > 0"}), 400
	results = search_companies(company, limit=limit, year=year, month=month)
	return jsonify({"company": company, "year": year, "month": month, "limit": limit, "results": results}), 200


@api_bp.get('/periods')
def api_get_periods():
	industry = request.args.get('industry', default=None, type=str)
	items = get_available_periods(industry=industry)
	return jsonify({"industry": (industry.upper() if industry else None), "periods": items}), 200


@api_bp.get('/discover')
def api_discover():
	data = get_discover_schema()
	return jsonify(data), 200





