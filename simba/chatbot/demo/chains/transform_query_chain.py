from typing import List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from simba.core.factories.llm_factory import get_llm

# LLM
llm = get_llm()

class Questions(BaseModel):
    sub_queries: List[str] = Field(description="the 3 sub queries to be used for retrieval")


# Prompt
system = """
    **Role**    
    You are an assistant that helps information‑retrieval systems.  
    Your job is to:  

    1. **Reformulate the user's original question** so it becomes a standalone, search-friendly query.
       - If the user input is a follow-up (e.g., "shorter", "why?", "explain that"), combine it with the topic from the chat history.
       - Example: History="Summarize X", Input="shorter" -> Query="Summarize X briefly".
    2. **Propose 3 concise sub‑queries** that help answer the user's core intent.
    3. Keep everything **short, specific, and self‑contained**.
    
    think step by step knowing that you're in context of insurance/tech docs.

    IMPORTANT: You MUST respond with ONLY a valid JSON object. No other text.
    Expected format: {{"sub_queries": ["query1", "query2", "query3"]}}
    """
re_write_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        (
            "human",
            "Here is the chat history:\n{chat_history}\n\nHere is the initial question: \n\n {question} \n Formulate a standalone question that can be understood without the chat history.",
        ),
    ]
)

question_rewrite_chain = re_write_prompt | llm.with_structured_output(Questions, method="json_mode")
