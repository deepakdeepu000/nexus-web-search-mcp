"""SerpApi Google Search API provider."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..models import WebSearchResult

logger = logging.getLogger(__name__)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class SerpApiError(RuntimeError):
	pass


class SerpApiConfigError(SerpApiError):
	pass


def _get_api_key() -> str:
	key = os.environ.get("SERPAPI_API_KEY", "").strip()
	if not key:
		raise SerpApiConfigError(
			"SERPAPI_API_KEY is not set. Get a key at https://serpapi.com"
		)
	return key


def _as_str(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, str):
		return value.strip()
	return str(value).strip()


def _format_lines(title: str, lines: list[str]) -> str:
	body = "\n".join(line for line in lines if line.strip())
	return f"## {title}\n{body}" if body else ""


def _format_mapping(title: str, data: dict[str, Any], keys: list[str]) -> str:
	lines: list[str] = []
	for key in keys:
		value = data.get(key)
		text = _as_str(value)
		if text:
			label = key.replace("_", " ").title()
			lines.append(f"- {label}: {text}")
	return _format_lines(title, lines)


def _format_link_list(title: str, items: list[dict[str, Any]], limit: int = 8) -> str:
	lines: list[str] = []
	for item in items[:limit]:
		item_title = _as_str(item.get("title")) or _as_str(item.get("text"))
		link = _as_str(item.get("link"))
		if not item_title and not link:
			continue
		if item_title and link:
			lines.append(f"- [{item_title}]({link})")
		elif item_title:
			lines.append(f"- {item_title}")
		else:
			lines.append(f"- {link}")
	return _format_lines(title, lines)


def _format_search_summary(data: dict[str, Any]) -> str:
	sections: list[str] = []

	metadata = data.get("search_metadata")
	if isinstance(metadata, dict):
		sections.append(
			_format_mapping(
				"Search metadata",
				metadata,
				["id", "status", "created_at", "processed_at", "google_url", "raw_html_file", "total_time_taken"],
			)
		)

	parameters = data.get("search_parameters")
	if isinstance(parameters, dict):
		sections.append(
			_format_mapping(
				"Search parameters",
				parameters,
				["engine", "q", "location_requested", "location_used", "google_domain", "device", "gl", "hl", "cr", "lr", "tbm", "start"],
			)
		)

	info = data.get("search_information")
	if isinstance(info, dict):
		sections.append(
			_format_mapping(
				"Search information",
				info,
				["query_displayed", "total_results", "time_taken_displayed", "organic_results_state", "results_for"],
			)
		)

	local_map = data.get("local_map")
	if isinstance(local_map, dict):
		lines = []
		link = _as_str(local_map.get("link"))
		image = _as_str(local_map.get("image"))
		if link:
			lines.append(f"- [Map link]({link})")
		if image:
			lines.append(f"- Image: {image}")
		coords = local_map.get("gps_coordinates")
		if isinstance(coords, dict):
			lat = _as_str(coords.get("latitude"))
			lon = _as_str(coords.get("longitude"))
			if lat or lon:
				lines.append(f"- GPS coordinates: {lat}, {lon}".strip())
		sections.append(_format_lines("Local map", lines))

	local_results = data.get("local_results")
	if isinstance(local_results, dict):
		places = local_results.get("places")
		if isinstance(places, list) and places:
			lines = []
			for place in places[:8]:
				if not isinstance(place, dict):
					continue
				title = _as_str(place.get("title"))
				place_type = _as_str(place.get("type"))
				address = _as_str(place.get("address"))
				rating = _as_str(place.get("rating"))
				reviews = _as_str(place.get("reviews_original") or place.get("reviews"))
				price = _as_str(place.get("price"))
				description = _as_str(place.get("description"))
				parts = [part for part in [title, place_type, address] if part]
				header = " — ".join(parts) if parts else "Local place"
				meta = [value for value in [rating and f"rating {rating}", reviews and f"reviews {reviews}", price] if value]
				line = f"- {header}"
				if meta:
					line += f" ({', '.join(meta)})"
				lines.append(line)
				if description:
					lines.append(f"  - {description}")
			sections.append(_format_lines("Local results", lines))

	knowledge_graph = data.get("knowledge_graph")
	if isinstance(knowledge_graph, dict):
		lines = []
		title = _as_str(knowledge_graph.get("title"))
		kg_type = _as_str(knowledge_graph.get("type"))
		kgmid = _as_str(knowledge_graph.get("kgmid"))
		description = _as_str(knowledge_graph.get("description"))
		source = knowledge_graph.get("source")
		if title:
			lines.append(f"- Title: {title}")
		if kg_type:
			lines.append(f"- Type: {kg_type}")
		if kgmid:
			lines.append(f"- KGMID: {kgmid}")
		if description:
			lines.append(f"- Description: {description}")
		if isinstance(source, dict):
			source_name = _as_str(source.get("name"))
			source_link = _as_str(source.get("link"))
			if source_name and source_link:
				lines.append(f"- Source: [{source_name}]({source_link})")
			elif source_name:
				lines.append(f"- Source: {source_name}")
		sources_include = _as_str(knowledge_graph.get("sources_include"))
		if sources_include:
			lines.append(f"- Sources include: {sources_include}")
		sections.append(_format_lines("Knowledge graph", lines))

	related_questions = data.get("related_questions")
	if isinstance(related_questions, list) and related_questions:
		lines = []
		for question in related_questions[:8]:
			if not isinstance(question, dict):
				continue
			q_title = _as_str(question.get("title"))
			q_text = _as_str(question.get("question"))
			q_snippet = _as_str(question.get("snippet") or question.get("text"))
			q_link = _as_str(question.get("link"))
			header = q_title or q_text or q_link
			if not header:
				continue
			if q_link:
				lines.append(f"- [{header}]({q_link})")
			else:
				lines.append(f"- {header}")
			if q_snippet:
				lines.append(f"  - {q_snippet}")
		sections.append(_format_lines("Related questions", lines))

	perspectives = data.get("perspectives")
	if isinstance(perspectives, list) and perspectives:
		lines = []
		for item in perspectives[:8]:
			if not isinstance(item, dict):
				continue
			title = _as_str(item.get("title"))
			author = _as_str(item.get("author"))
			source = _as_str(item.get("source"))
			date = _as_str(item.get("date"))
			link = _as_str(item.get("link"))
			header = title or author or link
			if not header:
				continue
			if link:
				lines.append(f"- [{header}]({link})")
			else:
				lines.append(f"- {header}")
			meta = [value for value in [author and f"author {author}", source and f"source {source}", date and f"date {date}"] if value]
			if meta:
				lines.append(f"  - {', '.join(meta)}")
		sections.append(_format_lines("Perspectives", lines))

	related_searches = data.get("related_searches")
	if isinstance(related_searches, list) and related_searches:
		sections.append(_format_link_list("Related searches", related_searches, limit=12))

	refine_this_search = data.get("refine_this_search")
	if isinstance(refine_this_search, list) and refine_this_search:
		sections.append(_format_link_list("Refine this search", refine_this_search, limit=12))

	refine_filters = data.get("refine_search_filters")
	if isinstance(refine_filters, list) and refine_filters:
		lines = []
		for group in refine_filters[:10]:
			if not isinstance(group, dict):
				continue
			group_type = _as_str(group.get("type"))
			options = group.get("options")
			if group_type:
				lines.append(f"- {group_type}")
			if isinstance(options, list):
				for option in options[:8]:
					if not isinstance(option, dict):
						continue
					option_title = _as_str(option.get("title"))
					option_link = _as_str(option.get("link"))
					if option_title and option_link:
						lines.append(f"  - [{option_title}]({option_link})")
					elif option_title:
						lines.append(f"  - {option_title}")
		sections.append(_format_lines("Refine search filters", lines))

	things_to_know = data.get("things_to_know")
	if isinstance(things_to_know, dict):
		buttons = things_to_know.get("buttons")
		if isinstance(buttons, list) and buttons:
			lines = []
			for button in buttons[:8]:
				if not isinstance(button, dict):
					continue
				text = _as_str(button.get("text"))
				title = _as_str(button.get("title"))
				link = _as_str(button.get("link"))
				snippet = _as_str(button.get("snippet"))
				header = text or title or link
				if not header:
					continue
				if link:
					lines.append(f"- [{header}]({link})")
				else:
					lines.append(f"- {header}")
				meta = [value for value in [title and f"title {title}", snippet and f"snippet {snippet}"] if value]
				if meta:
					lines.append(f"  - {', '.join(meta)}")
			sections.append(_format_lines("Things to know", lines))

	pagination = data.get("pagination")
	if isinstance(pagination, dict):
		sections.append(
			_format_mapping(
				"Pagination",
				pagination,
				["current", "next"],
			)
		)

	serpapi_pagination = data.get("serpapi_pagination")
	if isinstance(serpapi_pagination, dict):
		sections.append(
			_format_mapping(
				"SerpApi pagination",
				serpapi_pagination,
				["current", "next_link", "next"],
			)
		)

	return "\n\n".join(section for section in sections if section.strip())


def _format_result(item: dict[str, Any], *, shared_context: str = "") -> WebSearchResult | None:
	title = _as_str(item.get("title"))
	link = _as_str(item.get("link"))
	snippet = _as_str(item.get("snippet"))
	if not title or not link:
		return None

	content_parts: list[str] = [
		f"## {title}",
		f"- Link: {link}",
	]

	source = _as_str(item.get("source"))
	displayed_link = _as_str(item.get("displayed_link"))
	if source:
		content_parts.append(f"- Source: {source}")
	if displayed_link:
		content_parts.append(f"- Displayed link: {displayed_link}")
	if snippet:
		content_parts.append(f"- Snippet: {snippet}")

	position = item.get("position")
	if position is not None:
		content_parts.append(f"- Position: {position}")

	sitelinks = item.get("sitelinks")
	if isinstance(sitelinks, dict):
		inline = sitelinks.get("inline")
		if isinstance(inline, list) and inline:
			content_parts.append(_format_link_list("Sitelinks", inline, limit=8))

	rich_snippet = item.get("rich_snippet")
	if isinstance(rich_snippet, dict):
		top = rich_snippet.get("top")
		bottom = rich_snippet.get("bottom")
		for label, value in (("Rich snippet top", top), ("Rich snippet bottom", bottom)):
			if isinstance(value, dict):
				lines = []
				extensions = value.get("extensions")
				if isinstance(extensions, list) and extensions:
					lines.append("- Extensions: " + ", ".join(_as_str(entry) for entry in extensions if _as_str(entry)))
				detected = value.get("detected_extensions")
				if isinstance(detected, dict):
					for key, val in detected.items():
						text = _as_str(val)
						if text:
							lines.append(f"- {key.replace('_', ' ').title()}: {text}")
				block = _format_lines(label, lines)
				if block:
					content_parts.append(block)

	if shared_context:
		content_parts.append(shared_context)

	return WebSearchResult(
		title=title,
		link=link,
		snippet=snippet,
		page_content="\n\n".join(part for part in content_parts if part.strip()),
	)


async def search_serpapi(
	query: str,
	*,
	num_results: int,
	http_client: httpx.AsyncClient | None = None,
) -> list[WebSearchResult]:
	"""Query SerpApi's Google engine and return the most relevant searchable details."""
	if not query.strip() or num_results < 1:
		return []

	api_key = _get_api_key()
	logger.debug(f"Searching SerpApi for query: {query!r} with num_results={num_results}")
	logger.debug(f"Using SERPAPI_API_KEY: {api_key[:4]}***")

	params: dict[str, Any] = {
		"engine": "google",
		"q": query,
		"num": num_results,
		"api_key": api_key,
		"output": "json",
	}

	async def _request(client: httpx.AsyncClient) -> dict[str, Any]:
		resp = await client.get(SERPAPI_ENDPOINT, params=params)
		resp.raise_for_status()
		try:
			data = resp.json()
		except ValueError as exc:
			logger.error("SerpApi returned non-JSON response.")
			raise SerpApiError("SerpApi returned non-JSON response.") from exc
		if not isinstance(data, dict):
			logger.error("SerpApi response was not a JSON object.")
			raise SerpApiError("SerpApi response was not a JSON object.")
		return data

	if http_client is not None:
		data = await _request(http_client)
	else:
		async with httpx.AsyncClient(timeout=30) as client:
			data = await _request(client)

	shared_context = _format_search_summary(data)

	organic = data.get("organic_results")
	if not isinstance(organic, list):
		organic = data.get("organic", [])
	if not isinstance(organic, list):
		organic = []

	results: list[WebSearchResult] = []
	for index, item in enumerate(organic):
		if not isinstance(item, dict):
			continue
		result = _format_result(item, shared_context=shared_context if index == 0 else "")
		if result is None:
			continue
		results.append(result)
		if len(results) >= num_results:
			break

	if not results and shared_context:
		query_label = _as_str(data.get("search_information", {}).get("query_displayed")) if isinstance(data.get("search_information"), dict) else query
		results.append(
			WebSearchResult(
				title=query_label or query,
				link=_as_str(data.get("search_metadata", {}).get("google_url")) if isinstance(data.get("search_metadata"), dict) else "",
				snippet=_as_str(data.get("search_information", {}).get("results_for")) if isinstance(data.get("search_information"), dict) else "",
				page_content=shared_context,
			)
		)

	return results
