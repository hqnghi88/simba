from typing import List, Optional, Any
import os
import json
import re
from datetime import datetime
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from simba.core.factories.database_factory import get_database
from simba.core.factories.llm_factory import get_llm
from simba.core.config import settings

logger = logging.getLogger(__name__)

dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])

KPI_STORAGE_FILE = os.path.join(settings.paths.base_dir, "dashboard_kpis.json")

# Simplified KPI data structure for faster LLM response
class KPIData(BaseModel):
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
    
    if not enabled_docs:
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = []
        save_kpis(empty_data)
        return KPIResponse(**empty_data)
        
    # Optimized context: Take only the 3 most relevant docs and first 2 chunks
    # This significantly speeds up local LLM inference
    context_text = ""
    for doc in enabled_docs[:3]:
        content = ""
        if hasattr(doc, "documents") and doc.documents:
             content = "\n".join([c.page_content for c in doc.documents[:2]])
        elif hasattr(doc, "content") and doc.content:
             content = doc.content[:1500]
        
        if content:
            context_text += f"Source: {doc.metadata.filename}\n{content}\n---\n"
    
    if not context_text.strip():
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = current_ids
        save_kpis(empty_data)
        return KPIResponse(**empty_data)

    llm = get_llm()
    
    prompt = PromptTemplate.from_template(
        "Extract these agricultural KPIs as JSON from the text: soil_moisture, temperature, rainfall, humidity, crop_yield, pest_risk, fertilizer, equipment_health, solar_radiation, harvest_progress. "
        "Also include trends (up/down/neutral) for each. Provide values in concise formats (e.g., '25%', '27°C', 'Low').\n\n"
        "Text: {context}\n\nJSON output:"
    )
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        logger.info(f"Invoking LLM. Context size: {len(context_text)} chars")
        raw_output = await chain.ainvoke({"context": context_text})
        
        # Clean up output
        stripped = raw_output.strip()
        if "```json" in stripped:
            stripped = stripped.split("```json")[1].split("```")[0].strip()
        elif "```" in stripped:
             stripped = stripped.split("```")[1].split("```")[0].strip()
        
        # Extract JSON using regex if direct parse fails
        try:
            result = json.loads(stripped)
        except:
            # Fallback regex extraction
            result = {}
            for field in ["soil_moisture", "temperature", "rainfall", "humidity", "crop_yield", "pest_risk", "fertilizer", "equipment_health", "solar_radiation", "harvest_progress"]:
                m = re.search(f'"{field}"\\s*:\\s*"([^"]+)"', stripped, re.I)
                if m: result[field] = m.group(1)
                t_m = re.search(f'"{field}_trend"\\s*:\\s*"(up|down|neutral)"', stripped, re.I)
                if t_m: result[f"{field}_trend"] = t_m.group(1)

        # Merge with defaults
        final_values = KPIData().model_dump()
        for k, v in result.items():
            if k in final_values: final_values[k] = v
            
        final_values['source_doc_ids'] = current_ids
        save_kpis(final_values)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Recalculation completed in {elapsed:.2f}s")
        
        response = KPIResponse(**final_values)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")
        cached = load_kpis()
        if cached: return KPIResponse(**cached)
        return KPIResponse()
