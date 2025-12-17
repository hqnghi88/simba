from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from simba.core.factories.database_factory import get_database
from simba.core.factories.llm_factory import get_llm
import logging
logger = logging.getLogger(__name__)

dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])

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

@dashboard.get("/kpi", response_model=KPIData)
async def get_kpis():
    """
    Calculate KPIs based on enabled documents in the knowledge base.
    """
    logger.info("Calculating Dashboard KPIs from documents...")
    
    # 1. Fetch enabled documents
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    if not enabled_docs:
        # Return defaults if no data
        return KPIData()
        
    # 2. Prepare Context from Doc Summaries or first chunks
    # We use summaries if available, or just the first 2000 chars of content per doc
    # to fit in context window efficiently.
    context_text = ""
    for doc in enabled_docs:
        # Try to find a summary property if it exists, otherwise use raw text
        # Assuming SimbaDoc structure might vary, we'll try to extract text safely
        content = ""
        if hasattr(doc, "content") and doc.content:
             content = doc.content[:3000] # Take first 3000 chars
        elif hasattr(doc, "documents") and doc.documents:
             # Concatenate first few chunks
             content = "\n".join([c.page_content for c in doc.documents[:3]])
        
        context_text += f"--- Document: {doc.metadata.filename} ---\n{content}\n\n"
    
    if not context_text.strip():
        return KPIData()

    # 3. Use LLM to extract/calculate KPIs
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
        If a specific value is not found, make a REASONABLE ESTIMATE based on the context of the document (e.g. if it talks about heavy rain, rainfall is likely high and trend up).
        If absolutely no info is available, return "N/A" or safe defaults.
        
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
        return KPIData(**result)
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")
        return KPIData() # Fallback
