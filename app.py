"""
UGA Nutrition App - Streamlit PoC
A nutrition guidance application for UGA students using AI-powered recommendations
"""

import streamlit as st
from datetime import datetime, timedelta
import json
import pandas as pd
import os

from vision import VegetableDetector
import tempfile
from PIL import Image

# --- Data persistence helpers ---
# Works locally with file storage; on Streamlit Cloud use st.session_state only
# (Cloud filesystem is ephemeral - data resets on redeploy)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app_data")

def _ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        return True
    except OSError:
        return False

def save_user_data():
    """Save user data to JSON file (local) or just keep in session state (cloud)."""
    if not _ensure_data_dir():
        return  # On cloud / read-only filesystem, skip file save
    data = {
        "user_profile": st.session_state.get("user_profile"),
        "goals": st.session_state.get("goals"),
        "daily_targets": st.session_state.get("daily_targets"),
        "food_log": st.session_state.get("food_log", []),
        "onboarding_complete": st.session_state.get("onboarding_complete", False),
        "activity_day_type": st.session_state.get("activity_day_type", "Training Day"),
    }
    try:
        with open(os.path.join(DATA_DIR, "user_data.json"), "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # Gracefully handle read-only filesystem

def load_user_data():
    """Load persisted user data from JSON file if available."""
    path = os.path.join(DATA_DIR, "user_data.json")
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    return None

# --- CSV loading ---
@st.cache_data
def load_menu_cached():
    return load_menu_from_csv()

def parse_nutrition_value(value):
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    value_str = str(value).strip()
    for suffix in ['kcal', 'cal', 'mg', 'g']:
        if value_str.lower().endswith(suffix):
            value_str = value_str[:-len(suffix)].strip()
            break
    try:
        return float(value_str)
    except ValueError:
        return 0.0

def load_menu_from_csv():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "uga-nutrition-export.csv")
    if not os.path.exists(file_path):
        st.warning("Menu CSV not found.")
        return []

    df = pd.read_csv(file_path, encoding="latin1")
    columns_to_use = [
        "Location_Name", "Menu_Category_Name", "Recipe_Print_As_Name",
        "ServingSize", "CaloriesVal", "TotalFatVal", "TotalCarbVal",
        "ProteinVal", "DietaryFiberVal", "Recipe_Web_Codes",
    ]
    available = [c for c in columns_to_use if c in df.columns]
    df = df[available]
    df = df.drop_duplicates(subset=["Recipe_Print_As_Name", "Location_Name", "Menu_Category_Name"])

    menu = []
    for _, row in df.iterrows():
        name = row.get("Recipe_Print_As_Name", "")
        if pd.isna(name) or not str(name).strip():
            continue
        food_group = _classify_food_group(
            str(row.get("Menu_Category_Name", "")), str(name)
        )
        menu.append({
            'name': str(name).strip(),
            'hall': str(row.get('Location_Name', '')).strip(),
            'meal': str(row.get('Menu_Category_Name', '')).strip(),
            'calories': parse_nutrition_value(row.get('CaloriesVal', 0)),
            'protein': parse_nutrition_value(row.get('ProteinVal', 0)),
            'carbs': parse_nutrition_value(row.get('TotalCarbVal', 0)),
            'fat': parse_nutrition_value(row.get('TotalFatVal', 0)),
            'fiber': parse_nutrition_value(row.get('DietaryFiberVal', 0)),
            'serving_size': str(row['ServingSize']) if 'ServingSize' in row and pd.notna(row.get('ServingSize')) else '1 serving',
            'food_group': food_group,
            'tags': []
        })
    return menu

