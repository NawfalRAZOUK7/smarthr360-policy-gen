
import os
import json
try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq optional, service degrades to static logic
    Groq = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - env comes from settings in the platform
    pass

class GroqService:
    _client = None

    @classmethod
    def get_client(cls):
        if not cls._client:
            # Try lowercase first as seen in user's .env
            api_key = os.environ.get("groq_api_key") or os.environ.get("GROQ_API_KEY")
            
            if not api_key:
                print("Warning: GROQ_API_KEY not found in environment.")
                return None
                
            if Groq is None:
                print("Warning: groq package not installed; using static fallback.")
                return None
            cls._client = Groq(api_key=api_key)
        return cls._client

    @staticmethod
    def predict_impact(current_stats, policy_type, magnitude):
        client = GroqService.get_client()
        if not client:
            return None
            
        prompt = f"""
        Act as an HR Analytics Expert.
        
        Current Company State:
        - Turnover Rate: {current_stats.get('turnover', 0)}%
        - Average Performance Score: {current_stats.get('performance', 0)}/5.0
        
        Proposed HR Policy:
        - Type: {policy_type}
        - Investment Magnitude: {magnitude} (Scale 0-10)
        
        Task: Predict the quantitative impact of this policy.
        
        Return a JSON object with the following keys:
        - "turnover_change": (float) Predicted percentage change in turnover (e.g., -2.5 for decrease).
        - "performance_change": (float) Predicted absolute change in performance score (e.g., +0.3).
        - "cost_estimate": (float) Estimated implementation cost in MAD (Moroccan Dirham).
        
        JSON ONLY. No other text.
        """
        
        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7, # Increased for variety in text
                response_format={"type": "json_object"},
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"Groq Prediction Error: {e}")
            return None

    @staticmethod
    def get_recommendations(current_stats, budget_limit=100000):
        client = GroqService.get_client()
        if not client:
            return []
            
        # Add random focus to ensure variety in recommendations
        # Note: import random must be at top of file, using inline import for safety here or trusting previous context
        import random 
        
        focus_areas = [
            "innovation and creativity", 
            "employee well-being and work-life balance", 
            "professional development and growth", 
            "team cohesion and culture",
            "operational efficiency and autonomy"
        ]
        chosen_focus = random.choice(focus_areas)
            
        prompt = f"""
        Analyze the following HR metrics and suggest 3-4 strategic policies to improve the situation.
        
        Metrics:
        - Turnover Rate: {current_stats.get('turnover', 0)}%
        - Average Performance: {current_stats.get('performance', 0)}/5.0
        
        Constraint: Focus specifically on policies related to '{chosen_focus}' (but ensure they address the metrics).
        Constraint: TOTAL implementation cost for each individual policy MUST be under {budget_limit} MAD.
        
        Task: Suggest policies and estimate the budget required for each.
        
        Return a JSON list of objects, where each object has:
        - "policy": (string) Name of the policy.
        - "reason": (string) Brief reason for the recommendation.
        - "priority": (string) "High", "Medium", or "Low".
        - "budget_estimate": (string) Estimated budget to spend in MAD (Moroccan Dirham).
        - "estimated_cost_mad": (number) Numeric cost estimate in MAD for sorting purposes.
        
        CRITICAL INSTRUCTION - BUDGET AND COST:
        - The company wants to MINIMIZE COSTS.
        - "Horaires Flexibles" (Flexible Hours) MUST have 0 MAD cost.
        - "Mentorat" (Mentorship) MUST have 0 MAD cost (internal resources).
        - Prioritize recommendations that are COST-EFFECTIVE.
        
        RETURN THE LIST ALREADY SORTED BY estimated_cost_mad (LOWEST TO HIGHEST).
        
        Example (already sorted by cost in MAD):
        [
            {{"policy": "Engagement Culture", "reason": "Boost morale.", "priority": "High", "budget_estimate": "0 MAD", "estimated_cost_mad": 0}},
            {{"policy": "Télétravail Hybride", "reason": "Reduce burnout.", "priority": "High", "budget_estimate": "2,000 MAD/setup", "estimated_cost_mad": 2000}}
        ]
        
        JSON ONLY. No other text.
        """
        
        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,  # Increased to 0.7 to avoid static/repetitive recommendations
                response_format={"type": "json_object"},
            )
            content = json.loads(chat_completion.choices[0].message.content)
            
            # Handle potential wrapping
            recommendations = []
            if "recommendations" in content:
                recommendations = content["recommendations"]
            elif isinstance(content, list):
                recommendations = content
            else:
                # Try to find a list in values
                for key, value in content.items():
                    if isinstance(value, list):
                        recommendations = value
                        break
            
            # Ensure all recommendations have estimated_cost_mad
            for rec in recommendations:
                if "estimated_cost_mad" not in rec:
                    # Try to extract numeric value from budget_estimate
                    budget_str = rec.get("budget_estimate", "")
                    try:
                        # Extract first number from string (e.g., "5,000 MAD" -> 5000)
                        import re
                        numbers = re.findall(r'\d+(?:,\d+)*', budget_str.replace(',', ''))
                        rec["estimated_cost_mad"] = int(numbers[0]) if numbers else 0
                    except:
                        rec["estimated_cost_mad"] = 0
            
            # Sort by cost (lowest to highest) to ensure budget priority
            recommendations.sort(key=lambda x: x.get("estimated_cost_mad", 0))
            
            return recommendations
        except Exception as e:
             print(f"Groq Recommendation Error: {e}")
             return []
