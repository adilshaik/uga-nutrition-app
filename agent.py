# utils/nutrition_agent.py
import streamlit as st
from datetime import datetime

def generate_nutrition_response(question: str, context: str) -> str:
    if "protein" in question:
        return """🥩 **Protein Boost Plan:**\n\nBolton: Grilled chicken (45g), Greek yogurt (25g)\nSnelling: Turkey burger (38g), cottage cheese (28g)"""
    elif "bolton" in question:
        return """🍽️ **Bolton Today:**\nGrilled salmon (32g protein, 280 cal)\nChicken stir-fry (38g, 420 cal)"""
    # ... add other responses
    return "💪 Great question! Aim for 30g protein per meal."

def render_agent_page():
    """Full agent UI"""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    st.markdown("## 🤖 Nutrition Agent")
    
    # Suggested prompts
    cols = st.columns(2)
    prompts = ["High protein at Bolton?", "Hit 150g protein today?", "Low cal dinner?", "Plan my day"]
    for i, prompt in enumerate(prompts):
        with cols[i%2]:
            if st.button(prompt, key=f"agent_{i}"):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                st.rerun()
    
    # Chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input
    if user_input := st.chat_input("Ask about nutrition..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            context = f"Goals: {st.session_state.get('daily_targets', {})}"
            response = generate_nutrition_response(user_input.lower(), context)
            st.markdown(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()
