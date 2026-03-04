"""
Groq Integration Module for UGA Nutrition Agent
This module handles all AI/LLM functionality using Groq's API
"""

import os
from typing import Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Warning: groq package not installed. Run: pip install groq")


class NutritionAgent:
    """
    AI Agent for nutrition guidance using Groq's LLM API.
    Provides goal-based nutrition advice grounded in UGA Dining data.
    """

    SYSTEM_PROMPT = """You are a knowledgeable nutrition assistant for University of Georgia students.
Your role is to help students achieve their nutrition goals using UGA Dining Services options.

## Your Capabilities:
1. Help students define nutrition goals (bulk/cut/maintenance, performance, energy, general health)
2. Propose daily targets (protein, calories, fiber, sodium)
3. Recommend specific meals from UGA Dining halls based on their menus
4. Reflect on logged meals and suggest adjustments
5. Answer general nutrition questions

## Important Guidelines:
- Always ground your meal recommendations in ACTUAL UGA Dining options provided in the context
- Be direct, helpful, and informative. Do NOT use flattery or compliments like "Great question!" or "That's a wonderful goal!"
- Never start responses with praise about the user's question. Just answer it directly.
- Use simple, actionable language
- When recommending meals, include specific items, dining halls, and meal periods
- Include approximate nutrition info when available
- Maintain conversation continuity - if the user says "yes" or follows up on a previous suggestion, continue that thread naturally without restarting
- When a user confirms they want something (e.g., "yes", "sure", "please"), provide the thing you offered, don't ask what they want again

## Safety Boundaries:
- You are NOT a medical professional - refer clinical questions to UGA's campus nutrition counseling
- Do NOT provide eating disorder coaching or extreme restriction advice
- If a user shows signs of disordered eating or risky behavior, respond supportively and recommend professional help
- Keep recommendations within safe, evidence-based ranges

## Response Format:
- Be conversational but informative
- Use bullet points for meal suggestions
- Include specific numbers (calories, protein grams) when available
- End with a helpful follow-up question or actionable next step
- Do NOT compliment the user's questions or be sycophantic
"""

    @staticmethod
    def _normalize_api_key(api_key: Optional[str]) -> str:
        if not api_key:
            return ""
        cleaned = api_key.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    def __init__(self, api_key: Optional[str] = None):
        env_key = os.environ.get("GROQ_API_KEY")
        self.api_key = self._normalize_api_key(api_key or env_key)
        self.client = None
        self.model = "llama-3.3-70b-versatile"

        if GROQ_AVAILABLE and self.api_key:
            self.client = Groq(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def build_context_message(self, context: dict) -> str:
        parts = []

        if context.get('user_profile'):
            profile = context['user_profile']
            parts.append(f"""## User Profile:
- Weight: {profile.get('weight', 'Not set')} lbs
- Activity Level: {profile.get('activity_level', 'Not set')}
- Preferred Dining Halls: {', '.join(profile.get('dining_preference', ['Any']))}
- Dietary Restrictions: {', '.join(profile.get('dietary_restrictions', ['None']))}""")

        if context.get('goals'):
            goals = context['goals']
            targets = context.get('targets', {})
            parts.append(f"""## Current Goals:
- Primary Goal: {goals.get('type', 'Not set')}
- Daily Calorie Target: {targets.get('calories', 'Not set')} kcal
- Daily Protein Target: {targets.get('protein', 'Not set')}g
- Daily Carb Target: {targets.get('carbs', 'Not set')}g
- Daily Fat Target: {targets.get('fat', 'Not set')}g""")

        if context.get('today_log'):
            log_items = context['today_log']
            totals = context.get('today_totals', {})

            log_text = "\n".join([
                f"- {item['name']} ({item['calories']} cal, {item['protein']}g protein, "
                f"{item.get('carbs', 0)}g carbs, {item.get('fat', 0)}g fat, {item.get('fiber', 0)}g fiber) "
                f"at {item.get('hall', 'N/A')}"
                for item in log_items
            ])

            parts.append(f"""## Today's Food Log:
{log_text if log_items else 'No items logged yet'}

## Today's Totals:
- Calories consumed: {totals.get('calories', 0)} kcal
- Protein consumed: {totals.get('protein', 0)}g
- Carbs consumed: {totals.get('carbs', 0)}g
- Fat consumed: {totals.get('fat', 0)}g
- Fiber consumed: {totals.get('fiber', 0)}g""")

        parts.append("""## Today's UGA Dining Options (Sample):
### Bolton Dining Hall:
**Breakfast:**
- Scrambled Eggs: 180 cal, 14g protein, 2g carbs, 12g fat
- Greek Yogurt Parfait: 220 cal, 18g protein, 28g carbs, 4g fat

**Lunch:**
- Grilled Chicken Breast: 280 cal, 45g protein, 0g carbs, 8g fat
- Turkey Wrap: 380 cal, 28g protein, 35g carbs, 14g fat

**Dinner:**
- Grilled Salmon: 350 cal, 40g protein, 2g carbs, 18g fat
- Beef Stir Fry: 420 cal, 32g protein, 28g carbs, 22g fat

### Snelling Dining Hall:
**Breakfast:**
- Oatmeal with Berries: 280 cal, 8g protein, 52g carbs, 5g fat

**Lunch:**
- Brown Rice Bowl: 420 cal, 12g protein, 68g carbs, 8g fat
- Veggie Stir Fry: 320 cal, 15g protein, 42g carbs, 10g fat""")

        return "\n\n".join(parts)

    def get_response(
        self,
        user_message: str,
        context: dict,
        chat_history: list = None
    ) -> dict:
        if not self.is_available():
            return self._get_fallback_response(user_message, context, chat_history)

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ]

            context_message = self.build_context_message(context)
            messages.append({
                "role": "system",
                "content": f"## Current Context:\n{context_message}"
            })

            # Add chat history (last 10 messages to stay within limits)
            if chat_history:
                for msg in chat_history[-10:]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            messages.append({"role": "user", "content": user_message})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                top_p=0.9,
            )

            assistant_message = response.choices[0].message.content

            return {
                "message": assistant_message,
                "citation": "UGA Dining Services Data & Nutrition Guidelines",
                "success": True
            }

        except Exception as e:
            print(f"Groq API error: {e}")
            return self._get_fallback_response(user_message, context, chat_history)

    def _get_fallback_response(self, user_message: str, context: dict, chat_history: list = None) -> dict:
        """Provide a rule-based fallback response when API is unavailable."""
        user_input_lower = user_message.lower()
        targets = context.get('targets', {})
        goal_type = context.get('goals', {}).get('type', 'your goals')
        today_totals = context.get('today_totals', {})

        # Check if this is a follow-up confirmation (yes/sure/please/ok)
        if chat_history and user_input_lower.strip() in ['yes', 'yeah', 'sure', 'please', 'ok', 'okay', 'yep', 'y']:
            last_assistant = None
            for msg in reversed(chat_history):
                if msg['role'] == 'assistant':
                    last_assistant = msg['content']
                    break
            if last_assistant and 'meal plan' in last_assistant.lower():
                return self._get_meal_plan_response(context)
            if last_assistant and 'protein' in last_assistant.lower():
                return self._get_meal_plan_response(context)

        if any(word in user_input_lower for word in ['protein', 'muscle', 'bulk']):
            remaining_protein = targets.get('protein', 150) - today_totals.get('protein', 0)
            return {
                "message": f"""Based on your goal of **{goal_type}**, your daily protein target is **{targets.get('protein', 150)}g**.

You've logged **{today_totals.get('protein', 0)}g so far**, leaving about **{max(0, remaining_protein)}g** remaining.

**High-protein options at UGA Dining:**
- Grilled Chicken Breast (45g protein) - Bolton, Lunch
- Grilled Salmon (40g protein) - Bolton, Dinner
- Greek Yogurt Parfait (18g protein) - Bolton, Breakfast

Would you like me to suggest a meal plan to hit your protein target?""",
                "citation": "UGA Dining Services Menu Data",
                "success": True
            }

        elif any(word in user_input_lower for word in ['breakfast', 'morning']):
            return {
                "message": """Here are breakfast options at UGA Dining:

**High Protein:**
- Scrambled Eggs - 180 cal, 14g protein (Bolton)
- Greek Yogurt Parfait - 220 cal, 18g protein (Bolton)

**High Energy:**
- Oatmeal with Berries - 280 cal, 8g protein, 52g carbs (Snelling)

**Balanced Option:**
- Eggs + Oatmeal combo gives you 22g protein and sustained energy!

What's your priority for breakfast - protein, energy, or a balance of both?""",
                "citation": "UGA Dining Services Menu",
                "success": True
            }

        elif any(word in user_input_lower for word in ['lunch', 'dinner', 'meal', 'plan']):
            return self._get_meal_plan_response(context)

        elif any(word in user_input_lower for word in ['calories', 'cal', 'over', 'under']):
            remaining_cal = targets.get('calories', 2000) - today_totals.get('calories', 0)
            return {
                "message": f"""Here's your calorie status:

**Today's Progress:**
- Consumed: {today_totals.get('calories', 0)} kcal
- Target: {targets.get('calories', 2000)} kcal
- Remaining: {max(0, remaining_cal)} kcal

{'You are on track.' if 0 <= remaining_cal <= 500 else ''}
{'You have plenty of room for a full meal.' if remaining_cal > 500 else ''}
{'You are over your target. Consider a lighter dinner or extra activity.' if remaining_cal < 0 else ''}

**Low-calorie, high-protein options:**
- Grilled Chicken (280 cal) with vegetables
- Scrambled Eggs (180 cal) for a light meal

How can I help you adjust your remaining meals?""",
                "citation": "Calculated from your food log",
                "success": True
            }

        else:
            return {
                "message": f"""Here's what I can help with:

**Your Current Setup:**
- Goal: {goal_type}
- Calorie Target: {targets.get('calories', 'Not set')} kcal/day
- Protein Target: {targets.get('protein', 'Not set')}g/day
- Carb Target: {targets.get('carbs', 'Not set')}g/day
- Fat Target: {targets.get('fat', 'Not set')}g/day

**I can help you with:**
1. **Meal suggestions** from UGA Dining halls
2. **Protein optimization** to hit your targets
3. **Progress analysis** based on your food log
4. **Goal adjustments** as you progress

What would you like to focus on?""",
                "citation": "",
                "success": True
            }

    def _get_meal_plan_response(self, context: dict) -> dict:
        """Generate a meal plan based on user context."""
        targets = context.get('targets', {})
        goal_type = context.get('goals', {}).get('type', 'your goals')
        today_totals = context.get('today_totals', {})

        remaining_cal = targets.get('calories', 2000) - today_totals.get('calories', 0)
        remaining_protein = targets.get('protein', 150) - today_totals.get('protein', 0)

        return {
            "message": f"""Here's a meal plan for your **{goal_type}** goal:

**Remaining targets:** ~{max(0, remaining_cal)} cal, ~{max(0, remaining_protein)}g protein

**Suggested meals:**

**Lunch at Bolton:**
- Grilled Chicken Breast (280 cal, 45g protein)
- Side of Roasted Vegetables (120 cal, 4g protein, 6g fiber)
- *Subtotal: 400 cal, 49g protein*

**Dinner at Bolton:**
- Grilled Salmon (350 cal, 40g protein)
- Baked Sweet Potato (180 cal, 4g protein, 6g fiber)
- Side Caesar Salad (220 cal, 8g protein, 4g fiber)
- *Subtotal: 750 cal, 52g protein*

**Snack:**
- Greek Yogurt Parfait (220 cal, 18g protein)

**Day Total Estimate:** ~1,370 cal, ~119g protein

Would you like me to adjust this plan or suggest alternatives for a specific meal?""",
            "citation": "UGA Dining Services Menu",
            "success": True
        }

    def check_for_concerning_content(self, user_message: str) -> Optional[str]:
        concerning_phrases = [
            'not eating', 'starving', 'purge', 'binge', 'hate my body',
            'too fat', 'disgusting', 'fast for days', 'laxative',
            'make myself throw up', 'eating disorder'
        ]

        message_lower = user_message.lower()

        if any(phrase in message_lower for phrase in concerning_phrases):
            return """I hear that you might be going through a difficult time with food and your body.

Your wellbeing matters more than any nutrition goal.

**UGA has free, confidential support available:**
- UGA Counseling & Psychiatric Services (CAPS): (706) 542-2273
- UGA Health Center Nutrition Services: (706) 542-8690

Would you like me to help you find more resources, or is there something else I can support you with today?"""

        return None


def create_agent(api_key: Optional[str] = None) -> NutritionAgent:
    return NutritionAgent(api_key)
