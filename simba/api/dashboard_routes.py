from typing import List, Optional, Any

import os
import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from simba.core.factories.database_factory import get_database
from simba.core.factories.llm_factory import get_llm
from simba.core.config import settings
import logging

logger = logging.getLogger(__name__)

dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])

KPI_STORAGE_FILE = os.path.join(settings.paths.base_dir, "dashboard_kpis.json")

# Define the data structure for our KPIs
class KPIData(BaseModel):
    soil_moisture: str = Field(description="A single concise measurement value ONLY (e.g. '25%' or 'High')", default="N/A")
    temperature: str = Field(description="A single concise measurement value ONLY (e.g. '27.5°C' or 'High')", default="N/A")
    rainfall: str = Field(description="A single concise measurement value ONLY (e.g. '150mm' or 'Low')", default="N/A")
    humidity: str = Field(description="A single concise measurement value ONLY (e.g. '80%' or 'Optimal')", default="N/A")
    crop_yield: str = Field(description="A single concise measurement value ONLY (e.g. '5.2t/ha' or 'Good')", default="N/A")
    pest_risk: str = Field(description="A single concise measurement value ONLY (e.g. 'Low' or 'High')", default="Low")
    fertilizer: str = Field(description="A single concise measurement value ONLY (e.g. '50kg/ha' or 'Normal')", default="N/A")
    equipment_health: str = Field(description="A single concise measurement value ONLY (e.g. 'Good' or 'Fair')", default="Good")
    solar_radiation: str = Field(description="A single concise measurement value ONLY (e.g. '5.5kWh/m2' or 'Strong')", default="N/A")
    harvest_progress: str = Field(description="A single concise measurement value ONLY (e.g. '45%' or 'Complete')", default="0%")
    
    # Trends for UI
    soil_moisture_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    temperature_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    rainfall_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    humidity_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    crop_yield_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    pest_risk_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    fertilizer_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    equipment_health_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    solar_radiation_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    harvest_progress_trend: str = Field(description="'up', 'down', or 'neutral'", default="neutral")
    
    # Reasons/Explanations for transparency
    soil_moisture_explanation: str = Field(description="Reasoning for Soil Moisture value", default="")
    soil_moisture_trend_reasoning: str = Field(description="Why is soil moisture trending this way?", default="")
    temperature_explanation: str = Field(description="Reasoning for Temperature value", default="")
    temperature_trend_reasoning: str = Field(description="Why is temperature trending this way?", default="")
    rainfall_explanation: str = Field(description="Reasoning for Rainfall value", default="")
    rainfall_trend_reasoning: str = Field(description="Why is rainfall trending this way?", default="")
    humidity_explanation: str = Field(description="Reasoning for Humidity value", default="")
    humidity_trend_reasoning: str = Field(description="Why is humidity trending this way?", default="")
    crop_yield_explanation: str = Field(description="Reasoning for Crop Yield value", default="")
    crop_yield_trend_reasoning: str = Field(description="Why is crop yield trending this way?", default="")
    pest_risk_explanation: str = Field(description="Reasoning for Pest Risk value", default="")
    pest_risk_trend_reasoning: str = Field(description="Why is pest risk trending this way?", default="")
    fertilizer_explanation: str = Field(description="Reasoning for Fertilizer value", default="")
    fertilizer_trend_reasoning: str = Field(description="Why is fertilizer trending this way?", default="")
    equipment_health_explanation: str = Field(description="Reasoning for Equipment Health value", default="")
    equipment_health_trend_reasoning: str = Field(description="Why is equipment health trending this way?", default="")
    solar_radiation_explanation: str = Field(description="Reasoning for Solar Radiation value", default="")
    solar_radiation_trend_reasoning: str = Field(description="Why is solar radiation trending this way?", default="")
    harvest_progress_explanation: str = Field(description="Reasoning for Harvest Progress value", default="")
    harvest_progress_trend_reasoning: str = Field(description="Why is harvest progress trending this way?", default="")

class KPIResponse(KPIData):
    is_stale: bool = Field(default=False)
    last_updated: Optional[str] = Field(default=None)
    source_doc_ids: List[str] = Field(default=[])

