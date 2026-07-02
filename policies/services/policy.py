from ..models import Employe, Department, JobTitle, PerformanceReview, RetentionOffer
from django.db.models import Avg
from django.utils import timezone
import random
from datetime import timedelta
from .groq_service import GroqService

class HRAnalyticsService:
    @staticmethod
    def get_turnover_rate():
        total_employees = Employe.objects.count()
        if total_employees == 0:
            return 0.0
        terminated_employees = Employe.objects.filter(status='terminated').count()
        return (terminated_employees / total_employees) * 100

    @staticmethod
    def get_average_performance():
        avg_perf = PerformanceReview.objects.aggregate(Avg('overall_score'))['overall_score__avg']
        return avg_perf if avg_perf else 0.0

    @staticmethod
    def get_retention_stats():
        total_offers = RetentionOffer.objects.count()
        if total_offers == 0:
            return {"total": 0, "success_rate": 0.0}
        accepted_offers = RetentionOffer.objects.filter(status='accepted').count()
        return {
            "total": total_offers,
            "success_rate": (accepted_offers / total_offers) * 100
        }

class PolicySimulatorService:
    @staticmethod
    def simulate_policy_impact(policy_type, magnitude):
        # 1. Try Groq Prediction
        current_stats = {
            "turnover": HRAnalyticsService.get_turnover_rate(),
            "performance": HRAnalyticsService.get_average_performance()
        }
        
        prediction = GroqService.predict_impact(current_stats, policy_type, magnitude)
        if prediction:
            # FORCE ZERO COST for specific policies
            # User requirement: "Horaires Flexibles" and "Mentorat" should cost 0
            zero_cost_policies = ['flexible_hours', 'mentorship']
            if policy_type in zero_cost_policies:
                prediction['cost_estimate'] = 0.0
            elif policy_type == 'remote_work' and prediction.get('cost_estimate', 0) == 0:
                # If AI returned 0 for remote work but we know it costs, fallback to static or keep AI?
                # Let's trust AI but ensure minimum reasonable if desired. 
                # For now, just ensure we don't force it to 0 like before.
                pass
            return prediction

        # 2. Fallback to Static Logic
        # Base impact factors (simplified for demo)
        impact_map = {
            'salary_increase': {'turnover': -0.5, 'performance': 0.1, 'cost': 1000},
            'remote_work': {'turnover': -0.3, 'performance': 0.2, 'cost': 3000}, # Updated to 3000 to match recommendation logic
            'training_budget': {'turnover': -0.2, 'performance': 0.4, 'cost': 500},
            'wellness_program': {'turnover': -0.4, 'performance': 0.3, 'cost': 300},
            'flexible_hours': {'turnover': -0.3, 'performance': 0.2, 'cost': 0},
            'mentorship': {'turnover': -0.2, 'performance': 0.5, 'cost': 0}, # Explicitly 0
        }
        
        factors = impact_map.get(policy_type, {'turnover': 0, 'performance': 0, 'cost': 0})
        
        turnover_change = factors['turnover'] * magnitude
        performance_change = factors['performance'] * (magnitude / 10) # Scale down perf impact
        cost_estimate = factors['cost'] * magnitude * Employe.objects.filter(status='active').count()
        
        # Ensure zero cost for specific policies in fallback logic too
        if policy_type in ['flexible_hours', 'mentorship']:
            cost_estimate = 0.0
        
        return {
            "turnover_change": round(turnover_change, 1),
            "performance_change": round(performance_change, 2),
            "cost_estimate": round(cost_estimate, 2)
        }

    @staticmethod
    def generate_recommendations(budget_limit=100000):
        turnover = HRAnalyticsService.get_turnover_rate()
        performance = HRAnalyticsService.get_average_performance()
        
        # 1. Try Groq AI Recommendations
        ai_recommendations = GroqService.get_recommendations({"turnover": turnover, "performance": performance}, budget_limit)
        if ai_recommendations:
            # Ensure all recommendations have estimated_cost_mad
            for rec in ai_recommendations:
                if "estimated_cost_mad" not in rec:
                    # Fallback cost estimation based on policy name (in MAD)
                    policy_name = rec.get("policy", "").lower()
                    if "mentorat" in policy_name or "mentor" in policy_name:
                        rec["estimated_cost_mad"] = 0
                    elif "télétravail" in policy_name or "remote" in policy_name or "flexible" in policy_name:
                        rec["estimated_cost_mad"] = 3000  # 300 USD * 10
                    elif "formation" in policy_name or "training" in policy_name:
                        rec["estimated_cost_mad"] = 20000  # 2000 USD * 10
                    elif "bien-être" in policy_name or "wellness" in policy_name:
                        rec["estimated_cost_mad"] = 50000  # 5000 USD * 10
                    elif "augmentation" in policy_name or "salaire" in policy_name or "salary" in policy_name:
                        rec["estimated_cost_mad"] = 300000  # 30000 USD * 10
                    else:
                        rec["estimated_cost_mad"] = 10000  # Default (1000 USD * 10)
            
            # CRITICAL: Force sort by cost (lowest to highest)
            ai_recommendations.sort(key=lambda x: x.get("estimated_cost_mad", 0))
            return ai_recommendations
            
        # 2. Fallback to Static Logic if Groq fails
        recommendations = []
        
        # ALWAYS suggest low-cost policies first
        if performance < 3.5:
            recommendations.append({
                "policy": "Programme de Mentorat Interne",
                "reason": "La performance moyenne est en dessous de la cible. Le mentorat améliore les compétences sans coût externe.",
                "priority": "High",
                "budget_estimate": "0 MAD (ressources internes)",
                "estimated_cost_mad": 0
            })
        
        if turnover > 10:
            recommendations.append({
                "policy": "Télétravail 2 jours/semaine",
                "reason": "Le taux de turnover est critique (>10%). Le télétravail réduit les départs et les coûts immobiliers.",
                "priority": "High",
                "budget_estimate": "3,000 MAD setup/employé",
                "estimated_cost_mad": 3000
            })
        
        if performance < 3.5:
            recommendations.append({
                "policy": "Formations en ligne",
                "reason": "Développe les compétences à faible coût avec des plateformes comme Udemy ou Coursera.",
                "priority": "Medium",
                "budget_estimate": "20,000 MAD par trimestre",
                "estimated_cost_mad": 20000
            })
        
        if turnover > 10:
            recommendations.append({
                "policy": "Programme Bien-être",
                "reason": "Améliorer le climat social peut réduire les départs.",
                "priority": "Medium",
                "budget_estimate": "50,000 MAD par an",
                "estimated_cost_mad": 50000
            })
        
        # ONLY suggest expensive policies as LAST RESORT
        if turnover > 15 and performance < 3.0:
            recommendations.append({
                "policy": "Augmentation Générale Salaire",
                "reason": "Situation critique : turnover très élevé ET performance faible. Augmentation nécessaire en dernier recours.",
                "priority": "Low",
                "budget_estimate": "300,000 MAD annuel",
                "estimated_cost_mad": 300000
            })
        
        # If no specific issues, maintain current policies
        if not recommendations:
            recommendations.append({
                "policy": "Maintenir les politiques actuelles",
                "reason": "Les indicateurs sont dans les normes acceptables.",
                "priority": "Low",
                "budget_estimate": "0 MAD",
                "estimated_cost_mad": 0
            })
        
        # Sort by cost (lowest to highest)
        recommendations.sort(key=lambda x: x.get("estimated_cost_mad", 0))
        
        return recommendations

    @staticmethod
    def apply_policy(policy_type, magnitude):
        # 1. Get simulated impact
        impact = PolicySimulatorService.simulate_policy_impact(policy_type, magnitude)
        
        # 2. Apply changes to database to reflect impact
        
        # Reduce Turnover: "Resurrect" some terminated employees (simulate retention)
        # or prevent future turnover (not easily visible immediately).
        # For demo purposes, we will flip some 'terminated' to 'active'.
        if impact['turnover_change'] < 0:
            terminated_employees = list(Employe.objects.filter(status='terminated'))
            # Calculate how many to save. 
            # E.g. -2% turnover change. If we have 100 employees, that's 2 employees.
            num_to_save = max(1, int(abs(impact['turnover_change'])))
            for i in range(min(len(terminated_employees), num_to_save)):
                emp = terminated_employees[i]
                emp.status = 'active'
                emp.save()
                
        # Increase Performance: Boost scores of active employees
        if impact['performance_change'] > 0:
            reviews = PerformanceReview.objects.all()
            for review in reviews:
                # Cast Decimal to float for calculation
                current_score = float(review.overall_score)
                new_score = min(5.0, current_score + impact['performance_change'])
                review.overall_score = new_score
                review.save()
                
        return impact