# --- Food group classification ---
FOOD_GROUP_KEYWORDS = {
    "Protein": ["chicken", "beef", "pork", "turkey", "fish", "salmon", "tuna", "shrimp",
                "egg", "tofu", "sausage", "bacon", "steak", "burger", "meatball", "lamb",
                "wings", "tenderloin", "brisket", "ham", "falafel", "crab", "lobster"],
    "Grains": ["bread", "rice", "pasta", "noodle", "tortilla", "wrap", "biscuit", "roll",
               "cereal", "oatmeal", "grits", "bagel", "muffin", "pancake", "waffle",
               "crouton", "couscous", "quinoa", "pita", "croissant"],
    "Vegetables": ["broccoli", "carrot", "spinach", "kale", "lettuce", "tomato", "pepper",
                   "onion", "cucumber", "corn", "bean", "pea", "squash", "zucchini",
                   "celery", "mushroom", "potato", "sweet potato", "cabbage", "asparagus",
                   "cauliflower", "salad", "veggie", "vegetable", "greens", "collard"],
    "Fruits": ["apple", "banana", "orange", "berry", "strawberry", "blueberry", "grape",
               "melon", "watermelon", "pineapple", "mango", "peach", "pear", "fruit"],
    "Dairy": ["cheese", "milk", "yogurt", "cream", "butter", "ice cream", "cottage",
              "mozzarella", "cheddar", "parmesan", "provolone"],
    "Fats & Oils": ["oil", "dressing", "mayo", "mayonnaise", "ranch", "vinaigrette",
                    "guacamole", "avocado", "nuts", "almond", "peanut", "walnut"],
    "Sweets & Desserts": ["cake", "cookie", "brownie", "pie", "donut", "pastry", "candy",
                          "chocolate", "pudding", "dessert", "cobbler", "sweet"],
    "Beverages": ["juice", "coffee", "tea", "soda", "lemonade", "smoothie", "water",
                  "drink", "beverage", "shake"],
}

def _classify_food_group(category: str, name: str) -> str:
    text = f"{name} {category}".lower()
    best_group = "Other"
    best_score = 0
    for group, keywords in FOOD_GROUP_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_group = group
    return best_group

# --- YOLO detector (cached) ---
@st.cache_resource
def load_yolo_detector():
    return VegetableDetector(conf_threshold=0.25)

# --- Nutrition estimation for detected foods ---
FOOD_NUTRITION_DB = {
    "broccoli":  {"calories": 55, "protein": 3.7, "carbs": 11.2, "fat": 0.6, "fiber": 5.1, "food_group": "Vegetables"},
    "carrot":    {"calories": 41, "protein": 0.9, "carbs": 9.6,  "fat": 0.2, "fiber": 2.8, "food_group": "Vegetables"},
    "apple":     {"calories": 95, "protein": 0.5, "carbs": 25.1, "fat": 0.3, "fiber": 4.4, "food_group": "Fruits"},
    "orange":    {"calories": 62, "protein": 1.2, "carbs": 15.4, "fat": 0.2, "fiber": 3.1, "food_group": "Fruits"},
    "banana":    {"calories": 105,"protein": 1.3, "carbs": 27.0, "fat": 0.4, "fiber": 3.1, "food_group": "Fruits"},
    "tomato":    {"calories": 22, "protein": 1.1, "carbs": 4.8,  "fat": 0.2, "fiber": 1.5, "food_group": "Vegetables"},
}

PORTION_MULTIPLIERS = {
    "Small (half cup)": 0.5,
    "Medium (1 cup)": 1.0,
    "Large (1.5 cups)": 1.5,
    "Extra Large (2 cups)": 2.0,
    "1 piece / whole item": 1.0,
}


