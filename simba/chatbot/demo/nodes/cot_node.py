from simba.chatbot.demo.chains.cot_chain import cot_chain
from simba.chatbot.demo.state import State
from simba.core.factories.database_factory import get_database


def cot(state: State):
    db = get_database()
    # Fetch all documents fresh for each request to get latest summaries
    all_docs = db.get_all_documents()
    all_summaries = "\n\n".join(f"**{doc.id}**\n{doc.metadata.summary}" for doc in all_docs)

    question = state["messages"][-1].content
    sub_queries = state.get("sub_queries", []) 
    
    response = cot_chain.invoke({"question": question, "sub_queries": sub_queries, "summaries": all_summaries})
    is_summary_enough = response.is_summary_enough
    ids, summaries = response.id, response.page_content
    
    if is_summary_enough:
        return {
            "summaries": summaries,
            "sub_queries": sub_queries,
            "question": question,
            "documents": [],
            "is_summary_enough": response.is_summary_enough
        }
    else:
        context = db.get_document(ids)
        # Ensure context is a list
        if context and not isinstance(context, list):
            context = [context]
        elif context is None:
            context = []
            
        return {
            "summaries": summaries,
            "sub_queries": sub_queries,
            "question": question,
            "documents": context,
            "is_summary_enough": response.is_summary_enough
        }