"""
UGA Nutrition App - Streamlit PoC
A nutrition guidance application for UGA students using AI-powered recommendations
"""

import streamlit as st
from datetime import datetime, timedelta
import json

# Show instructions first time
if "show_instructions" not in st.session_state:
    st.session_state.show_instructions = True


# Page configuration
st.set_page_config(
    page_title="UGA Nutrition Assistant",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UGA branding
st.markdown("""
<style>
    .stApp {
        background-color: #f8f9fa;
    }
    .main-header {
        background: linear-gradient(135deg, #BA0C2F 0%, #000000 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #BA0C2F;
    }
    .goal-card {
        background: linear-gradient(135deg, #BA0C2F 0%, #9a0a27 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .food-item {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
    }
    .food-item:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-color: #BA0C2F;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background: #e3f2fd;
        margin-left: 2rem;
    }
    .assistant-message {
        background: #f5f5f5;
        margin-right: 2rem;
        border-left: 3px solid #BA0C2F;
    }
    .citation {
        font-size: 0.85rem;
        color: #666;
        background: #fff3cd;
        padding: 0.5rem;
        border-radius: 5px;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    defaults = {
        'user_profile': None,
        'goals': None,
        'daily_targets': None,
        'food_log': [],
        'chat_history': [],
        'current_page': 'home',
        'onboarding_complete': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Sidebar navigation
with st.sidebar:
    st.image("https://brand.uga.edu/wp-content/uploads/GEORGIA-FS-FC-1024x439.png", width=200)
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["🏠 Home & Goals", "🍽️ Dining Finder", "📝 Food Log", "🤖 Ask the Agent", "📊 Progress", "⚙️ Settings"],
        index=0
    )
    
    st.markdown("---")

    # Quick stats if goals are set
    if st.session_state.goals:
        st.markdown("### Today's Progress")
        targets = st.session_state.daily_targets or {}
        
        # Calculate today's totals from log
        today = datetime.now().date()
        today_log = [entry for entry in st.session_state.food_log 
                     if entry.get('date') == str(today)]
        
        total_calories = sum(entry.get('calories', 0) for entry in today_log)
        total_protein = sum(entry.get('protein', 0) for entry in today_log)
        
        cal_target = targets.get('calories', 2000)
        protein_target = targets.get('protein', 150)
        
        st.progress(min(total_calories / cal_target, 1.0))
        st.caption(f"Calories: {total_calories}/{cal_target}")
        
        st.progress(min(total_protein / protein_target, 1.0))
        st.caption(f"Protein: {total_protein}g/{protein_target}g")

# Main content based on selected page
if "Home" in page:
    st.markdown("""
    <div class="main-header">
        <h1>🐾 UGA Nutrition Assistant</h1>
        <p>Your personalized nutrition guide powered by UGA Dining Services</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.onboarding_complete:
        st.markdown("## Let's Set Up Your Nutrition Goals")
        st.markdown("Answer a few quick questions to get personalized recommendations.")
        
        with st.form("goal_setup"):
            col1, col2 = st.columns(2)
            
            with col1:
                goal_type = st.selectbox(
                    "What's your primary goal?",
                    ["Build Muscle / Bulk Up", "Lose Fat / Cut", "Maintain Weight", 
                     "Improve Energy", "General Health", "Athletic Performance"]
                )
                
                weight = st.number_input("Current weight (lbs)", min_value=80, max_value=400, value=160)
                height_ft = st.number_input("Height (feet)", min_value=4, max_value=7, value=5)
                height_in = st.number_input("Height (inches)", min_value=0, max_value=11, value=9)
                
            with col2:
                activity_level = st.selectbox(
                    "Activity level",
                    ["Sedentary (little exercise)", "Light (1-3 days/week)", 
                     "Moderate (3-5 days/week)", "Active (6-7 days/week)", 
                     "Very Active (athlete/physical job)"]
                )
                
                dining_preference = st.multiselect(
                    "Preferred dining halls",
                    ["Bolton", "Snelling", "Village Summit", "Niche", "O-House"],
                    default=["Bolton"]
                )
                
                dietary_restrictions = st.multiselect(
                    "Dietary restrictions (optional)",
                    ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", 
                     "Nut Allergy", "Shellfish Allergy", "Halal", "Kosher"]
                )
            
            submitted = st.form_submit_button("Calculate My Targets", type="primary")
            
            if submitted:
                # Calculate BMR and targets (Mifflin-St Jeor)
                height_cm = (height_ft * 12 + height_in) * 2.54
                weight_kg = weight * 0.453592
                
                # Simplified calculation (assuming average age of 20)
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * 20 + 5
                
                activity_multipliers = {
                    "Sedentary (little exercise)": 1.2,
                    "Light (1-3 days/week)": 1.375,
                    "Moderate (3-5 days/week)": 1.55,
                    "Active (6-7 days/week)": 1.725,
                    "Very Active (athlete/physical job)": 1.9
                }
                
                tdee = bmr * activity_multipliers[activity_level]
                
                # Adjust based on goal
                goal_adjustments = {
                    "Build Muscle / Bulk Up": (300, 1.0),  # +300 cal, 1g protein/lb
                    "Lose Fat / Cut": (-500, 1.0),
                    "Maintain Weight": (0, 0.8),
                    "Improve Energy": (0, 0.8),
                    "General Health": (0, 0.8),
                    "Athletic Performance": (200, 1.0)
                }
                
                cal_adj, protein_mult = goal_adjustments[goal_type]
                target_calories = int(tdee + cal_adj)
                target_protein = int(weight * protein_mult)
                
                st.session_state.user_profile = {
                    'weight': weight,
                    'height_ft': height_ft,
                    'height_in': height_in,
                    'activity_level': activity_level,
                    'dining_preference': dining_preference,
                    'dietary_restrictions': dietary_restrictions
                }
                
                st.session_state.goals = {
                    'type': goal_type,
                    'created_at': str(datetime.now())
                }
                
                st.session_state.daily_targets = {
                    'calories': target_calories,
                    'protein': target_protein,
                    'carbs': int(target_calories * 0.45 / 4),
                    'fat': int(target_calories * 0.25 / 9),
                    'fiber': 30,
                    'sodium': 2300
                }
                
                st.session_state.onboarding_complete = True
                st.rerun()
    
    else:
        # Show current goals and quick actions
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### Your Daily Targets")
            targets = st.session_state.daily_targets
            
            t_cols = st.columns(4)
            with t_cols[0]:
                st.metric("Calories", f"{targets['calories']} kcal")
            with t_cols[1]:
                st.metric("Protein", f"{targets['protein']}g")
            with t_cols[2]:
                st.metric("Carbs", f"{targets['carbs']}g")
            with t_cols[3]:
                st.metric("Fat", f"{targets['fat']}g")
            
            st.markdown("### Quick Actions")
            action_cols = st.columns(3)
            with action_cols[0]:
                if st.button("🍽️ Find Today's Meals", use_container_width=True):
                    st.session_state.current_page = 'dining'
                    st.rerun()
            with action_cols[1]:
                if st.button("📝 Log a Meal", use_container_width=True):
                    st.session_state.current_page = 'log'
                    st.rerun()
            with action_cols[2]:
                if st.button("🤖 Get Recommendations", use_container_width=True):
                    st.session_state.current_page = 'agent'
                    st.rerun()
        
        with col2:
            st.markdown(f"""
            <div class="goal-card">
                <h4>Current Goal</h4>
                <h2>{st.session_state.goals['type']}</h2>
                <p>Started: {st.session_state.goals['created_at'][:10]}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Reset Goals", type="secondary"):
                st.session_state.onboarding_complete = False
                st.session_state.goals = None
                st.session_state.daily_targets = None
                st.rerun()

elif "Dining" in page:
    st.markdown("## 🍽️ UGA Dining Finder")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_hall = st.selectbox("Dining Hall", ["All", "Bolton", "Snelling", "Village Summit", "Niche", "O-House"])
    with col2:
        selected_date = st.date_input("Date", datetime.now())
    with col3:
        selected_meal = st.selectbox("Meal Period", ["All", "Breakfast", "Lunch", "Dinner", "Late Night"])
    with col4:
        search_query = st.text_input("Search items", placeholder="e.g., chicken, salmon...")
    
    # Sample menu data (would be replaced with actual UGA data)
    sample_menu = [
        {"name": "Grilled Salmon", "hall": "Bolton", "meal": "Dinner", "calories": 350, "protein": 40, "carbs": 2, "fat": 18, "tags": ["High Protein", "Gluten-Free"]},
        {"name": "Chicken Breast", "hall": "Bolton", "meal": "Lunch", "calories": 280, "protein": 45, "carbs": 0, "fat": 8, "tags": ["High Protein", "Low Carb"]},
        {"name": "Brown Rice Bowl", "hall": "Snelling", "meal": "Lunch", "calories": 420, "protein": 12, "carbs": 68, "fat": 8, "tags": ["Vegetarian", "High Fiber"]},
        {"name": "Greek Yogurt Parfait", "hall": "Bolton", "meal": "Breakfast", "calories": 220, "protein": 18, "carbs": 28, "fat": 4, "tags": ["Vegetarian", "High Protein"]},
        {"name": "Turkey Wrap", "hall": "Village Summit", "meal": "Lunch", "calories": 380, "protein": 28, "carbs": 35, "fat": 14, "tags": ["High Protein"]},
        {"name": "Veggie Stir Fry", "hall": "Niche", "meal": "Dinner", "calories": 320, "protein": 15, "carbs": 42, "fat": 10, "tags": ["Vegetarian", "Vegan"]},
        {"name": "Scrambled Eggs", "hall": "Bolton", "meal": "Breakfast", "calories": 180, "protein": 14, "carbs": 2, "fat": 12, "tags": ["Vegetarian", "Gluten-Free"]},
        {"name": "Oatmeal with Berries", "hall": "Snelling", "meal": "Breakfast", "calories": 280, "protein": 8, "carbs": 52, "fat": 5, "tags": ["Vegetarian", "High Fiber"]},
    ]
    
    # Filter menu items
    filtered_menu = sample_menu
    if selected_hall != "All":
        filtered_menu = [item for item in filtered_menu if item['hall'] == selected_hall]
    if selected_meal != "All":
        filtered_menu = [item for item in filtered_menu if item['meal'] == selected_meal]
    if search_query:
        filtered_menu = [item for item in filtered_menu if search_query.lower() in item['name'].lower()]
    
    # Display menu items
    st.markdown(f"### {len(filtered_menu)} items found")
    
    for item in filtered_menu:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{item['name']}**")
                st.caption(f"📍 {item['hall']} • {item['meal']}")
                st.caption(" ".join([f"`{tag}`" for tag in item['tags']]))
            with col2:
                st.markdown(f"🔥 {item['calories']} cal | 🥩 {item['protein']}g protein")
                st.caption(f"🍞 {item['carbs']}g carbs | 🧈 {item['fat']}g fat")
            with col3:
                if st.button("➕ Add", key=f"add_{item['name']}"):
                    log_entry = {
                        'date': str(datetime.now().date()),
                        'time': datetime.now().strftime("%H:%M"),
                        'name': item['name'],
                        'hall': item['hall'],
                        'meal': item['meal'],
                        'calories': item['calories'],
                        'protein': item['protein'],
                        'carbs': item['carbs'],
                        'fat': item['fat'],
                        'servings': 1
                    }
                    st.session_state.food_log.append(log_entry)
                    st.success(f"Added {item['name']} to your log!")
            st.markdown("---")

elif "Log" in page:
    st.markdown("## 📝 Food Log")
    
    # Date selector
    selected_date = st.date_input("View date", datetime.now())
    
    # Filter log for selected date
    day_log = [entry for entry in st.session_state.food_log 
               if entry.get('date') == str(selected_date)]
    
    if day_log:
        # Daily summary
        total_cal = sum(e['calories'] * e.get('servings', 1) for e in day_log)
        total_protein = sum(e['protein'] * e.get('servings', 1) for e in day_log)
        total_carbs = sum(e['carbs'] * e.get('servings', 1) for e in day_log)
        total_fat = sum(e['fat'] * e.get('servings', 1) for e in day_log)
        
        targets = st.session_state.daily_targets or {'calories': 2000, 'protein': 150, 'carbs': 250, 'fat': 65}
        
        st.markdown("### Daily Summary")
        cols = st.columns(4)
        with cols[0]:
            delta = total_cal - targets['calories']
            st.metric("Calories", f"{total_cal}", f"{delta:+d} from target")
        with cols[1]:
            delta = total_protein - targets['protein']
            st.metric("Protein", f"{total_protein}g", f"{delta:+d}g from target")
        with cols[2]:
            st.metric("Carbs", f"{total_carbs}g")
        with cols[3]:
            st.metric("Fat", f"{total_fat}g")
        
        st.markdown("---")
        st.markdown("### Logged Items")
        
        for i, entry in enumerate(day_log):
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{entry['name']}**")
                    st.caption(f"📍 {entry.get('hall', 'N/A')} • {entry.get('meal', 'N/A')} • {entry['time']}")
                with col2:
                    st.markdown(f"🔥 {entry['calories']} cal | 🥩 {entry['protein']}g")
                    servings = st.number_input("Servings", min_value=0.5, max_value=5.0, 
                                               value=float(entry.get('servings', 1)), 
                                               step=0.5, key=f"serv_{i}")
                    if servings != entry.get('servings', 1):
                        st.session_state.food_log[st.session_state.food_log.index(entry)]['servings'] = servings
                with col3:
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.food_log.remove(entry)
                        st.rerun()
                st.markdown("---")
        
        # Export options
        st.markdown("### Export")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export as CSV"):
                import csv
                import io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=day_log[0].keys())
                writer.writeheader()
                writer.writerows(day_log)
                st.download_button("Download CSV", output.getvalue(), "food_log.csv", "text/csv")
        with col2:
            if st.button("📥 Export as JSON"):
                st.download_button("Download JSON", json.dumps(day_log, indent=2), "food_log.json", "application/json")
    
    else:
        st.info("No items logged for this date. Visit the Dining Finder to add meals!")
        if st.button("🍽️ Go to Dining Finder"):
            st.rerun()

elif "Agent" in page:
    if "agent_authenticated" not in st.session_state:
        st.session_state.agent_authenticated = False
    
    if not st.session_state.agent_authenticated:
        st.markdown("### 🔐 Enter password to access Nutrition Agent")
        password = st.text_input("Password:", type="password", key="agent_pass")
        if st.button("Unlock Agent", key="unlock_btn", use_container_width=True):
            if password == st.secrets["AGENT_PASSWORD"]:
                st.session_state.agent_authenticated = True
                st.success("✅ Access granted! Welcome to the Nutrition Agent.")
                st.rerun()
            else:
                st.error("❌ Incorrect password")
        st.stop()
    
    # === YOUR ORIGINAL AGENT CODE (NOW PROTECTED) ===
    st.markdown("## 🤖 Ask the Nutrition Agent")
    st.markdown("""
    <div class="citation">
        💡 <strong>Tip:</strong> Ask me about meal suggestions, how to hit your protein goals, 
        or what's available at the dining halls today!
    </div>
    """, unsafe_allow_html=True)
    
    # Suggested prompts
    st.markdown("### Suggested Questions")
    prompt_cols = st.columns(2)
    suggested_prompts = [
        "What should I eat at Bolton to hit my protein goal?",
        "How can I adjust my dinner to stay under calories?",
        "What are some high-protein breakfast options?",
        "Help me plan my meals for today"
    ]
    
    for i, prompt in enumerate(suggested_prompts):
        with prompt_cols[i % 2]:
            if st.button(prompt, key=f"prompt_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    # Chat interface
    st.markdown("---")
    
    # Use log context toggle
    use_log = st.checkbox("📝 Include my food log for context", value=True)
    
    # Display chat history
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You:</strong> {message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <strong>🤖 Agent:</strong> {message["content"]}
            </div>
            """, unsafe_allow_html=True)
            if "citation" in message:
                st.markdown(f"""
                <div class="citation">
                    📚 Source: {message["citation"]}
                </div>
                """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Ask about nutrition, dining options, or your goals...")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Build context for the agent
        context = build_agent_context(use_log)
        
        # Get response from agent (placeholder - integrate with Groq)
        response = get_agent_response(user_input, context)
        
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": response["message"],
            "citation": response.get("citation", "")
        })
        st.rerun()
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

