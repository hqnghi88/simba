import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simba.chatbot.demo.chains.transform_query_chain import question_rewrite_chain
from simba.core.factories.vector_store_factory import VectorStoreFactory

def verify_rewrite_and_retrieve():
    print("--- Verifying Contextual Rewrite & Retrieval ---")

    # 1. Mock Chat History
    chat_history = """
    User: Summarize the paper goodtechs_2025.
    Simba: The paper 'goodtechs_2025' discusses a new framework for agent-based modeling in complex systems, highlighting decentralized interactions and scenario flexibility.
    """
    
    current_question = "in 1 phrase"
    print(f"\n[Mock Context]")
    print(f"History: {chat_history.strip()}")
    print(f"Current Input: '{current_question}'")

    # 2. Test Query Rewriting (Transform Chain)
    print(f"\n[Step 1] Testing Query Rewrite...")
    try:
        rewritten = question_rewrite_chain.invoke({
            "question": current_question,
            "chat_history": chat_history
        })
        
        print(f"  Rewritten Sub-queries: {rewritten.sub_queries}")
        
        if not rewritten.sub_queries:
             print("  ❌ Rewrite Failed: No sub-queries generated.")
             return
             
        best_query = rewritten.sub_queries[0]
        print(f"  Using Best Query: '{best_query}'")
        
        # Check if it actually incorporated context
        if "goodtechs" not in best_query.lower() and "paper" not in best_query.lower():
             print("  ⚠️ WARNING: The rewritten query might barely use context. It should mention the topic.")

    except Exception as e:
        print(f"  ❌ Error in Rewrite Chain: {e}")
        return

    # 3. Test Retrieval with Rewritten Query
    print(f"\n[Step 2] Testing Retrieval with '{best_query}'...")
    vs = VectorStoreFactory.get_vector_store()
    
    try:
        results = vs.similarity_search(best_query, k=3)
        print(f"  Retrieved chunks: {len(results)}")
        
        if len(results) > 0:
            print("  ✅ SUCCESS: Found documents using rewritten query.")
            print(f"  Source: {results[0].metadata.get('source', 'unknown')}")
        else:
            print("  ❌ FAILURE: No documents found even with rewritten query.")

    except Exception as e:
        print(f"  ❌ Error in Retrieval: {e}")

if __name__ == "__main__":
    verify_rewrite_and_retrieve()