class DemoDataService:
    @staticmethod
    def reset_and_populate():
        # Clear existing data
        RetentionOffer.objects.all().delete()
        PerformanceReview.objects.all().delete()
        Employe.objects.all().delete()
        JobTitle.objects.all().delete()
        Department.objects.all().delete()
        
        # Create Departments
        dept_it = Department.objects.create(name="IT", code="IT")
        dept_hr = Department.objects.create(name="HR", code="HR")
        
        # Create Job Titles
        title_dev = JobTitle.objects.create(name="Developer", level=2)
        title_mgr = JobTitle.objects.create(name="Manager", level=4)
        
        # Create Employees (Active)
        for i in range(20):
            Employe.objects.create(
                first_name=f"Emp{i}",
                last_name=f"Last{i}",
                email=f"emp{i}@example.com",
                status='active',
                department=dept_it,
                job_title=title_dev
            )
            
        # Create Terminated Employees (High turnover scenario)
        for i in range(5):
            Employe.objects.create(
                first_name=f"Term{i}",
                last_name=f"Last{i}",
                email=f"term{i}@example.com",
                status='terminated',
                department=dept_it,
                job_title=title_dev
            )
            
        # Create Performance Reviews (Low performance scenario)
        employees = Employe.objects.all()
        for emp in employees:
            PerformanceReview.objects.create(
                employee=emp,
                overall_score=random.uniform(2.0, 4.0), # Mix of low/mid scores
                period_start=timezone.now() - timedelta(days=365),
                period_end=timezone.now()
            )
            
        # Create Retention Offers
        for i in range(10):
            RetentionOffer.objects.create(
                employee=employees[i],
                offer_type='bonus',
                status=random.choice(['accepted', 'rejected', 'offered'])
            )
