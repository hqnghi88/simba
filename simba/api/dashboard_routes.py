from typing import List, Optional, Any
import os
import json
import re
import asyncio
from datetime import datetime
import logging
import httpx

from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict

from simba.core.factories.database_factory import get_database
from simba.core.config import settings

logger = logging.getLogger(__name__)

dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])

KPI_STORAGE_FILE = os.path.join(settings.paths.base_dir, "dashboard_kpis.json")

# --- 13 KPI Categories ---
KPI_CATEGORIES = [
    "Productivity", "Value added", "Income", "Soil quality",
    "Exposure to pesticides", "Women's empowerment", "Youth empowerment",
    "Adaptive capacity", "Social Justice", "Human well-being",
    "Nutrient management", "Crop health", "Water sources",
]

CHAINS = ["Mango", "Rice-lotus", "Rice-shrimp", "Coconut"]
GROUPS = ["Worse-off", "Better-off", "Cooperative", "Independent"]


# --- Data Models ---
class KPIEntry(BaseModel):
    chain: str
    kpi: str
    indicator: str
    unit: str = ""
    group: str
    median: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    rate: Optional[float] = None


class KPIExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    is_stale: bool = False
    last_updated: Optional[str] = None
    source_doc_ids: List[str] = []
    chains: dict[str, list[KPIEntry]] = {}