def load_kpis() -> dict:
    if os.path.exists(KPI_STORAGE_FILE):
        try:
            with open(KPI_STORAGE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading KPIs: {e}")
    return {}

def save_kpis(data: dict):
    try:
        data['last_updated'] = datetime.now().isoformat()
        with open(KPI_STORAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving KPIs: {e}")

@dashboard.get("/kpi", response_model=KPIResponse)
async def get_kpis():
    """
    Get cached KPIs and check validation status.
    """
    cached_data = load_kpis()
    
    # Get enabled documents
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    current_ids = sorted([d.id for d in enabled_docs])
    cached_ids = sorted(cached_data.get('source_doc_ids', []))
    
    # Check timestamps for freshness of content
    latest_doc_ts = 0.0
    for doc in enabled_docs:
        ts_str = doc.metadata.parsed_at or doc.metadata.uploadedAt
        if ts_str:
            try:
                # Handle varying formats if needed
                ts = datetime.fromisoformat(str(ts_str)).timestamp()
                if ts > latest_doc_ts:
                    latest_doc_ts = ts
            except:
                pass

    last_kpi_ts = 0.0
    if cached_data.get('last_updated'):
        try:
            last_kpi_ts = datetime.fromisoformat(cached_data['last_updated']).timestamp()
        except:
            pass
            
    # Determine staleness
    is_stale = False
    
    logger.debug(f"Staleness Check: current_ids={current_ids}")
    logger.debug(f"Staleness Check: cached_ids={cached_ids}")
    logger.debug(f"Staleness Check: latest_doc_ts={latest_doc_ts}, last_kpi_ts={last_kpi_ts}")

    if not cached_data and enabled_docs:
        is_stale = True
        logger.info("Staleness Check: Stale because no cached data")
    elif current_ids != cached_ids:
        is_stale = True
        logger.info(f"Staleness Check: Stale because list of docs changed. Diff: {set(current_ids) ^ set(cached_ids)}")
    elif enabled_docs and (latest_doc_ts - last_kpi_ts) > 1.0: # Add 1s buffer
        is_stale = True
        logger.info(f"Staleness Check: Stale because documents were updated more recently than the last calculation. Diff: {latest_doc_ts - last_kpi_ts}s")
    else:
        logger.debug("Staleness Check: Data is UP TO DATE")
        
    response = KPIResponse(**(cached_data or {}))
    response.is_stale = is_stale
    response.last_updated = cached_data.get('last_updated')
    response.source_doc_ids = cached_data.get('source_doc_ids', [])
    
    return response

@dashboard.post("/kpi/recalculate", response_model=KPIResponse)
async def recalculate_kpis():
    """
    Force recalculation of KPIs using LLM.
    """
    logger.info("Recalculating Dashboard KPIs from documents...")
    
    # 1. Fetch enabled documents
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    current_ids = [d.id for d in enabled_docs]
    
    if not enabled_docs:
        # Save empty state
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = []
        save_kpis(empty_data)
        return KPIResponse(**empty_data)
        
    # 2. Prepare Context (Selective for speed)
    context_text = ""
    logger.info(f"Preparing context for {len(enabled_docs)} enabled documents")
    
    # Only take the 5 most recent documents, and only 3 chunks each
    for doc in enabled_docs[:5]:
        content = ""
        if hasattr(doc, "documents") and doc.documents:
             logger.info(f"Processing top chunks for {doc.metadata.filename}")
             content = "\n".join([c.page_content for c in doc.documents[:3]])
        elif hasattr(doc, "content") and doc.content:
             content = doc.content[:2000]
        
        if content:
            context_text += f"--- Source: {doc.metadata.filename} ---\n{content}\n\n"
    
    if not context_text.strip():
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = current_ids
        save_kpis(empty_data)
        return KPIResponse(**empty_data)

    llm = get_llm()
    
    # Use a very explicit JSON template the model must fill in
    json_template = """{
  "soil_moisture": "<single value like '25%' or 'Low'>",
  "temperature": "<single value like '27.6°C'>",
  "rainfall": "<single value like '1534mm'>",
  "humidity": "<single value like '79%'>",
  "crop_yield": "<single value like '5.2 t/ha'>",
  "pest_risk": "<single value: High/Medium/Low>",
  "fertilizer": "<single value or N/A>",
  "equipment_health": "<single value: Good/Fair/Poor>",
  "solar_radiation": "<single value like '2521 hrs'>",
  "harvest_progress": "<single value like '45%'>",
  "soil_moisture_trend": "<up|down|neutral>",
  "temperature_trend": "<up|down|neutral>",
  "rainfall_trend": "<up|down|neutral>",
  "humidity_trend": "<up|down|neutral>",
  "crop_yield_trend": "<up|down|neutral>",
  "pest_risk_trend": "<up|down|neutral>",
  "fertilizer_trend": "<up|down|neutral>",
  "equipment_health_trend": "<up|down|neutral>",
  "solar_radiation_trend": "<up|down|neutral>",
  "harvest_progress_trend": "<up|down|neutral>",
  "soil_moisture_explanation": "<max 15 words>",
  "temperature_explanation": "<max 15 words>",
  "rainfall_explanation": "<max 15 words>",
  "humidity_explanation": "<max 15 words>",
  "crop_yield_explanation": "<max 15 words>",
  "pest_risk_explanation": "<max 15 words>",
  "fertilizer_explanation": "<max 15 words>",
  "equipment_health_explanation": "<max 15 words>",
  "solar_radiation_explanation": "<max 15 words>",
  "harvest_progress_explanation": "<max 15 words>",
  "soil_moisture_trend_reasoning": "<max 8 words>",
  "temperature_trend_reasoning": "<max 8 words>",
  "rainfall_trend_reasoning": "<max 8 words>",
  "humidity_trend_reasoning": "<max 8 words>",
  "crop_yield_trend_reasoning": "<max 8 words>",
  "pest_risk_trend_reasoning": "<max 8 words>",
  "fertilizer_trend_reasoning": "<max 8 words>",
  "equipment_health_trend_reasoning": "<max 8 words>",
  "solar_radiation_trend_reasoning": "<max 8 words>",
  "harvest_progress_trend_reasoning": "<max 8 words>"
}"""

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate
    
    prompt = PromptTemplate.from_template(
        "You are an Agricultural Data Scientist. Analyze the documents and extract KPI values.\n\n"
        "RULES:\n"
        "- Each main metric MUST be a SINGLE measurement string (e.g. '27.6°C', '79%', 'Low').\n"
        "- Trend fields MUST be exactly 'up', 'down', or 'neutral'.\n"
        "- Fill in EVERY field in the JSON below with real values from the text.\n"
        "- Do NOT add any text before or after the JSON.\n"
        "- Output ONLY valid JSON.\n\n"
        "Documents:\n{context}\n\n"
        "Fill this JSON template with values from the documents:\n{template}"
    )
    
    chain = prompt | llm | StrOutputParser()

    import re, ast, json as jsonlib

    METRIC_FIELDS = ["soil_moisture", "temperature", "rainfall", "humidity", "crop_yield",
                     "pest_risk", "fertilizer", "equipment_health", "solar_radiation", "harvest_progress"]

    def force_single_value(v):
        """Returns a single concise string. No matter what."""
        if v is None: return "N/A"
        s = str(v).strip()
        
        # Strip markdown emphasis
        s = re.sub(r'[*_`]', '', s)
        
        # If it's already short and clean, return it
        if len(s) <= 12 and '{' not in s and '[' not in s:
            return s
        
        # 1. Percentage
        m = re.search(r"(\d+\.?\d*%)", s)
        if m: return m.group(1)
        
        # 2. Number + unit (e.g. 27.6°C, 1534mm, 5.2 t/ha, 2521 hrs)
        m = re.search(r"(\d+\.?\d*\s*(?:°C|t/ha|kg/ha|mm|kWh/m2|hrs|hours|%)?)", s)
        if m and m.group(1).strip(): return m.group(1).strip()
        
        # 3. Status keywords
        m = re.search(r"\b(High|Medium|Low|Good|Fair|Poor|Normal|Optimal|Stable|Neutral|N/A)\b", s, re.I)
        if m: return m.group(1).capitalize()
        
        # 4. First word fallback
        clean_s = re.sub(r'[\{\}\[\]\'\"]', '', s)
        words = [w for w in clean_s.split() if w not in ('Hoa','Binh','Luang','Prabang','Phrae','The','N/A')]
        if words: return words[0][:12]
        
        return "N/A"

    def parse_bullet_list(text):
        """Parse bullet-point lines like '* Soil Moisture: 27.6°C' into a dict."""
        result = {}
        field_map = {
            "soil moisture": "soil_moisture", "temperature": "temperature",
            "rainfall": "rainfall", "humidity": "humidity",
            "crop yield": "crop_yield", "pest risk": "pest_risk",
            "fertilizer": "fertilizer", "equipment health": "equipment_health",
            "solar radiation": "solar_radiation", "harvest progress": "harvest_progress",
        }
        for raw_field, key in field_map.items():
            m = re.search(
                rf"[\*\-]\s*{re.escape(raw_field)}[:\s]+([^\n\(]+)",
                text, re.I
            )
            if m:
                val = m.group(1).strip().rstrip('(').strip()
                result[key] = val
            m_trend = re.search(
                rf"[\*\-]\s*{re.escape(raw_field)}\s+trend[:\s]+(up|down|neutral)",
                text, re.I
            )
            if m_trend:
                result[f"{key}_trend"] = m_trend.group(1).lower()
        return result

    def extract_kv_from_raw(text):
        """
        Regex extraction of "key": "value" pairs from malformed JSON.
        Works even when the JSON parser fails due to bad chars in values.
        """
        result = {}
        # Match: "some_key": "some value possibly with commas and periods"
        pattern = re.finditer(r'"([a-z_]+)"\s*:\s*"([^"]*)"', text)
        for m in pattern:
            key, val = m.group(1), m.group(2)
            result[key] = val
        return result

    try:
        logger.info(f"Invoking LLM for KPIs. Context length: {len(context_text)} chars")
        raw_output = chain.invoke({
            "context": context_text,
            "template": json_template,
        })
        logger.info(f"Raw LLM Output (first 500 chars): {raw_output[:500]}")
        
        result = {}
        
        # Clean the raw output: strip markdown code fences if present
        stripped = raw_output.strip()
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped, flags=re.MULTILINE)
        stripped = re.sub(r'```\s*$', '', stripped, flags=re.MULTILINE)
        # Remove any <placeholder> values the model didn't fill in
        stripped = re.sub(r'"<[^"]*>"', '"N/A"', stripped)
        stripped = stripped.strip()
        
        # Strategy 1: Try to parse entire output as JSON
        try:
            result = jsonlib.loads(stripped)
            logger.info(f"Parsed entire output as JSON directly. Keys: {list(result.keys())[:5]}")
        except Exception as e1:
            logger.warning(f"Direct JSON parse failed: {e1}")
            # Strategy 2: Find JSON block (first { to last })
            start = stripped.find('{')
            end = stripped.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_snippet = stripped[start:end+1]
                # Remove trailing commas before } or ] (common LLM mistake)
                json_snippet = re.sub(r',\s*([}\]])', r'\1', json_snippet)
                try:
                    result = jsonlib.loads(json_snippet)
                    logger.info(f"Parsed via JSON block extraction. Keys: {list(result.keys())[:5]}")
                except Exception as e2:
                    logger.warning(f"JSON block extraction failed: {e2}")
        
        # Strategy 3: Regex extract "key": "value" pairs from raw text (handles malformed JSON)
        if not result or not any(k in result for k in METRIC_FIELDS):
            result = extract_kv_from_raw(raw_output)
            logger.info(f"Parsed via regex KV extraction. Got {len(result)} fields.")
        
        # Strategy 4: Parse bullet-point list (fallback for markdown output)
        if not result or not any(k in result for k in METRIC_FIELDS):
            result = parse_bullet_list(raw_output)
            logger.info(f"Parsed via bullet list: {result}")

        final_values = KPIData().model_dump()
        
        for field in list(final_values.keys()):
            val = result.get(field, "N/A")
            
            if field in METRIC_FIELDS:
                final_values[field] = force_single_value(val)
                logger.info(f"  {field}: '{val}' -> '{final_values[field]}'")
            elif field.endswith("_trend"):
                s = str(val).lower()
                if 'up' in s: final_values[field] = 'up'
                elif 'down' in s: final_values[field] = 'down'
                else: final_values[field] = 'neutral'
            elif field.endswith("_trend_reasoning"):
                s = re.sub(r'[\{\}\[\]]', '', str(val).strip())
                final_values[field] = s[:60] + "..." if len(s) > 63 else s
            else:
                s = re.sub(r'[\{\}\[\]]', '', str(val).strip())
                final_values[field] = s[:180] + "..." if len(s) > 183 else s

        final_values['source_doc_ids'] = sorted(current_ids)
        save_kpis(final_values)
        
        response = KPIResponse(**final_values)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}", exc_info=True)
        cached = load_kpis()
        if cached:
            return KPIResponse(**cached)
        return KPIResponse()
