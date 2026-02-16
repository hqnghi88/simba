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
            
    # Determine staleness:
    # 1. No cached data -> Stale (if docs exist)
    # 2. Source ID mismatch (Documents added/removed/disabled) -> Stale
    # 3. Latest doc timestamp > Last Calculation (Content updated) -> Stale
    is_stale = False
    
    if not cached_data and enabled_docs:
        is_stale = True
    elif current_ids != cached_ids:
        is_stale = True
    elif enabled_docs and latest_doc_ts > last_kpi_ts:
        is_stale = True
        
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
        
    # 2. Prepare Context
    context_text = ""
    for doc in enabled_docs:
        content = ""
        # Try to extract text safely
        if hasattr(doc, "documents") and doc.documents:
             # Concatenate first 5 chunks
             content = "\n".join([c.page_content for c in doc.documents[:5]])
        elif hasattr(doc, "content") and doc.content:
             content = doc.content[:3000]
        
        context_text += f"--- Document: {doc.metadata.filename} ---\n{content}\n\n"
    
    if not context_text.strip():
        empty_data = KPIData().model_dump()
        empty_data['source_doc_ids'] = current_ids
        save_kpis(empty_data)
        return KPIResponse(**empty_data)

    # 3. Use LLM
    llm = get_llm()
    parser = JsonOutputParser(pydantic_object=KPIData)
    # Use a custom parser robust to markdown blocks
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an Agricultural Data Analyst. 
        Your task is to analyze the provided documents and DIRECTLY EXTRACT key performance indicators (KPIs).
        
        DO NOT write any code (Python, etc).
        DO NOT explain your process.
        RETURN ONLY A SINGLE JSON OBJECT.
        
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
        
        Also determine the trend ('up', 'down', 'neutral') and provide:
        1. An EXPLANATION for the current value (how it was derived/extracted).
        2. A TREND REASONING (why is it up, down, or stable based on document evidence).
        
        If a specific value is not found, make a REASONABLE ESTIMATE based on the context and explain your reasoning.
        If absolutely no info is available, return "N/A" and explain why.
        
        Output format must be valid JSON matching this structure:
        {{
            "soil_moisture": "value",
            "soil_moisture_trend": "up",
            "soil_moisture_explanation": "brief reasoning for the value",
            "soil_moisture_trend_reasoning": "brief reasoning for the trend",
            ... and so on for all fields ...
        }}
        
        {format_instructions}
        """),
        ("human", "Here are the documents:\n\n{context}")
    ])
    
    # We use StrOutputParser first to get raw text, then try to parse JSON
    from langchain_core.output_parsers import StrOutputParser
    chain = prompt | llm | StrOutputParser()
    
    try:
        raw_result = chain.invoke({
            "context": context_text,
            "format_instructions": parser.get_format_instructions()
        })
        
        # Clean up result if it contains markdown code blocks
        clean_result = raw_result.strip()
        if "```json" in clean_result:
            clean_result = clean_result.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_result:
             clean_result = clean_result.split("```")[1].split("```")[0].strip()
            
        result = json.loads(clean_result)
        
        # Add source IDs and save
        result['source_doc_ids'] = current_ids
        save_kpis(result)
        
        response = KPIResponse(**result)
        response.is_stale = False
        response.last_updated = datetime.now().isoformat()
        response.source_doc_ids = current_ids
        return response
        
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")
        logger.error(f"Raw LLM Output was: {locals().get('raw_result', 'Not available')}")
        return KPIResponse() # Fallback
