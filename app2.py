"""
UGA Nutrition App - Streamlit PoC
A nutrition guidance application for UGA students using AI-powered recommendations
"""

import streamlit as st
from datetime import datetime, timedelta
import json
import pandas as pd

from vision import VegetableDetector
import tempfile
import os
from PIL import Image

# Cache CSV
@st.cache_data
def load_menu_cached():
    """Cached CSV loader - runs once per session"""
    return load_menu_from_csv()

@st.cache_data
def load_menu_data():
    """Load UGA menu - ONLY ONCE"""
    return pd.read_csv("uga_menu.csv")  # or your load function

@st.cache_data
def get_today_stats():
    """Calculate daily stats - cached"""
    today = str(datetime.now().date())
    today_log = [e for e in st.session_state.food_log if e.get('date') == today]
    return {
        'calories': sum(e.get('calories', 0) * e.get('servings', 1) for e in today_log),
        'protein': sum(e.get('protein', 0) * e.get('servings', 1) for e in today_log)
    }

@st.cache_resource
def load_yolo_detector():
    """YOLO detector - cached forever"""
    return VegetableDetector(conf_threshold=0.25)


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
    .stApp { background-color: #f8f9fa; }
    .main-header {
        background: linear-gradient(135deg, #BA0C2F 0%, #000000 100%);
        padding: 2rem; border-radius: 10px; color: white; margin-bottom: 2rem;
    }
    .metric-card {
        background: white; padding: 1.5rem; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 4px solid #BA0C2F;
    }
    .goal-card {
        background: linear-gradient(135deg, #BA0C2F 0%, #9a0a27 100%);
        color: white; padding: 1.5rem; border-radius: 10px; margin: 1rem 0;
    }
    .food-item {
        background: white; padding: 1rem; border-radius: 8px;
        margin: 0.5rem 0; border: 1px solid #e0e0e0;
        transition: all 0.2s;
    }
    .food-item:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-color: #BA0C2F;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    defaults = {
        'user_profile': None, 'goals': None, 'daily_targets': None,
        'food_log': [], 'chat_history': [], 'current_page': 'home',
        'onboarding_complete': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

def parse_nutrition_value(value):
    """Convert nutrition strings like '7.6g', '150', or '' to float"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    # Remove common units: g, mg, cal, kcal, etc.
    value_str = str(value).strip()
    if value_str.lower().endswith(('g', 'mg', 'cal', 'kcal')):
        value_str = value_str[:-1].strip()
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0

def parse_nutrition_value(value):
    """Convert nutrition strings like '7.6g', '150', or '' to float"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    value_str = str(value).strip()
    if value_str.lower().endswith(('g', 'mg', 'cal', 'kcal')):
        value_str = value_str[:-1].strip()
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0

### COMPLETE FIXED load_menu_from_csv function
def load_menu_from_csv(file_path=r'C:\Users\nikhi\uga-nutrition-app\uga-nutrition-export.csv', encoding="latin1"):
    df = pd.read_csv(file_path, encoding=encoding)
    
    # Keep only required columns
    columns_to_show = [
        "Location_Name",
        "Menu_Category_Name", 
        "Recipe_Print_As_Name",
        "ServingSize",
        "CaloriesVal",
        "TotalFatVal",
        "TotalCarbVal",
        "ProteinVal"
    ]
    df = df[columns_to_show].head(50)
    
    menu = []
    
    for i, row in df.iterrows():
        # BUILD DATA ONLY - NO UI/DISPLAY
        menu.append({
            'name': row['Recipe_Print_As_Name'],
            'hall': row['Location_Name'],
            'meal': row['Menu_Category_Name'],
            'calories': parse_nutrition_value(row['CaloriesVal']),
            'protein': parse_nutrition_value(row['ProteinVal']),
            'carbs': parse_nutrition_value(row['TotalCarbVal']),
            'fat': parse_nutrition_value(row['TotalFatVal']),
            'serving_size': str(row['ServingSize']) if pd.notna(row['ServingSize']) else '1 serving',
            'tags': []
        })
    
    return menu  # ONLY returns data structure, NO UI rendering

# Sidebar navigation
with st.sidebar:
    st.image("https://brand.uga.edu/wp-content/uploads/GEORGIA-FS-FC-1024x439.png", width=200)
    st.markdown("---")
    
    selected_page = st.radio(
        "Navigation", 
        ["🏠 Home & Goals", "🍽️ Dining Finder", "📝 Food Log", "🖼️ Food Scanner", "🤖 Ask the Agent", "📊 Progress", "⚙️ Settings"],
        index=0
    )

    if "next_page" in st.session_state:

        selected_page = st.session_state.next_page  # Quick action overrides!
        del st.session_state.next_page     # Clear after use
    
    
    st.markdown("---")

    #Cache function
    @st.cache_data
    def get_sidebar_stats(_food_log, _daily_targets, _today_str):
        today_log = [e for e in _food_log if e.get('date') == _today_str]
        return {
            'calories': sum(e.get('calories', 0) * e.get('servings', 1) for e in today_log),
            'protein': sum(e.get('protein', 0) * e.get('servings', 1) for e in today_log)
        }

    
    if st.session_state.goals:
        st.markdown("### Today's Progress")
        targets = st.session_state.daily_targets or {}
        today_str = str(datetime.now().date())
        
        # ⚡ CACHED - 10x faster!
        stats = get_sidebar_stats(
            st.session_state.food_log, 
            targets, 
            today_str
        )
        
        cal_target = targets.get('calories', 2000)
        protein_target = targets.get('protein', 150)
        
        st.progress(min(stats['calories'] / cal_target, 1.0))
        st.caption(f"Calories: {int(stats['calories'])}/{cal_target}")
        st.progress(min(stats['protein'] / protein_target, 1.0))
        st.caption(f"Protein: {int(stats['protein'])}g/{protein_target}g")

    #Centralized page state    
    if "page" not in st.session_state:
        st.session_state.page = selected_page
    else:
        if selected_page != st.session_state.page:
            st.session_state.page = selected_page

    page = st.session_state.page

# Main content by page
if "Home" in page or page == "🏠 Home & Goals":
    st.markdown("""
    <div class="main-header">
        <h1>🐾 UGA Nutrition Assistant</h1>
        <p>Your personalized nutrition guide powered by UGA Dining Services</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.onboarding_complete:
        st.markdown("## Let's Set Up Your Nutrition Goals")
        with st.form("goal_setup"):
            col1, col2 = st.columns(2)
            with col1:
                goal_type = st.selectbox("Primary goal?", 
                    ["Build Muscle / Bulk Up", "Lose Fat / Cut", "Maintain Weight", 
                     "Improve Energy", "General Health", "Athletic Performance"])
                weight = st.number_input("Weight (lbs)", min_value=80, max_value=400, value=160)
                height_ft = st.number_input("Height (feet)", min_value=4, max_value=7, value=5)
                height_in = st.number_input("Height (inches)", min_value=0, max_value=11, value=9)
            
            with col2:
                activity_level = st.selectbox("Activity level", 
                    ["Sedentary (little exercise)", "Light (1-3 days/week)", 
                     "Moderate (3-5 days/week)", "Active (6-7 days/week)", 
                     "Very Active (athlete/physical job)"])
                dining_preference = st.multiselect("Preferred dining halls", 
                    ["Bolton", "Snelling", "Village Summit", "Niche", "O-House"], default=["Bolton"])
                dietary_restrictions = st.multiselect("Dietary restrictions (optional)",
                    ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", 
                     "Nut Allergy", "Shellfish Allergy", "Halal", "Kosher"])
            
            if st.form_submit_button("Calculate My Targets", type="primary"):
                # Calculate targets (simplified Mifflin-St Jeor)
                height_cm = (height_ft * 12 + height_in) * 2.54
                weight_kg = weight * 0.453592
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * 20 + 5
                
                activity_multipliers = {
                    "Sedentary (little exercise)": 1.2, "Light (1-3 days/week)": 1.375,
                    "Moderate (3-5 days/week)": 1.55, "Active (6-7 days/week)": 1.725,
                    "Very Active (athlete/physical job)": 1.9
                }
                
                tdee = bmr * activity_multipliers[activity_level]
                goal_adjustments = {
                    "Build Muscle / Bulk Up": (300, 1.0), "Lose Fat / Cut": (-500, 1.0),
                    "Maintain Weight": (0, 0.8), "Improve Energy": (0, 0.8),
                    "General Health": (0, 0.8), "Athletic Performance": (200, 1.0)
                }
                cal_adj, protein_mult = goal_adjustments[goal_type]
                
                st.session_state.user_profile = {
                    'weight': weight, 'height_ft': height_ft, 'height_in': height_in,
                    'activity_level': activity_level, 'dining_preference': dining_preference,
                    'dietary_restrictions': dietary_restrictions
                }
                st.session_state.goals = {'type': goal_type, 'created_at': str(datetime.now())}
                st.session_state.daily_targets = {
                    'calories': int(tdee + cal_adj), 'protein': int(weight * protein_mult),
                    'carbs': int((tdee + cal_adj) * 0.45 / 4), 'fat': int((tdee + cal_adj) * 0.25 / 9)
                }
                st.session_state.onboarding_complete = True
                st.rerun()
    
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("### Your Daily Targets")
            targets = st.session_state.daily_targets
            t_cols = st.columns(4)
            with t_cols[0]: st.metric("Calories", f"{targets['calories']} kcal")
            with t_cols[1]: st.metric("Protein", f"{targets['protein']}g")
            with t_cols[2]: st.metric("Carbs", f"{targets['carbs']}g")
            with t_cols[3]: st.metric("Fat", f"{targets['fat']}g")
            
            st.markdown("### Quick Actions")
            action_cols = st.columns(3)

            with action_cols[0]:
                if st.button("🍽️ Find Today's Meals"):
                    st.session_state.next_page = "🍽️ Dining Finder"  # Use different key

            with action_cols[1]:
                if st.button("📝 Log a Meal"):
                    st.session_state.next_page = "📝 Food Log"

            with action_cols[2]:
                if st.button("🤖 Get Recommendations"):
                    st.session_state.next_page = "🤖 Ask the Agent"


            
    # 
  


elif "Dining" in page or page == "🍽️ Dining Finder":
    st.markdown("## 🍽️ UGA Dining Finder")
    
    # Filters (your exact code)
    col1, col2, col3, col4 = st.columns(4)
    with col1: 
        selected_hall = st.selectbox("Dining Hall", ["All", "Bolton", "Snelling", "Village Summit", "Niche", "O-House"])
    with col2: 
        selected_date = st.date_input("Date", datetime.now())
    with col3: 
        selected_meal = st.selectbox("Meal Period", ["All", "Breakfast", "Lunch", "Dinner", "Late Night"])
    with col4: 
        search_query = st.text_input("Search items", placeholder="e.g., chicken, salmon...")

    st.markdown("---")
    
    # ⚡ FAST CACHED LOAD
    sample_menu = load_menu_cached()
    
    # Filter (your exact logic)
    filtered_menu = sample_menu
    if selected_hall != "All":
        filtered_menu = [item for item in filtered_menu if item['hall'] == selected_hall]
    if selected_meal != "All":
        filtered_menu = [item for item in filtered_menu if item['meal'] == selected_meal]
    if search_query:
        filtered_menu = [item for item in filtered_menu if search_query.lower() in item['name'].lower()]
    
    st.markdown(f"### Found **{len(filtered_menu)}** items")
    
    for i, item in enumerate(filtered_menu):
        col1, col2 = st.columns([5, 1])
        
        with col1:
            st.markdown(f"""
            <div style="
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 10px;
                background-color: #fafafa;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            ">
                <div style="font-weight: bold; font-size: 18px; margin-bottom: 4px;">
                    {item['name']}
                </div>
                <div style="color: #666; font-size: 14px; margin-bottom: 8px;">
                    📍 {item['hall']} • {item['meal']}
                </div>
                <div style="font-size: 14px; line-height: 1.4;">
                    🔥 <strong>{float(item['calories']):.0f} cal</strong> | 
                    🥩 <strong>{float(item['protein']):.1f}g</strong> protein | 
                    🍞 <strong>{float(item['carbs']):.1f}g</strong> carbs | 
                    🧈 <strong>{float(item['fat']):.1f}g</strong> fat
                </div>
                <div style="font-size: 13px; color: #888; margin-top: 6px;">
                    🍽️ {item.get('serving_size', '1 serving')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # ✅ ALL BUTTONS WORK - Direct session_state update
            if st.button("➕ Add to Log", key=f"dining_add_{i}"):
                log_entry = {
                    'date': str(selected_date),
                    'time': datetime.now().strftime("%H:%M"),
                    'name': item['name'],
                    'hall': item['hall'],
                    'meal': item['meal'],
                    'calories': float(item['calories']),
                    'protein': float(item['protein']),
                    'carbs': float(item['carbs']),
                    'fat': float(item['fat']),
                    'serving_size': item.get('serving_size'),
                    'servings': 1,
                    'tags': item.get('tags', [])
                }
                st.session_state.food_log.append(log_entry)
                st.success(f"✅ Added **{item['name']}**!")
                
        
        st.markdown("---")
    
    if not filtered_menu:
        st.info("🔍 No items match your filters. Try different hall/meal!")

elif "Log" in page or page == "📝 Food Log":
    st.markdown("## 📝 Food Log")
    selected_date = st.date_input("View date", datetime.now())
    
    day_log = [e for e in st.session_state.food_log if e.get('date') == str(selected_date)]
    
    if day_log:
        total_cal = sum(e['calories'] * e.get('servings', 1) for e in day_log)
        total_protein = sum(e['protein'] * e.get('servings', 1) for e in day_log)
        total_carbs = sum(e['carbs'] * e.get('servings', 1) for e in day_log)
        total_fat = sum(e['fat'] * e.get('servings', 1) for e in day_log)
        
        targets = st.session_state.daily_targets or {'calories': 2000, 'protein': 150, 'carbs': 250, 'fat': 65}
        
        # Replace your entire Daily Summary metrics section:
        st.markdown("### Daily Summary")

        # Calculate totals (with float conversion)
        total_cal = sum(float(e['calories']) * e.get('servings', 1) for e in day_log)
        total_protein = sum(float(e['protein']) * e.get('servings', 1) for e in day_log)
        total_carbs = sum(float(e['carbs']) * e.get('servings', 1) for e in day_log)
        total_fat = sum(float(e['fat']) * e.get('servings', 1) for e in day_log)

        # Default targets
        targets = st.session_state.daily_targets or {
            'calories': 2000, 
            'protein': 150, 
            'carbs': 250, 
            'fat': 65
        }

        # FIXED metrics - ALL use int() conversion
        cols = st.columns(4)
        with cols[0]:
            delta_cal = int(total_cal - targets['calories'])
            st.metric("Calories", f"{int(total_cal)}", f"{delta_cal:+d}")
        with cols[1]:
            delta_protein = int(total_protein - targets['protein'])
            st.metric("Protein", f"{int(total_protein)}g", f"{delta_protein:+d}g")
        with cols[2]:
            st.metric("Carbs", f"{int(total_carbs)}g")
        with cols[3]:
            st.metric("Fat", f"{int(total_fat)}g")

        
        st.markdown("### Logged Items")
        for i, entry in enumerate(day_log):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{entry['name']}**")
                st.caption(f"📍 {entry.get('hall', 'N/A')} • {entry.get('meal', 'N/A')} • {entry['time']}")
            with col2:
                st.markdown(f"🔥 {entry['calories']} cal | 🥩 {entry['protein']}g")
                servings = st.number_input("Servings", min_value=0.5, max_value=5.0, 
                                         value=float(entry.get('servings', 1)), step=0.5, key=f"serv_{i}")
                if servings != entry.get('servings', 1):
                    st.session_state.food_log[st.session_state.food_log.index(entry)]['servings'] = servings
            with col3:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.food_log.remove(entry)
                    st.rerun()
            st.markdown("---")
        
        # Export
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export CSV"):
                import csv, io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=day_log[0].keys())
                writer.writeheader()
                writer.writerows(day_log)
                st.download_button("Download CSV", output.getvalue(), "food_log.csv", "text/csv")
        with col2:
            if st.button("📥 Export JSON"):
                st.download_button("Download JSON", json.dumps(day_log, indent=2), "food_log.json")
    else:
        st.info("No items logged. Visit Dining Finder to add meals!")
        if st.button("🍽️ Go to Dining Finder"): page = "🍽️ Dining Finder"; st.rerun()

elif "Scanner" in page or page == "🖼️ Food Scanner":
    st.markdown("## 🖼️ Food Scanner")
    st.markdown("**Upload a photo of your plate to auto-detect foods and log nutrition!**")
    
    # Initialize detector (cached)
    @st.cache_resource
    def load_detector():
        return VegetableDetector(conf_threshold=0.25)
    
    detector = load_detector()
    
    # File uploader
    uploaded_file = st.file_uploader(
        "📸 Upload food/plate photo", 
        type=['jpg', 'jpeg', 'png', 'webp'],
        help="Clear photos with good lighting work best!"
    )
    
    if uploaded_file is not None:
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            img_path = tmp_file.name
        
        # Show images side-by-side
        col1, col2 = st.columns([1, 1])
        with col1:
            st.image(uploaded_file, caption="📷 Your photo", use_column_width=True)
        
        with col2:
            # AUTO-DETECTION STARTS HERE (no button needed)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            progress_bar.progress(25)
            status_text.text("🔍 Analyzing image...")
            
            # YOUR EXISTING DETECTION CODE
            detections = detector.detect_vegetables(img_path)
            annotated_path = detector.visualize_detections(img_path)
            annotated_img = Image.open(annotated_path)
            
            progress_bar.progress(75)
            status_text.text("🍽️ Matching to UGA menu...")
            
            # Show results
            st.image(annotated_img, caption="🔍 Detected foods", use_column_width=True)
            
            st.markdown("---")
            if detections:
                st.success(f"🥗 Found **{len(detections)}** foods!")
                # ... YOUR EXISTING food columns + Add All button code stays here
                
            progress_bar.progress(100)
            status_text.text("✅ Done!")
        
        # Cleanup
        os.unlink(img_path)
        os.unlink(annotated_path)

        
        # Cleanup (moved outside button)
        if 'img_path' in locals():
            os.unlink(img_path)

        
    # Clear chat button
elif "Agent" in page or page == "🤖 Ask the Agent":
    from agent import render_agent_page
    render_agent_page() 


elif "Progress" in page or page == "📊 Progress":
    st.markdown("## 📊 Progress Tracking")
    if not st.session_state.food_log:
        st.info("Start logging meals to see progress!")
    else:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        week_log = [e for e in st.session_state.food_log 
                   if week_ago <= datetime.strptime(e['date'], '%Y-%m-%d').date() <= today]
        
        if week_log:
            from collections import defaultdict
            daily_totals = defaultdict(lambda: {'calories': 0, 'protein': 0})
            for entry in week_log:
                date = entry['date']
                daily_totals[date]['calories'] += entry['calories'] * entry.get('servings', 1)
                daily_totals[date]['protein'] += entry['protein'] * entry.get('servings', 1)
            
            df = pd.DataFrame([{'Date': k, **v} for k, v in daily_totals.items()])
            st.line_chart(df.set_index('Date')[['calories']])
            st.metric("Days Logged", len(daily_totals))
            st.metric("Avg Calories", f"{sum(d['calories'] for d in daily_totals.values())//max(len(daily_totals),1)}")

elif "Settings" in page or page == "⚙️ Settings":
    st.markdown("## ⚙️ Settings")
    if st.button("🗑️ Clear All Data", type="secondary"):
        for key in ['user_profile', 'goals', 'daily_targets', 'food_log', 'chat_history']:
            st.session_state[key] = None if key not in ['food_log', 'chat_history'] else []
        st.success("Data cleared!")
        st.rerun()

# Footer
st.markdown("---")
st.caption("UGA Nutrition Assistant • Powered by UGA Dining Services Data")