elif "Progress" in page:
    st.markdown("## 📊 Progress Tracking")
    
    if not st.session_state.food_log:
        st.info("Start logging meals to see your progress!")
    else:
        # Weekly summary
        st.markdown("### Weekly Overview")
        
        # Calculate weekly averages
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        week_log = [entry for entry in st.session_state.food_log 
                    if week_ago <= datetime.strptime(entry['date'], '%Y-%m-%d').date() <= today]
        
        if week_log:
            # Group by date
            from collections import defaultdict
            daily_totals = defaultdict(lambda: {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0})
            
            for entry in week_log:
                date = entry['date']
                daily_totals[date]['calories'] += entry['calories'] * entry.get('servings', 1)
                daily_totals[date]['protein'] += entry['protein'] * entry.get('servings', 1)
                daily_totals[date]['carbs'] += entry['carbs'] * entry.get('servings', 1)
                daily_totals[date]['fat'] += entry['fat'] * entry.get('servings', 1)
            
            # Display chart
            import pandas as pd
            df = pd.DataFrame([
                {'Date': k, **v} for k, v in daily_totals.items()
            ])
            
            if not df.empty:
                st.line_chart(df.set_index('Date')[['calories']])
                st.line_chart(df.set_index('Date')[['protein', 'carbs', 'fat']])
        
        # Goal adherence
        st.markdown("### Goal Adherence")
        targets = st.session_state.daily_targets or {}
        
        if targets and week_log:
            days_logged = len(set(entry['date'] for entry in week_log))
            days_on_target = 0  # Simplified calculation
            
            st.metric("Days Logged This Week", days_logged)
            st.metric("Avg Daily Calories", 
                      f"{sum(daily_totals[d]['calories'] for d in daily_totals) // max(len(daily_totals), 1)}")
            st.metric("Avg Daily Protein", 
                      f"{sum(daily_totals[d]['protein'] for d in daily_totals) // max(len(daily_totals), 1)}g")

