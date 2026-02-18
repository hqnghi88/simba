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
    soil_moisture: Any = Field(description="Value for Soil Moisture", default="N/A")
    temperature: Any = Field(description="Value for Average Temperature", default="N/A")
    rainfall: Any = Field(description="Value for Rainfall", default="N/A")
    humidity: Any = Field(description="Value for Humidity", default="N/A")
    crop_yield: Any = Field(description="Value for Crop Yield Forecast", default="N/A")
    pest_risk: Any = Field(description="Value for Pest Risk Index", default="Low")
    fertilizer: Any = Field(description="Value for Fertilizer Usage", default="N/A")
    equipment_health: Any = Field(description="Value for Equipment Health", default="Good")
    solar_radiation: Any = Field(description="Value for Solar Radiation", default="N/A")
    harvest_progress: Any = Field(description="Value for Harvest Progress", default="0%")
    
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

    # 3. Use LLM
    llm = get_llm()
    # Explicitly set max_tokens lower for the dashboard to force speed
    llm.max_tokens = 800
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a meticulous Agricultural Data Scientist.
        Extract metrics from the provided text and provide HEAVY EVIDENCE for each value.
        
        LOCATIONS: Hoa Binh (VN), Luang Prabang (LA), Phrae (TH).
        
        REQUIRED FIELDS for EACH metric (e.g. soil_moisture):
        - [metric]: The value string (e.g. "25.4")
        - [metric]_trend: "up", "down", or "neutral"
        - [metric]_explanation: EXACT CITATION from the text stating the document name and context.
        - [metric]_trend_reasoning: Brief logic for the trend choice.
        
        ALL FIELDS MUST BE PRESENT FOR THESE METRICS: 
        soil_moisture, temperature, rainfall, humidity, crop_yield, pest_risk, fertilizer, equipment_health, solar_radiation, harvest_progress.
        
        CRITICAL RULES:
        - If you find a value, you MUST explain exactly which document it came from.
        - If you fallback (e.g. 24.5C for temp), explain it as "Regional Average for Indochina".
        - RETURN ONLY A PURE JSON OBJECT. NO CHAT.
        """),
        ("human", "Analyze these documents and provide a JSON response with evidence for EVERY field:\n\n{context}")
    ])
    
    from langchain_core.output_parsers import StrOutputParser
    chain = prompt | llm | StrOutputParser()
    
    try:
        logger.info(f"Invoking LLM for KPIs. Context length: {len(context_text)} chars")
        raw_result = chain.invoke({"context": context_text})
        logger.info(f"Raw LLM Response: {raw_result}")
        
        # Robust JSON cleaning
        clean_result = raw_result.strip()
        if "{" in clean_result:
            clean_result = clean_result[clean_result.find("{"):clean_result.rfind("}")+1]
            
        result = json.loads(clean_result)
        
        # Merge with defaults and cast to strings
        final_values = KPIData().model_dump()
        for k, v in result.items():
            if k in final_values:
                # Force everything to string for the frontend, but handle nested objects if LLM messed up
                if isinstance(v, dict):
                    # Try to extract 'value' if it's nested
                    final_values[k] = str(v.get('value', v))
                else:
                    final_values[k] = str(v)
        
        final_values['source_doc_ids'] = sorted(current_ids)
        save_kpis(final_values)
        
        response = KPIResponse(**final_values)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}", exc_info=True)
        # Return last known good data or empty
        cached = load_kpis()
        if cached:
            return KPIResponse(**cached)
        return KPIResponse() # Fallback
