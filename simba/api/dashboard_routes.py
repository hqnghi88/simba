from typing import List, Optional
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
    
    # Get latest document update time to check staleness
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    latest_doc_ts = 0.0
    for doc in enabled_docs:
        # Assuming metadata has uploadedAt or parsed_at
        ts_str = doc.metadata.parsed_at or doc.metadata.uploadedAt
        if ts_str:
            try:
                # Handle varying formats if needed, assuming isoformat
                ts = datetime.fromisoformat(ts_str).timestamp()
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
            
    # Determine staleness:
    # 1. No cached data -> Stale (needs Calc)
    # 2. Latest doc is newer than Last Calc -> Stale
    # 3. No docs enabled -> Not Stale (just N/A)
    is_stale = False
    if not cached_data and enabled_docs:
        is_stale = True
    elif enabled_docs and latest_doc_ts > last_kpi_ts:
        is_stale = True
        
    response = KPIResponse(**(cached_data or {}))
    response.is_stale = is_stale
    response.last_updated = cached_data.get('last_updated')
    
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
    
    if not enabled_docs:
        return KPIResponse()
        
    # 2. Prepare Context
    context_text = ""
    for doc in enabled_docs:
        content = ""
        # Try to extract text safely (from content or chunks)
        if hasattr(doc, "documents") and doc.documents:
             # Concatenate first few chunks
             content = "\n".join([c.page_content for c in doc.documents[:5]])
        elif hasattr(doc, "content") and doc.content:
             content = doc.content[:3000]
        
        context_text += f"--- Document: {doc.metadata.filename} ---\n{content}\n\n"
    
    if not context_text.strip():
        # Save empty/default if no content
        empty_data = KPIData().model_dump()
        save_kpis(empty_data)
        return KPIResponse(**empty_data)

    # 3. Use LLM
    llm = get_llm()
    parser = JsonOutputParser(pydantic_object=KPIData)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an Agricultural Data Analyst. 
        Your task is to analyze the provided documents and extract/calculate key performance indicators (KPIs) for a farm dashboard.
        
        Extract values for the following metrics:
        - Soil Moisture (%, e.g. "64")
        - Temperature (AVG in Celsius, e.g. "24.5")
        - Rainfall (mm, e.g. "128")
        - Humidity (%, e.g. "72")
        - Crop Yield Forecast (tons/ha)
        - Pest Risk Index (Low/Medium/High)
        - Fertilizer Usage (kg)
        - Equipment Health (%)
        - Solar Radiation (MJ/m²)
        - Harvest Progress (%)
        
        Also determine the trend ('up', 'down', 'neutral') based on historical comparisons or context in the text.
        If a specific value is not found, make a REASONABLE ESTIMATE based on the context of the document.
        If absolutely no info is available, return "N/A".
        
        {format_instructions}
        """),
        ("human", "Here are the documents:\n\n{context}")
    ])
    
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "context": context_text,
            "format_instructions": parser.get_format_instructions()
        })
        
        # Save to cache
        save_kpis(result)
        
        # Return result with stale=False
        response = KPIResponse(**result)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")
        return KPIResponse() # Fallback