elif "Settings" in page:
    st.markdown("## ⚙️ Settings")
    
    st.markdown("### Profile")
    if st.session_state.user_profile:
        st.json(st.session_state.user_profile)
    
    st.markdown("### Data Management")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear All Data", type="secondary"):
            for key in ['user_profile', 'goals', 'daily_targets', 'food_log', 'chat_history']:
                st.session_state[key] = None if key != 'food_log' and key != 'chat_history' else []
            st.session_state.onboarding_complete = False
            st.success("All data cleared!")
            st.rerun()
    
    with col2:
        if st.button("📥 Export All Data"):
            all_data = {
                'profile': st.session_state.user_profile,
                'goals': st.session_state.goals,
                'targets': st.session_state.daily_targets,
                'food_log': st.session_state.food_log
            }
            st.download_button("Download", json.dumps(all_data, indent=2), "uga_nutrition_data.json")
    
    st.markdown("### API Configuration")
    st.text_input("Groq API Key", type="password", help="Enter your Groq API key for AI features")
    st.info("Get your API key at https://console.groq.com")


# Helper functions
def build_agent_context(include_log=True):
    """Build context for the AI agent"""
    context = {
        'user_profile': st.session_state.user_profile,
        'goals': st.session_state.goals,
        'targets': st.session_state.daily_targets,
    }
    
    if include_log:
        today = str(datetime.now().date())
        today_log = [e for e in st.session_state.food_log if e.get('date') == today]
        context['today_log'] = today_log
        context['today_totals'] = {
            'calories': sum(e['calories'] * e.get('servings', 1) for e in today_log),
            'protein': sum(e['protein'] * e.get('servings', 1) for e in today_log),
        }
    
    return context