# --- Storage helpers ---
def load_kpis() -> dict:
    if os.path.exists(KPI_STORAGE_FILE):
        try:
            with open(KPI_STORAGE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading KPIs: {e}")
    return {}


def save_kpis(data: dict):
    try:
        data["last_updated"] = datetime.now().isoformat()
        with open(KPI_STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving KPIs: {e}")


# --- LLM Extraction (direct Ollama API, no langchain) ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", settings.llm.base_url)


def _ollama_generate(prompt: str, timeout: int = 120) -> str:
    """Call Ollama API directly with stream=false for reliable non-streaming response."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.llm.model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "num_predict": 4096,
            "temperature": settings.llm.temperature,
        },
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        return ""


CHAIN_PROMPT = """Read the following document carefully. Understand its content and extract any agricultural KPI baseline data relevant to the "{chain}" value chain.

KPI categories: Productivity, Value added, Income, Soil quality, Exposure to pesticides, Women's empowerment, Youth empowerment, Adaptive capacity, Social Justice, Human well-being, Nutrient management, Crop health, Water sources

Groups of interest: Worse-off, Better-off, Cooperative, Independent

For each piece of KPI data you find in the document — regardless of how it is formatted (tables, paragraphs, bullet points, labels, etc.) — create a JSON entry:
{{"kpi":"best matching category","indicator":"what is being measured","unit":"unit if found","group":"which group","median":value,"p25":null,"p75":null,"rate":null}}

Use your understanding of the document to:
- Determine which KPI category each data point belongs to
- Identify which group (Worse-off, Better-off, Cooperative, Independent) each value applies to
- Place numeric values in the "median" field
- If a percentage or rate is found, use the "rate" field

Return ONLY a JSON array of entries. One entry per data point per group.

Document:
{context}

JSON:"""


def _build_context_from_docs(enabled_docs: list, chain_filter: str = "") -> tuple[str, list[str]]:
    """Build context text from enabled documents, optionally filtered by chain."""
    context_text = ""
    docs_used = []

    def get_doc_ts(d):
        return d.metadata.parsed_at or d.metadata.uploadedAt or ""

    sorted_docs = sorted(enabled_docs, key=get_doc_ts, reverse=True)

    for doc in sorted_docs[:5]:
        content = ""
        if hasattr(doc, "documents") and doc.documents and len(doc.documents) > 0:
            content = doc.documents[0].page_content
        elif hasattr(doc, "content") and doc.content:
            content = doc.content[:1500]

        if content:
            context_text += f"\n--- {doc.metadata.filename} ---\n{content[:1500]}\n"
            docs_used.append(doc.metadata.filename)

    return context_text, docs_used


def _normalize_group(g: str) -> str:
    """Normalize group name to match frontend format."""
    g_lower = g.lower().strip()
    # Remove punctuation and extra spaces
    g_clean = re.sub(r'[–—\-_]', ' ', g_lower).strip()
    g_clean = re.sub(r'\s+', ' ', g_clean)
    
    mapping = {
        "worse off": "Worse \u2013 off",
        "worse": "Worse \u2013 off",
        "woff": "Worse \u2013 off",
        "better off": "Better \u2013 off",
        "better": "Better \u2013 off",
        "boff": "Better \u2013 off",
        "cooperative": "Cooperative",
        "coop": "Cooperative",
        "independent": "Independent",
        "indep": "Independent",
    }
    return mapping.get(g_clean, mapping.get(g_lower, g))


def _normalize_chain(c: str) -> str:
    """Normalize chain name."""
    c_lower = c.lower().strip()
    mapping = {
        "mango": "Mango",
        "rice-lotus": "Rice-lotus",
        "rice lotus": "Rice-lotus",
        "rice_lotus": "Rice-lotus",
        "rice-shrimp": "Rice - shrimp",
        "rice shrimp": "Rice - shrimp",
        "rice_shrimp": "Rice - shrimp",
        "coconut": "Coconut",
    }
    return mapping.get(c_lower, c)


def _parse_json_from_llm(raw: str) -> list:
    """Extract JSON array from LLM output, handling markdown fences etc."""
    stripped = raw.strip()
    if "```json" in stripped:
        stripped = stripped.split("```json")[1].split("```")[0].strip()
    elif "```" in stripped:
        stripped = stripped.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            for key in ["data", "entries", "kpis", "results"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return []


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def extract_kpis_from_docs(
    context_text: str, docs_used: list[str], doc_ids: list[str]
) -> dict:
    """Use LLM to extract KPI data from documents (synchronous, one chain at a time)."""
    if not context_text.strip():
        return {"chains": {}, "source_doc_ids": doc_ids}

    all_entries = []

    for chain_name in CHAINS:
        logger.info(f"Extracting KPIs for chain: {chain_name}")
        prompt = CHAIN_PROMPT.format(chain=chain_name, context=context_text)
        raw_output = _ollama_generate(prompt, timeout=120)
        logger.info(f"LLM output for {chain_name} ({len(raw_output)} chars): {raw_output[:200]}")

        entries = _parse_json_from_llm(raw_output)
        for entry in entries:
            if isinstance(entry, dict):
                chain = _normalize_chain(entry.get("chain", chain_name))
                group = _normalize_group(entry.get("group", ""))
                normalized = {
                    "chain": chain,
                    "kpi": entry.get("kpi", ""),
                    "indicator": entry.get("indicator", ""),
                    "unit": entry.get("unit", ""),
                    "group": group,
                    "median": _to_float(entry.get("median")),
                    "p25": _to_float(entry.get("p25")),
                    "p75": _to_float(entry.get("p75")),
                    "rate": _to_float(entry.get("rate")),
                }
                all_entries.append(normalized)

    # Build chain -> entries dict
    chains_dict: dict[str, list[dict]] = {}
    for entry in all_entries:
        chain = entry.get("chain", "")
        if chain not in chains_dict:
            chains_dict[chain] = []
        chains_dict[chain].append(entry)

    return {"chains": chains_dict, "source_doc_ids": doc_ids}


# --- Baseline Excel data (always used as foundation) ---
BASELINE_FILE = os.path.join(
    settings.paths.base_dir, "frontend", "public", "kpi_data.json"
)


def load_baseline() -> dict[str, list[dict]]:
    """Load the Excel baseline KPI data as chain -> entries dict."""
    if not os.path.exists(BASELINE_FILE):
        logger.warning(f"Baseline file not found: {BASELINE_FILE}")
        return {}
    try:
        with open(BASELINE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading baseline: {e}")
        return {}


def _merge_with_baseline(baseline: dict, llm_chains: dict) -> dict:
    """Merge LLM-extracted data into baseline.
    
    - Start with ALL baseline entries
    - For each LLM entry, find a matching baseline entry (by kpi+indicator+group)
    - If LLM has a non-null value, update the baseline entry
    - If LLM value is null/missing, keep baseline unchanged
    - Add any new indicators from LLM that don't exist in baseline
    """
    merged: dict[str, list[dict]] = {}

    for chain_name, baseline_entries in baseline.items():
        chain_key = _normalize_chain(chain_name)
        merged[chain_key] = [dict(e) for e in baseline_entries]

        llm_entries = llm_chains.get(chain_name, []) or llm_chains.get(chain_key, [])

        for llm_entry in llm_entries:
            llm_kpi = llm_entry.get("kpi", "")
            llm_indicator = llm_entry.get("indicator", "")
            llm_group = _normalize_group(llm_entry.get("group", ""))

            if not llm_kpi or not llm_indicator:
                continue

            # Find matching baseline entry
            matched = False
            for base_entry in merged[chain_key]:
                base_kpi = base_entry.get("kpi", "")
                base_indicator = base_entry.get("indicator", "")
                base_group = _normalize_group(base_entry.get("group", ""))

                # Match by kpi + indicator (fuzzy) + group
                kpi_match = base_kpi == llm_kpi
                group_match = base_group == llm_group
                # Fuzzy indicator match: LLM indicator contains baseline indicator or vice versa
                ind_match = (
                    base_indicator == llm_indicator
                    or llm_indicator.lower().startswith(base_indicator.lower())
                    or base_indicator.lower().startswith(llm_indicator.lower())
                    or base_indicator.lower() in llm_indicator.lower()
                    or llm_indicator.lower() in base_indicator.lower()
                )

                if kpi_match and group_match and ind_match:
                    # Update only non-null LLM values
                    for field in ["median", "p25", "p75", "rate"]:
                        llm_val = _to_float(llm_entry.get(field))
                        if llm_val is not None and llm_val != 0:
                            base_entry[field] = llm_val
                    matched = True
                    break

            if not matched:
                # New indicator not in baseline — add it
                new_entry = {
                    "chain": chain_key,
                    "kpi": llm_kpi,
                    "indicator": llm_indicator,
                    "unit": llm_entry.get("unit", ""),
                    "group": llm_group,
                    "median": _to_float(llm_entry.get("median")),
                    "p25": _to_float(llm_entry.get("p25")),
                    "p75": _to_float(llm_entry.get("p75")),
                    "rate": _to_float(llm_entry.get("rate")),
                }
                merged[chain_key].append(new_entry)

    # Also add chains from LLM that don't exist in baseline
    for chain_name, llm_entries in llm_chains.items():
        chain_key = _normalize_chain(chain_name)
        if chain_key not in merged:
            merged[chain_key] = []
            for llm_entry in llm_entries:
                merged[chain_key].append({
                    "chain": chain_key,
                    "kpi": llm_entry.get("kpi", ""),
                    "indicator": llm_entry.get("indicator", ""),
                    "unit": llm_entry.get("unit", ""),
                    "group": _normalize_group(llm_entry.get("group", "")),
                    "median": _to_float(llm_entry.get("median")),
                    "p25": _to_float(llm_entry.get("p25")),
                    "p75": _to_float(llm_entry.get("p75")),
                    "rate": _to_float(llm_entry.get("rate")),
                })

    return merged


# --- API Endpoints ---
@dashboard.get("/kpi", response_model=KPIExtractionResponse)
async def get_kpis():
    """Get KPI data: baseline + any LLM adjustments."""
    baseline = load_baseline()
    cached_data = load_kpis()

    # If no cached extraction yet, just return baseline
    if not cached_data.get("chains"):
        enriched = {}
        for chain_name, entries in baseline.items():
            chain_key = _normalize_chain(chain_name)
            enriched[chain_key] = [
                KPIEntry(chain=chain_key, **{k: v for k, v in e.items() if k != "chain"})
                for e in entries
            ]
        response = KPIExtractionResponse(chains=enriched)
        response.is_stale = False
        return response

    # Merge cached LLM data on top of baseline
    merged = _merge_with_baseline(baseline, cached_data.get("chains", {}))

    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]

    response = KPIExtractionResponse(
        chains={k: [KPIEntry(chain=k, **{kk: vv for kk, vv in e.items() if kk != "chain"}) for e in v] for k, v in merged.items()},
        source_doc_ids=cached_data.get("source_doc_ids", []),
        last_updated=cached_data.get("last_updated"),
    )

    # Staleness check
    current_ids = sorted([d.id for d in enabled_docs])
    cached_ids = sorted(cached_data.get("source_doc_ids", []))
    response.is_stale = current_ids != cached_ids

    return response


@dashboard.post("/kpi/recalculate", response_model=KPIExtractionResponse)
async def recalculate_kpis():
    """Recalculate: run LLM extraction, merge with baseline (baseline always preserved)."""
    logger.info("Recalculating KPI extraction...")
    start_time = datetime.now()

    baseline = load_baseline()
    if not baseline:
        logger.error("No baseline data found.")
        return KPIExtractionResponse()

    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    current_ids = [d.id for d in enabled_docs]

    logger.info(f"Found {len(enabled_docs)} enabled documents for KPI extraction.")

    llm_chains = {}
    if enabled_docs:
        context_text, docs_used = _build_context_from_docs(enabled_docs)
        logger.info(f"Context built from {len(docs_used)} documents: {', '.join(docs_used)}")

        if context_text.strip():
            try:
                result = await asyncio.to_thread(
                    extract_kpis_from_docs, context_text, docs_used, current_ids
                )
                llm_chains = result.get("chains", {})
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"LLM extraction completed in {elapsed:.2f}s. Chains: {list(llm_chains.keys())}")
            except Exception as e:
                logger.error(f"LLM extraction error: {e}", exc_info=True)
        else:
            logger.warning("Context text empty, skipping LLM extraction.")

    # ALWAYS merge with baseline — baseline values are preserved
    merged = _merge_with_baseline(baseline, llm_chains)

    response_data = {
        "chains": {k: v for k, v in merged.items()},
        "source_doc_ids": current_ids,
    }
    save_kpis(response_data)

    response = KPIExtractionResponse(
        chains={k: [KPIEntry(chain=k, **{kk: vv for kk, vv in e.items() if kk != "chain"}) for e in v] for k, v in merged.items()},
        source_doc_ids=current_ids,
        last_updated=datetime.now().isoformat(),
    )
    response.is_stale = False
    return response
