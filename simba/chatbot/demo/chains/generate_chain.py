# Chain
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from simba.core.factories.llm_factory import get_llm

# prompt = hub.pull("rlm/rag-prompt")
prompt_template = ChatPromptTemplate.from_template(
    """
    You are a strictly constrained AI assistant named Simba.
    
    You are Simba, a helpful and intelligent AI assistant.
    
    Instructions:
    1. Answer the user's question using the provided Document Summaries, Detailed Context, and Chat History.
    2. If the user asks for a specific format (e.g., "in 1 phrase", "shorter"), apply that constraint to the information you have.
    3. If the chat history contains the relevant information, use it!
    4. If you really cannot answer based on any of the provided information, politely say so, but try your best to infer the answer from the context.

    Summaries:
    {summaries}
    
    Detailed Context:
    {context}
    
    Chat History:
    {chat_history}
    
    User Question: {question}
    
    Answer:
"""
)

llm = get_llm()
generate_chain = prompt_template | llm | StrOutputParser()