def get_agent_response(user_input, context):
    """
    Get response from the AI agent.
    This is a placeholder - integrate with Groq API.
    """
    # Placeholder response logic
    user_input_lower = user_input.lower()
    
    if 'protein' in user_input_lower:
        return {
            "message": f"""Based on your goal of **{context.get('goals', {}).get('type', 'building muscle')}**, 
            I recommend aiming for {context.get('targets', {}).get('protein', 150)}g of protein daily.
            
            **Top high-protein options at Bolton today:**
            - Grilled Salmon (40g protein) - Dinner
            - Chicken Breast (45g protein) - Lunch
            - Greek Yogurt Parfait (18g protein) - Breakfast
            
            You've logged {context.get('today_totals', {}).get('protein', 0)}g protein so far today.""",
            "citation": "UGA Dining Services Menu Data, Accessed Today"
        }
    
    elif 'breakfast' in user_input_lower:
        return {
            "message": """Here are some great breakfast options for your goals:
            
            **High Protein:**
            - Scrambled Eggs (14g protein) at Bolton
            - Greek Yogurt Parfait (18g protein) at Bolton
            
            **High Energy:**
            - Oatmeal with Berries (8g protein, 52g carbs) at Snelling
            
            Would you like me to suggest a complete breakfast meal plan?""",
            "citation": "UGA Dining Services Menu"
        }
    
    else:
        return {
            "message": f"""I'd be happy to help with your nutrition goals! 
            
            Based on your profile, you're working towards **{context.get('goals', {}).get('type', 'your goals')}**.
            
            Your daily targets are:
            - Calories: {context.get('targets', {}).get('calories', 'Not set')}
            - Protein: {context.get('targets', {}).get('protein', 'Not set')}g
            
            What specific aspect would you like help with? I can:
            - Suggest meals from today's dining hall menus
            - Help you hit your protein targets
            - Recommend adjustments based on your food log""",
            "citation": ""
        }


# Footer
st.markdown("---")
st.caption("UGA Nutrition Assistant • Powered by UGA Dining Services Data • Not medical advice")