# ================================================
# Page configuration
# ================================================
st.set_page_config(
    page_title="UGA Nutrition Assistant",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean neutral CSS - no red/dark colors
st.markdown("""
<style>
    .stApp { background-color: #fafbfc; }

    /* Header banner - neutral warm tones */
    .app-header {
        background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .app-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .app-header p { margin: 0.25rem 0 0 0; opacity: 0.85; font-size: 0.95rem; }

    /* Metric cards - neutral borders */
    .target-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .target-card .label { font-size: 0.8rem; color: #718096; text-transform: uppercase; letter-spacing: 0.5px; }
    .target-card .value { font-size: 1.3rem; font-weight: 700; color: #2d3748; margin-top: 0.25rem; }

    /* Quick action buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }

    /* Food item cards */
    .food-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s;
    }
    .food-card:hover {
        border-color: #a0aec0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .food-card .food-name { font-weight: 600; font-size: 1rem; color: #2d3748; }
    .food-card .food-meta { color: #718096; font-size: 0.85rem; margin-top: 0.2rem; }
    .food-card .food-macros { font-size: 0.85rem; margin-top: 0.5rem; color: #4a5568; }
    .food-card .food-macros strong { color: #2d3748; }
    .food-card .food-badge {
        display: inline-block;
        background: #edf2f7;
        color: #4a5568;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        margin-left: 6px;
        vertical-align: middle;
    }

    /* Override Streamlit metric delta colors to neutral */
    [data-testid="stMetricDelta"] { color: #718096 !important; }
    [data-testid="stMetricDelta"] svg { display: none !important; }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f7fafc;
    }

    /* Progress bars - neutral color */
    .stProgress > div > div { background-color: #a0aec0 !important; }

    /* Clean dividers */
    hr { border-color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)


# ================================================
# Initialize session state
# ================================================
def init_session_state():
    defaults = {
        'user_profile': None, 'goals': None, 'daily_targets': None,
        'food_log': [], 'chat_history': [],
        'onboarding_complete': False, 'activity_day_type': 'Training Day',
    }
    saved = load_user_data()
    for key, value in defaults.items():
        if key not in st.session_state:
            if saved and key in saved and saved[key] is not None:
                st.session_state[key] = saved[key]
            else:
                st.session_state[key] = value

init_session_state()


# ================================================
# Target range calculation
# ================================================
def get_target_range(base_targets: dict, day_type: str) -> dict:
    if day_type == "Rest Day":
        low_mult, high_mult = 0.85, 0.95
    elif day_type == "Active Rest Day":
        low_mult, high_mult = 0.95, 1.05
    else:
        low_mult, high_mult = 1.0, 1.15
    result = {}
    for key in ['calories', 'protein', 'carbs', 'fat']:
        base = base_targets.get(key, 0)
        result[key] = {"low": int(base * low_mult), "high": int(base * high_mult)}
    result['fiber'] = {"low": 25, "high": 35}
    return result


# ================================================
# Navigation
# ================================================
PAGES = [
    "🏠 Home & Goals", "🍽️ Dining Finder", "📝 Food Log",
    "🖼️ Food Scanner", "🤖 Ask the Agent", "📊 Progress", "⚙️ Settings"
]

def navigate_to(page_name: str):
    """Queue a navigation for the next rerun. Must be used in on_click callbacks."""
    st.session_state._pending_nav = page_name


# Apply any pending navigation BEFORE widgets render
if "_pending_nav" in st.session_state and st.session_state._pending_nav:
    st.session_state.nav_radio = st.session_state._pending_nav
    st.session_state._pending_nav = None

# ================================================
# Sidebar
# ================================================
with st.sidebar:
    # UGA logo - use working URL with text fallback
    try:
        st.image("https://brand.uga.edu/wp-content/uploads/GEORGIA-FS-FC.png", width=200)
    except Exception:
        st.markdown("**University of Georgia**")
    st.markdown("---")

    selected_page = st.radio("Navigation", PAGES, key="nav_radio")

    st.markdown("---")

    if st.session_state.daily_targets:
        st.markdown("**Today's Progress**")
        targets = st.session_state.daily_targets
        today_str = str(datetime.now().date())
        today_log = [e for e in st.session_state.food_log if e.get('date') == today_str]

        cal_consumed = sum(e.get('calories', 0) * e.get('servings', 1) for e in today_log)
        protein_consumed = sum(e.get('protein', 0) * e.get('servings', 1) for e in today_log)

        day_type = st.session_state.get("activity_day_type", "Training Day")
        t_range = get_target_range(targets, day_type)

        cal_mid = (t_range['calories']['low'] + t_range['calories']['high']) / 2
        prot_mid = (t_range['protein']['low'] + t_range['protein']['high']) / 2

        st.progress(min(cal_consumed / max(cal_mid, 1), 1.0))
        st.caption(f"Calories: {int(cal_consumed)} / {t_range['calories']['low']}-{t_range['calories']['high']}")
        st.progress(min(protein_consumed / max(prot_mid, 1), 1.0))
        st.caption(f"Protein: {int(protein_consumed)}g / {t_range['protein']['low']}-{t_range['protein']['high']}g")

    page = selected_page


# ================================================
# HOME PAGE
# ================================================
if page == "🏠 Home & Goals":
    st.markdown("""
    <div class="app-header">
        <h1>🐾 UGA Nutrition Assistant</h1>
        <p>Your personalized nutrition guide powered by UGA Dining Services</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.onboarding_complete:
        st.markdown("### Set Up Your Nutrition Goals")
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
                save_user_data()
                st.rerun()

    else:
        # --- Activity Day Type ---
        day_type = st.radio(
            "What kind of day is today?",
            ["Rest Day", "Active Rest Day", "Training Day"],
            index=["Rest Day", "Active Rest Day", "Training Day"].index(
                st.session_state.get("activity_day_type", "Training Day")
            ),
            horizontal=True,
            key="day_type_selector"
        )
        if day_type != st.session_state.get("activity_day_type"):
            st.session_state.activity_day_type = day_type
            save_user_data()

        targets = st.session_state.daily_targets
        t_range = get_target_range(targets, day_type)

        # --- Target range cards using HTML for clean display ---
        st.markdown(f"#### Daily Target Ranges &nbsp; <span style='color:#718096;font-size:0.85rem;'>({day_type})</span>", unsafe_allow_html=True)

        macro_data = [
            ("Calories", f"{t_range['calories']['low']} - {t_range['calories']['high']}", "kcal"),
            ("Protein", f"{t_range['protein']['low']} - {t_range['protein']['high']}", "g"),
            ("Carbs", f"{t_range['carbs']['low']} - {t_range['carbs']['high']}", "g"),
            ("Fat", f"{t_range['fat']['low']} - {t_range['fat']['high']}", "g"),
            ("Fiber", f"{t_range['fiber']['low']} - {t_range['fiber']['high']}", "g"),
        ]

        cards_html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1.5rem;">'
        for label, val, unit in macro_data:
            cards_html += f'''
            <div class="target-card" style="flex:1;min-width:140px;">
                <div class="label">{label}</div>
                <div class="value">{val}<span style="font-size:0.8rem;color:#a0aec0;"> {unit}</span></div>
            </div>'''
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

        # --- Quick Actions - full width, large buttons ---
        st.markdown("#### Quick Actions")
        qa1, qa2, qa3, qa4 = st.columns(4)
        with qa1:
            st.button("🍽️ Find Meals", use_container_width=True, key="qa_dining",
                       on_click=navigate_to, args=("🍽️ Dining Finder",))
        with qa2:
            st.button("📝 Log a Meal", use_container_width=True, key="qa_log",
                       on_click=navigate_to, args=("📝 Food Log",))
        with qa3:
            st.button("🤖 Ask Agent", use_container_width=True, key="qa_agent",
                       on_click=navigate_to, args=("🤖 Ask the Agent",))
        with qa4:
            st.button("🖼️ Scan Food", use_container_width=True, key="qa_scanner",
                       on_click=navigate_to, args=("🖼️ Food Scanner",))

        # --- Today's intake summary (if any logs exist) ---
        today_str = str(datetime.now().date())
        today_log = [e for e in st.session_state.food_log if e.get('date') == today_str]
        if today_log:
            st.markdown("---")
            st.markdown("#### Today's Intake")
            tc = sum(float(e['calories']) * e.get('servings', 1) for e in today_log)
            tp = sum(float(e['protein']) * e.get('servings', 1) for e in today_log)
            tca = sum(float(e['carbs']) * e.get('servings', 1) for e in today_log)
            tf = sum(float(e['fat']) * e.get('servings', 1) for e in today_log)
            tfi = sum(float(e.get('fiber', 0)) * e.get('servings', 1) for e in today_log)

            intake_html = '<div style="display:flex;gap:12px;flex-wrap:wrap;">'
            for label, eaten, rng in [
                ("Calories", int(tc), t_range['calories']),
                ("Protein", int(tp), t_range['protein']),
                ("Carbs", int(tca), t_range['carbs']),
                ("Fat", int(tf), t_range['fat']),
                ("Fiber", int(tfi), t_range['fiber']),
            ]:
                unit = "kcal" if label == "Calories" else "g"
                intake_html += f'''
                <div class="target-card" style="flex:1;min-width:130px;">
                    <div class="label">{label}</div>
                    <div class="value">{eaten}<span style="font-size:0.75rem;color:#a0aec0;"> {unit}</span></div>
                    <div style="font-size:0.75rem;color:#a0aec0;margin-top:2px;">of {rng["low"]}-{rng["high"]}</div>
                </div>'''
            intake_html += '</div>'
            st.markdown(intake_html, unsafe_allow_html=True)

        # --- Edit Profile ---
        st.markdown("---")
        with st.expander("Edit Profile / Reset Goals"):
            if st.button("Reset Goals & Profile"):
                st.session_state.onboarding_complete = False
                st.session_state.user_profile = None
                st.session_state.goals = None
                st.session_state.daily_targets = None
                save_user_data()
                st.rerun()


# ================================================
# DINING FINDER
# ================================================
elif page == "🍽️ Dining Finder":
    st.markdown("### 🍽️ UGA Dining Finder")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_hall = st.selectbox("Dining Hall", ["All", "Bolton", "Snelling", "Village Summit", "Niche", "O-House"])
    with col2:
        selected_date = st.date_input("Date", datetime.now())
    with col3:
        selected_meal = st.selectbox("Meal Period", ["All", "Breakfast", "Lunch", "Dinner", "Late Night",
                                                      "BREAKFAST CLASSICS", "LUNCH", "DINNER"])
    with col4:
        search_query = st.text_input("Search items", placeholder="e.g., chicken, salmon...")

    food_group_filter = st.multiselect(
        "Filter by Food Group",
        ["Protein", "Grains", "Vegetables", "Fruits", "Dairy", "Fats & Oils", "Sweets & Desserts", "Beverages", "Other"],
        default=[]
    )

    st.markdown("---")

    sample_menu = load_menu_cached()
    filtered_menu = sample_menu
    if selected_hall != "All":
        filtered_menu = [item for item in filtered_menu if item['hall'] == selected_hall]
    if selected_meal != "All":
        filtered_menu = [item for item in filtered_menu if selected_meal.lower() in item['meal'].lower()]
    if search_query:
        filtered_menu = [item for item in filtered_menu if search_query.lower() in item['name'].lower()]
    if food_group_filter:
        filtered_menu = [item for item in filtered_menu if item.get('food_group', 'Other') in food_group_filter]

    display_limit = 100
    count_label = f"Found **{len(filtered_menu)}** items"
    if len(filtered_menu) > display_limit:
        count_label += f" (showing first {display_limit})"
    st.markdown(count_label)

    for i, item in enumerate(filtered_menu[:display_limit]):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"""
            <div class="food-card">
                <span class="food-name">{item['name']}</span>
                <span class="food-badge">{item.get('food_group','')}</span>
                <div class="food-meta">📍 {item['hall']} &middot; {item['meal']} &middot; {item.get('serving_size','1 serving')}</div>
                <div class="food-macros">
                    <strong>{float(item['calories']):.0f}</strong> cal &middot;
                    <strong>{float(item['protein']):.1f}g</strong> protein &middot;
                    <strong>{float(item['carbs']):.1f}g</strong> carbs &middot;
                    <strong>{float(item['fat']):.1f}g</strong> fat &middot;
                    <strong>{float(item.get('fiber',0)):.1f}g</strong> fiber
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("➕ Add", key=f"dining_add_{i}"):
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
                    'fiber': float(item.get('fiber', 0)),
                    'food_group': item.get('food_group', 'Other'),
                    'serving_size': item.get('serving_size'),
                    'servings': 1,
                    'tags': item.get('tags', [])
                }
                st.session_state.food_log.append(log_entry)
                save_user_data()
                st.success(f"Added **{item['name']}**!")

    if not filtered_menu:
        st.info("No items match your filters. Try a different hall or meal period.")


# ================================================
# FOOD LOG
# ================================================
elif page == "📝 Food Log":
    st.markdown("### 📝 Food Log")
    selected_date = st.date_input("View date", datetime.now())
    day_log = [e for e in st.session_state.food_log if e.get('date') == str(selected_date)]

    if day_log:
        total_cal = sum(float(e['calories']) * e.get('servings', 1) for e in day_log)
        total_protein = sum(float(e['protein']) * e.get('servings', 1) for e in day_log)
        total_carbs = sum(float(e['carbs']) * e.get('servings', 1) for e in day_log)
        total_fat = sum(float(e['fat']) * e.get('servings', 1) for e in day_log)
        total_fiber = sum(float(e.get('fiber', 0)) * e.get('servings', 1) for e in day_log)

        targets = st.session_state.daily_targets or {'calories': 2000, 'protein': 150, 'carbs': 250, 'fat': 65}
        day_type = st.session_state.get("activity_day_type", "Training Day")
        t_range = get_target_range(targets, day_type)

        st.caption(f"Day type: **{day_type}**")

        # Summary cards
        summary_html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1rem;">'
        for label, total, rng in [
            ("Calories", total_cal, t_range['calories']),
            ("Protein", total_protein, t_range['protein']),
            ("Carbs", total_carbs, t_range['carbs']),
            ("Fat", total_fat, t_range['fat']),
            ("Fiber", total_fiber, t_range['fiber']),
        ]:
            unit = "kcal" if label == "Calories" else "g"
            summary_html += f'''
            <div class="target-card" style="flex:1;min-width:120px;">
                <div class="label">{label}</div>
                <div class="value">{int(total)}<span style="font-size:0.75rem;color:#a0aec0;"> {unit}</span></div>
                <div style="font-size:0.7rem;color:#a0aec0;">target: {rng["low"]}-{rng["high"]}</div>
            </div>'''
        summary_html += '</div>'
        st.markdown(summary_html, unsafe_allow_html=True)

        net_carbs = total_carbs - total_fiber
        st.caption(f"Net Carbs (Carbs - Fiber): **{int(net_carbs)}g** | Net Calories (deducting fiber): **~{int(total_cal - total_fiber * 2)}** kcal")

        # Food Group Breakdown
        from collections import Counter
        group_counts = Counter(e.get('food_group', 'Other') for e in day_log)
        if group_counts:
            st.markdown("**Food Groups**")
            group_html = '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem;">'
            for group, count in group_counts.most_common():
                group_html += f'<span style="background:#edf2f7;color:#4a5568;padding:4px 12px;border-radius:16px;font-size:0.8rem;">{group}: {count}</span>'
            group_html += '</div>'
            st.markdown(group_html, unsafe_allow_html=True)

        # Logged Items
        st.markdown("**Logged Items**")
        for i, entry in enumerate(day_log):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                fg_label = entry.get('food_group', '')
                st.markdown(f"**{entry['name']}** {('(' + fg_label + ')') if fg_label else ''}")
                st.caption(f"📍 {entry.get('hall', 'N/A')} · {entry.get('meal', 'N/A')} · {entry['time']}")
            with col2:
                st.caption(
                    f"{entry['calories']:.0f} cal · {entry['protein']:.1f}g P · "
                    f"{entry['carbs']:.1f}g C · {entry['fat']:.1f}g F · {entry.get('fiber',0):.1f}g fiber"
                )
                full_idx = st.session_state.food_log.index(entry)
                servings = st.number_input("Servings", min_value=0.5, max_value=5.0,
                                           value=float(entry.get('servings', 1)), step=0.5, key=f"serv_{i}")
                if servings != entry.get('servings', 1):
                    st.session_state.food_log[full_idx]['servings'] = servings
                    save_user_data()
            with col3:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.food_log.remove(entry)
                    save_user_data()
                    st.rerun()
            st.markdown("---")

        # Export
        exp1, exp2 = st.columns(2)
        with exp1:
            if st.button("📥 Export CSV"):
                import csv, io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=day_log[0].keys())
                writer.writeheader()
                writer.writerows(day_log)
                st.download_button("Download CSV", output.getvalue(), "food_log.csv", "text/csv")
        with exp2:
            if st.button("📥 Export JSON"):
                st.download_button("Download JSON", json.dumps(day_log, indent=2), "food_log.json")
    else:
        st.info("No items logged for this date.")
        st.button("🍽️ Go to Dining Finder",
                  on_click=navigate_to, args=("🍽️ Dining Finder",))


# ================================================
# FOOD SCANNER
# ================================================
elif page == "🖼️ Food Scanner":
    st.markdown("### 🖼️ Food Scanner")
    st.markdown("Upload or take a photo of your plate to detect foods, choose portions, and add to your log.")

    detector = load_yolo_detector()

    tab_upload, tab_camera = st.tabs(["📁 Upload Photo", "📸 Take Photo"])
    with tab_upload:
        uploaded_file = st.file_uploader("Upload food/plate photo", type=['jpg', 'jpeg', 'png', 'webp'])
    with tab_camera:
        camera_photo = st.camera_input("Take a photo of your food")

    image_source = uploaded_file or camera_photo

    if image_source is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(image_source.getvalue())
            img_path = tmp_file.name

        col1, col2 = st.columns(2)
        with col1:
            st.image(image_source, caption="Your photo", use_container_width=True)
        with col2:
            with st.spinner("Analyzing image..."):
                detections = detector.detect_vegetables(img_path)
                annotated_path = detector.visualize_detections(img_path)
                annotated_img = Image.open(annotated_path)
            st.image(annotated_img, caption="Detected foods", use_container_width=True)

        try:
            os.unlink(img_path)
            os.unlink(annotated_path)
        except Exception:
            pass

        st.markdown("---")

        if detections:
            st.success(f"Found **{len(detections)}** food items!")

            items_to_add = []
            for idx, det in enumerate(detections):
                food_name = det['class_name']
                confidence = det['confidence']
                nutrition = FOOD_NUTRITION_DB.get(food_name, {
                    "calories": 50, "protein": 2, "carbs": 10, "fat": 1, "fiber": 2, "food_group": "Other"
                })

                st.markdown(f"**{food_name.title()}** ({confidence:.0%} confidence)")
                p1, p2, p3 = st.columns([2, 2, 1])
                with p1:
                    portion = st.selectbox(f"Portion for {food_name}", list(PORTION_MULTIPLIERS.keys()),
                                          index=1, key=f"portion_{idx}")
                with p2:
                    mult = PORTION_MULTIPLIERS[portion]
                    st.caption(
                        f"{nutrition['calories']*mult:.0f} cal · {nutrition['protein']*mult:.1f}g P · "
                        f"{nutrition['carbs']*mult:.1f}g C · {nutrition['fat']*mult:.1f}g F · "
                        f"{nutrition.get('fiber',0)*mult:.1f}g fiber"
                    )
                with p3:
                    if st.checkbox("Add", key=f"scan_add_{idx}", value=True):
                        items_to_add.append({
                            'name': food_name.title(),
                            'calories': nutrition['calories'] * mult,
                            'protein': nutrition['protein'] * mult,
                            'carbs': nutrition['carbs'] * mult,
                            'fat': nutrition['fat'] * mult,
                            'fiber': nutrition.get('fiber', 0) * mult,
                            'food_group': nutrition.get('food_group', 'Other'),
                            'portion': portion,
                        })

            if items_to_add and st.button("📝 Add Selected to Food Log", type="primary"):
                for item in items_to_add:
                    st.session_state.food_log.append({
                        'date': str(datetime.now().date()),
                        'time': datetime.now().strftime("%H:%M"),
                        'name': f"{item['name']} ({item['portion']})",
                        'hall': 'Scanned', 'meal': 'Scanned',
                        'calories': item['calories'], 'protein': item['protein'],
                        'carbs': item['carbs'], 'fat': item['fat'],
                        'fiber': item['fiber'], 'food_group': item['food_group'],
                        'serving_size': item['portion'], 'servings': 1, 'tags': ['scanned']
                    })
                save_user_data()
                st.success(f"Added {len(items_to_add)} item(s) to your food log!")
        else:
            st.warning("No foods detected. Try a clearer photo with better lighting.")


# ================================================
# ASK THE AGENT
# ================================================
elif page == "🤖 Ask the Agent":
    st.markdown("### 🤖 Nutrition Agent")

    from groq_agent import NutritionAgent
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if "nutrition_agent" not in st.session_state:
        # Try multiple sources for the API key
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets.get("GROQ_API_KEY")
            except Exception:
                pass
        st.session_state.nutrition_agent = NutritionAgent(api_key=api_key)

    agent = st.session_state.nutrition_agent

    if not agent.is_available():
        st.warning(
            "AI agent not available. To enable AI responses:\n"
            "- **Local**: Add `GROQ_API_KEY=gsk_...` to your `.env` file\n"
            "- **Streamlit Cloud**: Add it in Settings > Secrets as `GROQ_API_KEY = \"gsk_...\"`\n"
            "- Get a free key at [console.groq.com](https://console.groq.com)\n\n"
            "Using rule-based responses for now."
        )

    if not st.session_state.chat_history:
        st.caption("Try one of these:")
        prompt_cols = st.columns(2)
        prompts = [
            "High protein options at Bolton?",
            "How can I hit my protein target?",
            "Suggest a low calorie dinner",
            "Plan my meals for today"
        ]
        for i, prompt in enumerate(prompts):
            with prompt_cols[i % 2]:
                if st.button(prompt, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": prompt})
                    st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Ask about nutrition..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        today_str = str(datetime.now().date())
        today_log = [e for e in st.session_state.food_log if e.get('date') == today_str]
        today_totals = {
            'calories': sum(e.get('calories', 0) * e.get('servings', 1) for e in today_log),
            'protein': sum(e.get('protein', 0) * e.get('servings', 1) for e in today_log),
            'carbs': sum(e.get('carbs', 0) * e.get('servings', 1) for e in today_log),
            'fat': sum(e.get('fat', 0) * e.get('servings', 1) for e in today_log),
            'fiber': sum(e.get('fiber', 0) * e.get('servings', 1) for e in today_log),
        }

        context = {
            'user_profile': st.session_state.user_profile,
            'goals': st.session_state.goals,
            'targets': st.session_state.daily_targets,
            'today_log': today_log,
            'today_totals': today_totals,
        }

        concern_msg = agent.check_for_concerning_content(user_input)
        if concern_msg:
            response_text = concern_msg
        else:
            result = agent.get_response(
                user_message=user_input, context=context,
                chat_history=st.session_state.chat_history[:-1]
            )
            response_text = result['message']

        with st.chat_message("assistant"):
            st.markdown(response_text)

        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        st.rerun()

    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()


# ================================================
# PROGRESS
# ================================================
elif page == "📊 Progress":
    st.markdown("### 📊 Progress Tracking")
    if not st.session_state.food_log:
        st.info("Start logging meals to see progress!")
    else:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        week_log = [e for e in st.session_state.food_log
                    if week_ago <= datetime.strptime(e['date'], '%Y-%m-%d').date() <= today]

        if week_log:
            from collections import defaultdict
            daily_totals = defaultdict(lambda: {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'fiber': 0})
            for entry in week_log:
                d = entry['date']
                s = entry.get('servings', 1)
                daily_totals[d]['calories'] += entry['calories'] * s
                daily_totals[d]['protein'] += entry['protein'] * s
                daily_totals[d]['carbs'] += entry['carbs'] * s
                daily_totals[d]['fat'] += entry['fat'] * s
                daily_totals[d]['fiber'] += entry.get('fiber', 0) * s

            df = pd.DataFrame([{'Date': k, **v} for k, v in daily_totals.items()]).sort_values('Date')

            st.markdown("**Calories**")
            st.line_chart(df.set_index('Date')[['calories']])
            st.markdown("**Macros**")
            st.line_chart(df.set_index('Date')[['protein', 'carbs', 'fat', 'fiber']])

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Days Logged", len(daily_totals))
            with m2:
                st.metric("Avg Calories", f"{sum(d['calories'] for d in daily_totals.values()) // max(len(daily_totals), 1)}")
            with m3:
                st.metric("Avg Protein", f"{sum(d['protein'] for d in daily_totals.values()) // max(len(daily_totals), 1)}g")

            st.markdown("**Food Group Distribution (This Week)**")
            from collections import Counter
            groups = Counter(e.get('food_group', 'Other') for e in week_log)
            if groups:
                gdf = pd.DataFrame(list(groups.items()), columns=['Food Group', 'Count'])
                st.bar_chart(gdf.set_index('Food Group'))
        else:
            st.info("No data for the past 7 days.")


# ================================================
# SETTINGS
# ================================================
elif page == "⚙️ Settings":
    st.markdown("### ⚙️ Settings")

    if st.button("🗑️ Clear All Data", type="secondary"):
        for key in ['user_profile', 'goals', 'daily_targets', 'food_log', 'chat_history']:
            st.session_state[key] = None if key not in ['food_log', 'chat_history'] else []
        st.session_state.onboarding_complete = False
        save_user_data()
        st.success("Data cleared!")
        st.rerun()

    st.markdown("**Data Persistence**")
    st.caption("Your data is saved to disk locally and persists across reloads. On Streamlit Cloud, data persists only within your browser session (resets on redeploy).")

    data_path = os.path.join(DATA_DIR, "user_data.json")
    if os.path.exists(data_path):
        st.caption(f"Stored at: `{data_path}`")
        with st.expander("View saved data"):
            with open(data_path, "r") as f:
                st.json(json.load(f))


# Footer
st.markdown("---")
st.caption("UGA Nutrition Assistant · Powered by UGA Dining Services Data")
