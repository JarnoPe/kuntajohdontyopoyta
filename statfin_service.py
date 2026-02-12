from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import unicodedata

import requests

MUNICIPALITY_CODES = {
    "KU074": "Halsua",
    "KU236": "Kaustinen",
    "KU421": "Lestijärvi",
    "KU849": "Toholampi",
    "KU924": "Veteli",
}

MUNICIPALITIES = ["Halsua", "Kaustinen", "Toholampi", "Lestijärvi", "Veteli"]
MUNICIPALITY_COLORS = {
    "Halsua": "#8884d8",
    "Kaustinen": "#82ca9d",
    "Toholampi": "#ffc658",
    "Lestijärvi": "#ff8042",
    "Veteli": "#a4de6c",
}

YEARS = ["2020", "2021", "2022", "2023", "2024"]


@dataclass
class SeriesConfig:
    label_keyword: str
    preferred_labels: tuple[str, ...] = ()


def _normalize_label(value: str) -> str:
    base = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()


def _get_coords(index: int, sizes: list[int]) -> list[int]:
    remaining = index
    coords = [0] * len(sizes)
    for i in range(len(sizes) - 1, -1, -1):
        coords[i] = remaining % sizes[i]
        remaining //= sizes[i]
    return coords


def _get_px_metadata(url: str) -> dict[str, Any] | None:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def _post_jsonstat(url: str, query: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post(url, json=query, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def _pick_value_code(variable: dict[str, Any], config: SeriesConfig) -> str | None:
    values = variable.get("values", [])
    value_texts = variable.get("valueTexts", [])
    if not values or not value_texts:
        return None

    preferred_norm = {_normalize_label(label) for label in config.preferred_labels}
    keyword_norm = _normalize_label(config.label_keyword)

    contains_candidates: list[tuple[int, str]] = []

    for code, label in zip(values, value_texts):
        label_norm = _normalize_label(label)

        if label_norm in preferred_norm:
            return code

        if keyword_norm and keyword_norm in label_norm:
            score = 0
            if "%" in label:
                score += 1
            if "," in label:
                score += 1
            if "ika" in label_norm or "vuotia" in label_norm:
                score -= 1
            contains_candidates.append((score, code))

    if contains_candidates:
        return sorted(contains_candidates, key=lambda item: item[0], reverse=True)[0][1]

    return None


def _extract_series(data: dict[str, Any], area_dim: str, year_dim: str):
    dim_ids: list[str] = data["id"]
    sizes: list[int] = data["size"]
    values: list[float | None] = data["value"]

    area_keys = list(data["dimension"][area_dim]["category"]["index"].keys())
    area_labels = data["dimension"][area_dim]["category"]["label"]
    year_keys = list(data["dimension"][year_dim]["category"]["index"].keys())

    rows: list[dict[str, Any]] = []
    for i, value in enumerate(values):
        if value is None:
            continue

        coords = _get_coords(i, sizes)
        dim_map = {dim: coords[idx] for idx, dim in enumerate(dim_ids)}

        area_code = area_keys[dim_map[area_dim]]
        municipality = area_labels[area_code]
        if municipality not in MUNICIPALITIES:
            continue

        year = int(year_keys[dim_map[year_dim]])
        rows.append({"year": year, "municipality": municipality, "value": float(value)})

    return rows


def _rows_to_frame(rows):
    import pandas as pd

    if not rows:
        return pd.DataFrame(columns=["year", "municipality", "value"])

    frame = pd.DataFrame(rows)
    frame = frame.groupby(["year", "municipality"], as_index=False)["value"].sum()
    return frame.sort_values(["year", "municipality"]).reset_index(drop=True)


def _fetch_series_by_label(url: str, config: SeriesConfig):
    metadata = _get_px_metadata(url)
    if not metadata:
        return _rows_to_frame([])

    variables = metadata.get("variables", [])
    if not variables:
        return _rows_to_frame([])

    query_items: list[dict[str, Any]] = []
    matched_metric = False

    for variable in variables:
        code = variable.get("code")
        if not code:
            continue

        code_norm = _normalize_label(code)

        if code == "Alue":
            query_items.append(
                {"code": code, "selection": {"filter": "item", "values": list(MUNICIPALITY_CODES.keys())}}
            )
            continue

        if code == "Vuosi":
            available_years = set(variable.get("values", []))
            selected_years = [year for year in YEARS if year in available_years]
            if not selected_years:
                selected_years = variable.get("values", [])[:1]
            query_items.append({"code": code, "selection": {"filter": "item", "values": selected_years}})
            continue

        metric_code = _pick_value_code(variable, config)
        if metric_code is not None:
            query_items.append({"code": code, "selection": {"filter": "item", "values": [metric_code]}})
            matched_metric = True
            continue

        values = variable.get("values", [])
        if values:
            query_items.append({"code": code, "selection": {"filter": "item", "values": [values[0]]}})

    if not matched_metric:
        return _rows_to_frame([])

    query = {"query": query_items, "response": {"format": "json-stat2"}}
    data = _post_jsonstat(url, query)
    if not data:
        return _rows_to_frame([])

    rows = _extract_series(data, "Alue", "Vuosi")
    return _rows_to_frame(rows)


def fetch_population_data():
    return _fetch_series_by_label(
        "https://pxdata.stat.fi/PxWeb/api/v1/fi/Kuntien_avainluvut/2025/kuntien_avainluvut_2025_aikasarja.px",
        SeriesConfig(label_keyword="Väkiluku", preferred_labels=("Väkiluku",)),
    )


def fetch_employment_data():
    return fetch_employed_18_64_data()


def fetch_employed_18_64_data():
    return _fetch_series_by_label(
        "https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/tyokay/statfin_tyokay_pxt_115x.px",
        SeriesConfig(
            label_keyword="työlliset 18 64",
            preferred_labels=("Työlliset, 18 - 64-vuotiaat", "Työlliset 18-64-vuotiaat"),
        ),
    )


def fetch_unemployment_data():
    return fetch_unemployed_18_64_data()


def fetch_unemployed_18_64_data():
    return _fetch_series_by_label(
        "https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/tyokay/statfin_tyokay_pxt_115x.px",
        SeriesConfig(
            label_keyword="tyottomat 18 64",
            preferred_labels=("Työttömät, 18 - 64-vuotiaat", "Työttömät 18-64-vuotiaat"),
        ),
    )


def fetch_dependency_ratio_data():
    return _fetch_series_by_label(
        "https://pxdata.stat.fi/PxWeb/api/v1/fi/Kuntien_avainluvut/2025/kuntien_avainluvut_2025_aikasarja.px",
        SeriesConfig(
            label_keyword="vaestollinen huoltosuhde",
            preferred_labels=("Väestöllinen huoltosuhde",),
        ),
    )
