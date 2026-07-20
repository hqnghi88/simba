from typing import List, Optional, Any
import os
import json
import re
import asyncio
import uuid
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
KPI_PENDING_FILE = os.path.join(settings.paths.base_dir, "dashboard_kpi_pending.json")

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


class KPIPendingEntry(BaseModel):
    id: str
    chain: str
    kpi: str
    indicator: str
    unit: str = ""
    group: str
    median: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    rate: Optional[float] = None
    baseline_median: Optional[float] = None
    baseline_p25: Optional[float] = None
    baseline_p75: Optional[float] = None
    baseline_rate: Optional[float] = None
    is_new: bool = False
    approved: bool = True


class KPIExtractionReviewResponse(BaseModel):
    pending_id: str
    entries: List[KPIPendingEntry] = []
    source_doc_ids: List[str] = []
    extracted_at: str = ""


class KPIApplyRequest(BaseModel):
    pending_id: str
    approved_ids: List[str]


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


def save_pending(data: dict):
    try:
        with open(KPI_PENDING_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving pending KPIs: {e}")


def load_pending() -> dict:
    if os.path.exists(KPI_PENDING_FILE):
        try:
            with open(KPI_PENDING_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading pending KPIs: {e}")
    return {}


# --- LLM Extraction (direct API, no langchain) ---
LLM_BASE_URL = os.environ.get("OLLAMA_HOST", settings.llm.base_url)


def _llm_generate(prompt: str, timeout: int = 120) -> str:
    """Call LLM API directly, supports both Ollama and vLLM (OpenAI-compatible)."""
    provider = settings.llm.provider

    if provider == "vllm":
        base_url = LLM_BASE_URL.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        url = f"{base_url}/chat/completions"
        payload = {
            "model": settings.llm.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens or 4096,
            "stream": False,
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"vLLM API error: {e}")
            return ""
    else:
        url = f"{LLM_BASE_URL}/api/generate"
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


CHAIN_PROMPT = """Read the following document carefully. Understand its content and extract ALL agricultural KPI baseline data found.

Value chains: Mango, Rice-lotus, Rice-shrimp, Coconut
KPI categories: Productivity, Value added, Income, Soil quality, Exposure to pesticides, Women's empowerment, Youth empowerment, Adaptive capacity, Social Justice, Human well-being, Nutrient management, Crop health, Water sources
Groups of interest: Worse-off, Better-off, Cooperative, Independent

For each piece of KPI data you find, create a JSON entry:
{{"chain":"which value chain (Mango, Rice-lotus, Rice-shrimp, or Coconut)","kpi":"best matching category","indicator":"what is being measured","unit":"unit if found","group":"which group","median":value,"p25":null,"p75":null,"rate":null}}

Rules:
- ONLY extract data that is explicitly stated in the document
- Assign each data point to the correct value chain based on the document context
- If the document only discusses one chain, only return entries for that chain
- Do NOT invent or repeat data for chains not mentioned in the document

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
    """Use LLM to extract KPI data from documents (single call)."""
    if not context_text.strip():
        return {"chains": {}, "source_doc_ids": doc_ids}

    # Detect which chains are actually mentioned in the document
    mentioned_chains = _detect_chains_in_text(context_text)
    logger.info(f"Chains detected in document: {mentioned_chains}")

    logger.info("Extracting KPIs (single LLM call)...")
    prompt = CHAIN_PROMPT.format(context=context_text)
    raw_output = _llm_generate(prompt, timeout=120)
    logger.info(f"LLM output ({len(raw_output)} chars): {raw_output[:300]}")

    entries = _parse_json_from_llm(raw_output)
    chains_dict: dict[str, list[dict]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        chain = _normalize_chain(entry.get("chain", ""))
        if not chain:
            continue
        # Filter: only keep entries for chains actually mentioned in the document
        if chain not in mentioned_chains:
            logger.info(f"Discarding LLM entry for unmentioned chain '{chain}': {entry.get('indicator', '')}")
            continue
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
        if chain not in chains_dict:
            chains_dict[chain] = []
        chains_dict[chain].append(normalized)

    return {"chains": chains_dict, "source_doc_ids": doc_ids}


def _detect_chains_in_text(text: str) -> set[str]:
    """Detect which value chains are actually mentioned in the document text."""
    text_lower = text.lower()
    chain_keywords = {
        "Mango": ["mango"],
        "Rice-lotus": ["rice-lotus", "rice lotus", "rice_lotus", "lúa - sen", "lúa sen", "lúa sen"],
        "Rice - shrimp": ["rice-shrimp", "rice shrimp", "rice_shrimp", "lúa - tôm", "lúa tôm"],
        "Coconut": ["coconut", "dừa"],
    }
    detected = set()
    for chain, keywords in chain_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                detected.add(chain)
                break
    return detected


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

    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    current_ids = sorted([d.id for d in enabled_docs])

    # Staleness check: if enabled docs changed, discard cached LLM data
    cached_ids = sorted(cached_data.get("source_doc_ids", []))
    is_stale = current_ids != cached_ids
    if is_stale and cached_data.get("chains"):
        save_kpis({"chains": {}, "source_doc_ids": current_ids})
        cached_data = {"chains": {}, "source_doc_ids": current_ids}
        logger.info("Documents changed, cleared stale LLM data.")

    if not cached_data.get("chains"):
        enriched = {}
        for chain_name, entries in baseline.items():
            chain_key = _normalize_chain(chain_name)
            enriched[chain_key] = [
                KPIEntry(chain=chain_key, **{k: v for k, v in e.items() if k != "chain"})
                for e in entries
            ]
        response = KPIExtractionResponse(chains=enriched)
        response.is_stale = is_stale
        return response

    merged = _merge_with_baseline(baseline, cached_data.get("chains", {}))
    response = KPIExtractionResponse(
        chains={k: [KPIEntry(chain=k, **{kk: vv for kk, vv in e.items() if kk != "chain"}) for e in v] for k, v in merged.items()},
        source_doc_ids=cached_data.get("source_doc_ids", []),
        last_updated=cached_data.get("last_updated"),
    )
    response.is_stale = is_stale
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
        "chains": {k: v for k, v in llm_chains.items()},
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


def _find_baseline_match(baseline_entries: list, llm_entry: dict) -> Optional[dict]:
    """Find a matching baseline entry for an LLM-extracted entry."""
    llm_kpi = llm_entry.get("kpi", "")
    llm_indicator = llm_entry.get("indicator", "")
    llm_group = _normalize_group(llm_entry.get("group", ""))

    for base_entry in baseline_entries:
        base_kpi = base_entry.get("kpi", "")
        base_indicator = base_entry.get("indicator", "")
        base_group = _normalize_group(base_entry.get("group", ""))

        kpi_match = base_kpi == llm_kpi
        group_match = base_group == llm_group
        ind_match = (
            base_indicator == llm_indicator
            or llm_indicator.lower().startswith(base_indicator.lower())
            or base_indicator.lower().startswith(llm_indicator.lower())
            or base_indicator.lower() in llm_indicator.lower()
            or llm_indicator.lower() in base_indicator.lower()
        )

        if kpi_match and group_match and ind_match:
            return base_entry
    return None


@dashboard.post("/kpi/extract", response_model=KPIExtractionReviewResponse)
async def extract_kpis_for_review():
    """Run LLM extraction and return raw entries for human review (no merge)."""
    logger.info("Extracting KPIs for review...")
    start_time = datetime.now()

    baseline = load_baseline()
    if not baseline:
        logger.error("No baseline data found.")
        return KPIExtractionReviewResponse(pending_id="", extracted_at=datetime.now().isoformat())

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

    # Build pending entries with baseline comparison
    pending_entries = []
    pending_id = str(uuid.uuid4())

    for chain_name, chain_baseline in baseline.items():
        chain_key = _normalize_chain(chain_name)
        llm_entries = llm_chains.get(chain_name, []) or llm_chains.get(chain_key, [])

        for llm_entry in llm_entries:
            llm_kpi = llm_entry.get("kpi", "")
            llm_indicator = llm_entry.get("indicator", "")
            llm_group = _normalize_group(llm_entry.get("group", ""))

            if not llm_kpi or not llm_indicator:
                continue

            baseline_match = _find_baseline_match(chain_baseline, llm_entry)

            entry_id = str(uuid.uuid4())[:8]
            if baseline_match:
                pending_entries.append(KPIPendingEntry(
                    id=entry_id,
                    chain=chain_key,
                    kpi=llm_kpi,
                    indicator=llm_indicator,
                    unit=llm_entry.get("unit", ""),
                    group=llm_group,
                    median=_to_float(llm_entry.get("median")),
                    p25=_to_float(llm_entry.get("p25")),
                    p75=_to_float(llm_entry.get("p75")),
                    rate=_to_float(llm_entry.get("rate")),
                    baseline_median=_to_float(baseline_match.get("median")),
                    baseline_p25=_to_float(baseline_match.get("p25")),
                    baseline_p75=_to_float(baseline_match.get("p75")),
                    baseline_rate=_to_float(baseline_match.get("rate")),
                    is_new=False,
                    approved=True,
                ))
            else:
                pending_entries.append(KPIPendingEntry(
                    id=entry_id,
                    chain=chain_key,
                    kpi=llm_kpi,
                    indicator=llm_indicator,
                    unit=llm_entry.get("unit", ""),
                    group=llm_group,
                    median=_to_float(llm_entry.get("median")),
                    p25=_to_float(llm_entry.get("p25")),
                    p75=_to_float(llm_entry.get("p75")),
                    rate=_to_float(llm_entry.get("rate")),
                    baseline_median=None,
                    baseline_p25=None,
                    baseline_p75=None,
                    baseline_rate=None,
                    is_new=True,
                    approved=True,
                ))

    # Save pending extraction
    pending_data = {
        "pending_id": pending_id,
        "entries": [e.model_dump() for e in pending_entries],
        "source_doc_ids": current_ids,
        "extracted_at": datetime.now().isoformat(),
    }
    save_pending(pending_data)

    return KPIExtractionReviewResponse(
        pending_id=pending_id,
        entries=pending_entries,
        source_doc_ids=current_ids,
        extracted_at=datetime.now().isoformat(),
    )


@dashboard.post("/kpi/apply", response_model=KPIExtractionResponse)
async def apply_approved_kpis(req: KPIApplyRequest):
    """Apply only the approved entries from a pending extraction to the KPIs."""
    pending_data = load_pending()

    if not pending_data or pending_data.get("pending_id") != req.pending_id:
        logger.error(f"Pending extraction {req.pending_id} not found.")
        return KPIExtractionResponse()

    baseline = load_baseline()
    approved_ids = set(req.approved_ids)

    approved_entries = []
    for entry in pending_data.get("entries", []):
        if entry["id"] in approved_ids:
            approved_entries.append(entry)

    # Build llm_chains from approved entries only
    llm_chains: dict[str, list[dict]] = {}
    for entry in approved_entries:
        chain = entry.get("chain", "")
        if chain not in llm_chains:
            llm_chains[chain] = []
        llm_chains[chain].append(entry)

    merged = _merge_with_baseline(baseline, llm_chains)

    source_doc_ids = pending_data.get("source_doc_ids", [])
    response_data = {
        "chains": {k: v for k, v in llm_chains.items()},
        "source_doc_ids": source_doc_ids,
    }
    save_kpis(response_data)

    # Clean up pending file
    try:
        os.remove(KPI_PENDING_FILE)
    except OSError:
        pass

    return KPIExtractionResponse(
        chains={k: [KPIEntry(chain=k, **{kk: vv for kk, vv in e.items() if kk != "chain"}) for e in v] for k, v in merged.items()},
        source_doc_ids=source_doc_ids,
        last_updated=datetime.now().isoformat(),
    )
