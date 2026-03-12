from typing import List, Optional, Any
import os
import json
import re
from datetime import datetime
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from simba.core.factories.database_factory import get_database
from simba.core.factories.llm_factory import get_llm
from simba.core.config import settings

logger = logging.getLogger(__name__)

dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])

KPI_STORAGE_FILE = os.path.join(settings.paths.base_dir, "dashboard_kpis.json")

# KPI data structure
class KPIData(BaseModel):
    # Core values
    soil_moisture: str = Field(description="Value for Soil Moisture", default="N/A")
    temperature: str = Field(description="Value for Average Temperature", default="N/A")
    rainfall: str = Field(description="Value for Rainfall", default="N/A")
    humidity: str = Field(description="Value for Humidity", default="N/A")
    crop_yield: str = Field(description="Value for Crop Yield Forecast", default="N/A")
    pest_risk: str = Field(description="Value for Pest Risk Index", default="Low")
    fertilizer: str = Field(description="Value for Fertilizer Usage", default="N/A")
    equipment_health: str = Field(description="Value for Equipment Health", default="Good")
    solar_radiation: str = Field(description="Value for Solar Radiation", default="N/A")
    harvest_progress: str = Field(description="Value for Harvest Progress", default="0%")
    
    # Trends
    soil_moisture_trend: str = Field(default="neutral")
    temperature_trend: str = Field(default="neutral")
    rainfall_trend: str = Field(default="neutral")
    humidity_trend: str = Field(default="neutral")
    crop_yield_trend: str = Field(default="neutral")
    pest_risk_trend: str = Field(default="neutral")
    fertilizer_trend: str = Field(default="neutral")
    equipment_health_trend: str = Field(default="neutral")
    solar_radiation_trend: str = Field(default="neutral")
    harvest_progress_trend: str = Field(default="neutral")

    # Explanations (source evidence)
    soil_moisture_explanation: str = Field(default="")
    temperature_explanation: str = Field(default="")
    rainfall_explanation: str = Field(default="")
    humidity_explanation: str = Field(default="")
    crop_yield_explanation: str = Field(default="")
    pest_risk_explanation: str = Field(default="")
    fertilizer_explanation: str = Field(default="")
    equipment_health_explanation: str = Field(default="")
    solar_radiation_explanation: str = Field(default="")
    harvest_progress_explanation: str = Field(default="")

    # Trend reasoning
    soil_moisture_trend_reasoning: str = Field(default="")
    temperature_trend_reasoning: str = Field(default="")
    rainfall_trend_reasoning: str = Field(default="")
    humidity_trend_reasoning: str = Field(default="")
    crop_yield_trend_reasoning: str = Field(default="")
    pest_risk_trend_reasoning: str = Field(default="")
    fertilizer_trend_reasoning: str = Field(default="")
    equipment_health_trend_reasoning: str = Field(default="")
    solar_radiation_trend_reasoning: str = Field(default="")
    harvest_progress_trend_reasoning: str = Field(default="")

class KPIResponse(KPIData):
    model_config = ConfigDict(extra='allow')  # preserve any additional LLM fields
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
    """Get cached KPIs and check validation status."""
    cached_data = load_kpis()
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    current_ids = sorted([d.id for d in enabled_docs])
    cached_ids = sorted(cached_data.get('source_doc_ids', []))
    
    # Check timestamps
    latest_doc_ts = 0.0
    for doc in enabled_docs:
        ts_str = doc.metadata.parsed_at or doc.metadata.uploadedAt
        if ts_str:
            try:
                ts = datetime.fromisoformat(str(ts_str)).timestamp()
                if ts > latest_doc_ts:
                    latest_doc_ts = ts
            except: pass

    last_kpi_ts = 0.0
    if cached_data.get('last_updated'):
        try:
            last_kpi_ts = datetime.fromisoformat(cached_data['last_updated']).timestamp()
        except: pass
            
    is_stale = False
    if not cached_data and enabled_docs:
        is_stale = True
    elif current_ids != cached_ids:
        is_stale = True
    elif enabled_docs and (latest_doc_ts - last_kpi_ts) > 1.0:
        is_stale = True
        
    response = KPIResponse(**(cached_data or {}))
    response.is_stale = is_stale
    response.last_updated = cached_data.get('last_updated')
    response.source_doc_ids = cached_data.get('source_doc_ids', [])
    
    return response

@dashboard.post("/kpi/recalculate", response_model=KPIResponse)
async def recalculate_kpis():
    """Force recalculation of KPIs using LLM with optimized context."""
    logger.info("Recalculating Dashboard KPIs...")
    start_time = datetime.now()
    
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    current_ids = [d.id for d in enabled_docs]
    
    logger.info(f"Total documents in database: {len(all_docs)}")
    logger.info(f"Found {len(enabled_docs)} enabled documents: {current_ids}")
    
    if not enabled_docs:
        logger.warning("No enabled documents found for KPI calculation.")
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = []
        save_kpis(empty_data)
        return KPIResponse(**empty_data)
        
    # Sort enabled docs by parsed_at or uploadedAt descending to prioritize newest/freshly enabled/updated docs
    def get_doc_ts(d):
        ts = d.metadata.parsed_at or d.metadata.uploadedAt or ""
        return ts
    
    enabled_docs.sort(key=get_doc_ts, reverse=True)
    
    # Optimized context: Take up to 8 documents but limit each to the first chunk
    # This provides a broader overview of all enabled data while keeping tokens low.
    context_text = ""
    logger.info(f"Targeting up to 8 documents from {len(enabled_docs)} enabled docs for context.")
    
    docs_used = []
    for doc in enabled_docs[:8]:
        content = ""
        # Priority: Check for chunks (documents)
        if hasattr(doc, "documents") and doc.documents and len(doc.documents) > 0:
             content = doc.documents[0].page_content
             logger.debug(f"Using first chunk of {doc.metadata.filename}")
        # Fallback: Check for raw content
        elif hasattr(doc, "content") and doc.content:
             content = doc.content[:1000]
             logger.debug(f"Using raw content of {doc.metadata.filename}")
        
        if content:
            context_text += f"\n--- Source Document: {doc.metadata.filename} ---\n{content}\n"
            docs_used.append(doc.metadata.filename)
        else:
            logger.warning(f"Document {doc.metadata.filename} (ID: {doc.id}) has NO content chunks and NO raw content.")
    
    logger.info(f"Context successfully built using {len(docs_used)} documents: {', '.join(docs_used)}")
    logger.info(f"Total context text size: {len(context_text)} characters")
    
    if not context_text.strip():
        logger.error("Context text is empty! Cannot calculate KPIs.")
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = current_ids
        save_kpis(empty_data)
        return KPIResponse(**empty_data)

    llm = get_llm()
    
    prompt = PromptTemplate.from_template(
        "Extract agricultural KPIs from the text and return a single FLAT JSON object. "
        "DO NOT nest objects. For each KPI (soil_moisture, temperature, rainfall, humidity, crop_yield, pest_risk, fertilizer, equipment_health, solar_radiation, harvest_progress), provide:\n"
        "  - <kpi>: concise value string (e.g. '25%', '27°C', 'Low', 'N/A')\n"
        "  - <kpi>_trend: 'up', 'down', or 'neutral'\n"
        "  - <kpi>_trend_reasoning: one short sentence explaining the trend\n"
        "  - <kpi>_explanation: one short sentence quoting the source evidence\n\n"
        "Example flat structure:\n"
        "{{\"soil_moisture\": \"20%\", \"soil_moisture_trend\": \"up\", \"soil_moisture_trend_reasoning\": \"Recent rain\", \"soil_moisture_explanation\": \"Sensor data shows 20%\"}}\n\n"
        "Text: {context}\n\nJSON output:"
    )
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        logger.info(f"Invoking LLM. Context size: {len(context_text)} chars")
        raw_output = await chain.ainvoke({"context": context_text})
        logger.info(f"RAW LLM OUTPUT: {raw_output}")
        
        # Clean up output
        stripped = raw_output.strip()
        if "```json" in stripped:
            stripped = stripped.split("```json")[1].split("```")[0].strip()
        elif "```" in stripped:
             stripped = stripped.split("```")[1].split("```")[0].strip()
        
        # Extract JSON using regex if direct parse fails
        try:
            result = json.loads(stripped)
            logger.info(f"JSON successfully parsed. Type: {type(result)}")
            
            # AGGRESSIVE FLATTENING
            flattened = {}
            
            # If it's a list, take the first element
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            if isinstance(result, dict):
                logger.info(f"Root keys before flattening: {list(result.keys())}")
                for k, v in result.items():
                    if isinstance(v, dict):
                        logger.info(f"Flattening nested dict for key: {k}")
                        # Extract 'value' or similar as the main key
                        val = v.get("value") or v.get("val") or v.get("amount")
                        if val is not None:
                            flattened[k] = str(val)
                        
                        # Extract everything else with suffix
                        for sub_k, sub_v in v.items():
                            if sub_k not in ["value", "val", "amount"]:
                                flattened[f"{k}_{sub_k}"] = str(sub_v)
                            elif k not in flattened:
                                # Fallback if we didn't set the main key yet
                                flattened[k] = str(sub_v)
                    else:
                        flattened[k] = str(v)
                result = flattened
            
            logger.info(f"Keys after flattening: {list(result.keys())}")
            # Log a couple of sample flattened values to verify
            if "soil_moisture" in result:
                logger.info(f"Sample: soil_moisture='{result['soil_moisture']}' (type: {type(result['soil_moisture'])})")
            
        except Exception as json_err:
            logger.warning(f"JSON parse failed: {json_err}. Attempting regex extraction.")
            # Fallback regex extraction
            result = {}
            kpis = ["soil_moisture", "temperature", "rainfall", "humidity", "crop_yield", "pest_risk", "fertilizer", "equipment_health", "solar_radiation", "harvest_progress"]
            for field in kpis:
                # Value
                m = re.search(rf'"{field}"\s*:\s*"([^"]+)"', stripped, re.I)
                if m: result[field] = m.group(1)
                
                # Trend, reasoning, explanation
                for suffix in ["_trend", "_trend_reasoning", "_explanation"]:
                    f_m = re.search(rf'"{field}{suffix}"\s*:\s*"([^"]+)"', stripped, re.I)
                    if f_m: result[f"{field}{suffix}"] = f_m.group(1)
            
            logger.info(f"Regex extraction found {len(result)} fields: {list(result.keys())}")
            
        except Exception as json_err:
            logger.warning(f"JSON parse failed: {json_err}. Attempting regex extraction.")
            # Fallback regex extraction
            result = {}
            kpis = ["soil_moisture", "temperature", "rainfall", "humidity", "crop_yield", "pest_risk", "fertilizer", "equipment_health", "solar_radiation", "harvest_progress"]
            for field in kpis:
                # Value
                m = re.search(rf'"{field}"\s*:\s*"([^"]+)"', stripped, re.I)
                if m: result[field] = m.group(1)
                
                # Trend, reasoning, explanation
                for suffix in ["_trend", "_trend_reasoning", "_explanation"]:
                    f_m = re.search(rf'"{field}{suffix}"\s*:\s*"([^"]+)"', stripped, re.I)
                    if f_m: result[f"{field}{suffix}"] = f_m.group(1)
            
            logger.info(f"Regex extraction found {len(result)} fields: {list(result.keys())}")

        # Merge LLM result over defaults — keep ALL keys the LLM returned
        final_values = KPIData().model_dump()
        final_values.update(result)        # overwrite with everything from LLM
        final_values['source_doc_ids'] = current_ids
        save_kpis(final_values)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Recalculation completed in {elapsed:.2f}s. KPI values updated.")
        
        response = KPIResponse(**final_values)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}", exc_info=True)
        cached = load_kpis()
        if cached: return KPIResponse(**cached)
        return KPIResponse()
