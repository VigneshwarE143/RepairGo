"""
Seed script to populate MongoDB with test data for RepairGo.
Run with: python seed_data.py
"""
import random
from datetime import datetime, timedelta
from bson import ObjectId
import bcrypt
from database import (
    users_collection,
    technicians_collection,
    services_collection,
    categories_collection,
    payments_collection,
    feedback_collection,
)

# Helper function to hash passwords
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Clear existing data
def clear_data():
    print("Clearing existing data...")
    users_collection.delete_many({})
    technicians_collection.delete_many({})
    services_collection.delete_many({})
    categories_collection.delete_many({})
    payments_collection.delete_many({})
    feedback_collection.delete_many({})
    print("Data cleared ✅")

# Service categories
CATEGORIES = [
    {"name": "Plumbing", "base_price": 50, "travel_rate": 2.5, "urgency_addon_low": 0, "urgency_addon_medium": 15, "urgency_addon_high": 35},
    {"name": "Electrical", "base_price": 60, "travel_rate": 2.0, "urgency_addon_low": 0, "urgency_addon_medium": 20, "urgency_addon_high": 40},
    {"name": "HVAC", "base_price": 75, "travel_rate": 3.0, "urgency_addon_low": 0, "urgency_addon_medium": 25, "urgency_addon_high": 50},
    {"name": "Appliance Repair", "base_price": 55, "travel_rate": 2.0, "urgency_addon_low": 0, "urgency_addon_medium": 15, "urgency_addon_high": 30},
    {"name": "Roofing", "base_price": 100, "travel_rate": 4.0, "urgency_addon_low": 0, "urgency_addon_medium": 30, "urgency_addon_high": 60},
    {"name": "Painting", "base_price": 45, "travel_rate": 1.5, "urgency_addon_low": 0, "urgency_addon_medium": 10, "urgency_addon_high": 25},
    {"name": "Carpentry", "base_price": 65, "travel_rate": 2.5, "urgency_addon_low": 0, "urgency_addon_medium": 20, "urgency_addon_high": 40},
    {"name": "Locksmith", "base_price": 40, "travel_rate": 3.0, "urgency_addon_low": 0, "urgency_addon_medium": 25, "urgency_addon_high": 50},
]

# Customer data
CUSTOMERS = [
    {"name": "John Smith", "email": "john.smith@email.com"},
    {"name": "Sarah Johnson", "email": "sarah.j@email.com"},
    {"name": "Michael Brown", "email": "m.brown@email.com"},
    {"name": "Emily Davis", "email": "emily.d@email.com"},
    {"name": "David Wilson", "email": "d.wilson@email.com"},
    {"name": "Jessica Martinez", "email": "jessica.m@email.com"},
    {"name": "Christopher Lee", "email": "chris.lee@email.com"},
    {"name": "Amanda Taylor", "email": "amanda.t@email.com"},
    {"name": "Daniel Anderson", "email": "daniel.a@email.com"},
    {"name": "Michelle Thomas", "email": "michelle.t@email.com"},
]

# Technician first and last names
TECH_FIRST_NAMES = [
    "James", "Robert", "William", "Richard", "Joseph", "Thomas", "Charles", "Daniel",
    "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason",
    "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen",
    "Larry", "Justin", "Scott", "Brandon", "Benjamin", "Samuel", "Henry", "Patrick"
]
TECH_LAST_NAMES = [
    "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez",
    "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz", "Reyes", "Cruz",
    "Morales", "Ortiz", "Gutierrez", "Chavez", "Ramos", "Vargas", "Castillo", "Jimenez",
    "Moreno", "Romero", "Herrera", "Medina", "Aguilar", "Castro", "Ruiz", "Mendoza",
    "Santos", "Guerrero", "Delgado", "Vega", "Salazar", "Espinoza", "Cabrera", "Campos"
]

# Service descriptions by category
SERVICE_DESCRIPTIONS = {
    "Plumbing": [
        "Leaky faucet in kitchen needs repair",
        "Bathroom sink clogged and draining slowly",
        "Water heater not producing hot water",
        "Toilet running constantly, needs fixing",
        "Pipe burst under sink causing flooding",
        "Garbage disposal making strange noises",
        "Shower head has low water pressure",
        "Need new water filter installation",
    ],
    "Electrical": [
        "Multiple outlets not working in living room",
        "Circuit breaker keeps tripping",
        "Need ceiling fan installed in bedroom",
        "Outdoor lighting installation required",
        "Light fixtures flickering throughout house",
        "Need additional outlets in home office",
        "Smart thermostat installation",
        "Smoke detector replacement and wiring",
    ],
    "HVAC": [
        "AC unit not cooling properly",
        "Furnace making loud banging noises",
        "Need annual HVAC maintenance checkup",
        "Thermostat not responding correctly",
        "Air ducts need cleaning and inspection",
        "Heat pump not switching modes",
        "Refrigerant leak in AC system",
        "Ventilation system needs upgrade",
    ],
    "Appliance Repair": [
        "Washing machine not spinning properly",
        "Refrigerator not cooling, food spoiling",
        "Dishwasher leaking water on floor",
        "Dryer not heating clothes",
        "Oven temperature inconsistent",
        "Microwave sparking when in use",
        "Ice maker stopped working",
        "Stove burner won't ignite",
    ],
    "Roofing": [
        "Roof leaking during heavy rain",
        "Missing shingles after storm",
        "Gutter cleaning and repair needed",
        "Skylight installation request",
        "Roof inspection for insurance claim",
        "Fascia board replacement",
        "Attic ventilation improvement",
        "Emergency tarp for roof damage",
    ],
    "Painting": [
        "Interior painting for living room",
        "Exterior house painting needed",
        "Touch up paint on walls after repair",
        "Cabinet refinishing in kitchen",
        "Fence staining and sealing",
        "Deck restoration and painting",
        "Wallpaper removal and painting",
        "Accent wall painting in bedroom",
    ],
    "Carpentry": [
        "Broken cabinet door needs fixing",
        "Custom shelving installation",
        "Deck repair and board replacement",
        "Door frame damaged, needs repair",
        "Window trim replacement",
        "Closet organization system install",
        "Stair railing repair",
        "Crown molding installation",
    ],
    "Locksmith": [
        "Locked out of house, need entry",
        "Deadbolt replacement on front door",
        "Rekey all locks after moving in",
        "Smart lock installation",
        "Garage door lock repair",
        "Safe unlocking service needed",
        "Mailbox lock replacement",
        "Security upgrade consultation",
    ],
}

# Locations around a city (latitude, longitude pairs)
LOCATIONS = [
    (40.7128, -74.0060),  # NYC area
    (40.7580, -73.9855),
    (40.7484, -73.9857),
    (40.7614, -73.9776),
    (40.7527, -73.9772),
    (40.7282, -74.0776),
    (40.7061, -74.0088),
    (40.7831, -73.9712),
    (40.7489, -73.9680),
    (40.7295, -73.9965),
    (40.7193, -73.9857),
    (40.7424, -73.9884),
    (40.7549, -73.9840),
    (40.7112, -74.0055),
    (40.7308, -73.9973),
]


def seed_categories():
    print("Seeding categories...")
    for cat in CATEGORIES:
        cat["created_at"] = datetime.utcnow()
        categories_collection.insert_one(cat)
    print(f"  Created {len(CATEGORIES)} categories ✅")


def seed_admin():
    print("Seeding admin user...")
    admin = {
        "name": "Admin User",
        "email": "admin@repairgo.com",
        "password": hash_password("admin123"),
        "role": "admin",
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    users_collection.insert_one(admin)
    print("  Created admin user ✅")


def seed_customers():
    print("Seeding customers...")
    customer_ids = []
    for customer in CUSTOMERS:
        user = {
            "name": customer["name"],
            "email": customer["email"],
            "password": hash_password("password123"),
            "role": "customer",
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(30, 365)),
        }
        result = users_collection.insert_one(user)
        customer_ids.append(result.inserted_id)
    print(f"  Created {len(CUSTOMERS)} customers ✅")
    return customer_ids


def seed_technicians():
    print("Seeding technicians...")
    technician_ids = []
    
    # Distribute technicians across categories
    categories_list = [cat["name"] for cat in CATEGORIES]
    
    for i in range(40):
        first_name = TECH_FIRST_NAMES[i]
        last_name = TECH_LAST_NAMES[i]
        
        # Assign 1-3 skills to each technician
        num_skills = random.randint(1, 3)
        skills = random.sample(categories_list, num_skills)
        
        # Generate random stats
        completed_jobs = random.randint(10, 200)
        total_ratings = random.randint(5, completed_jobs)
        avg_rating = round(random.uniform(3.5, 5.0), 1)
        
        # Location around NYC area
        base_lat, base_lng = random.choice(LOCATIONS)
        lat = base_lat + random.uniform(-0.05, 0.05)
        lng = base_lng + random.uniform(-0.05, 0.05)
        
        technician = {
            "name": f"{first_name} {last_name}",
            "email": f"{first_name.lower()}.{last_name.lower()}@repairgo.com",
            "skills": skills,
            "experience_years": random.randint(1, 20),
            "availability": random.choice([True, True, True, False]),  # 75% available
            "workload": random.randint(0, 5),
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "rating": avg_rating,
            "total_ratings": total_ratings,
            "completed_jobs": completed_jobs,
            "is_verified": True,
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(60, 500)),
            "last_active": datetime.utcnow() - timedelta(hours=random.randint(0, 48)),
        }
        
        # Insert technician first to get ID
        result = technicians_collection.insert_one(technician)
        technician_ids.append(result.inserted_id)
        
        # Then add to users collection with technician_id reference
        user = {
            "name": technician["name"],
            "email": technician["email"],
            "password": hash_password("tech123"),
            "role": "technician",
            "is_active": True,
            "created_at": technician["created_at"],
            "technician_id": str(result.inserted_id),
        }
        users_collection.insert_one(user)
    
    print(f"  Created 40 technicians ✅")
    return technician_ids


def seed_services(customer_ids, technician_ids):
    print("Seeding service history...")
    
    statuses = ["pending", "assigned", "on_the_way", "in_progress", "completed", "rated"]
    urgencies = ["low", "medium", "high"]
    service_count = 0
    
    # Get technician data for matching
    technicians = list(technicians_collection.find())
    
    # Create 100+ services with various statuses
    for _ in range(150):
        customer_id = random.choice(customer_ids)
        customer = users_collection.find_one({"_id": customer_id})
        
        # Pick a random category
        category = random.choice(CATEGORIES)["name"]
        
        # Find a technician with this skill (or random if none)
        matching_techs = [t for t in technicians if category in t["skills"]]
        if matching_techs:
            technician = random.choice(matching_techs)
        else:
            technician = random.choice(technicians)
        
        # Generate service dates (past 6 months)
        days_ago = random.randint(0, 180)
        created_at = datetime.utcnow() - timedelta(days=days_ago)
        
        # Status distribution (more completed than pending)
        if days_ago > 30:
            status = random.choices(
                ["completed", "rated", "cancelled"],
                weights=[40, 50, 10]
            )[0]
        elif days_ago > 7:
            status = random.choices(
                ["completed", "rated", "in_progress", "assigned"],
                weights=[30, 40, 15, 15]
            )[0]
        else:
            status = random.choices(
                ["pending", "assigned", "on_the_way", "in_progress", "completed"],
                weights=[20, 25, 15, 20, 20]
            )[0]
        
        # Location
        base_lat, base_lng = random.choice(LOCATIONS)
        lat = base_lat + random.uniform(-0.03, 0.03)
        lng = base_lng + random.uniform(-0.03, 0.03)
        
        # Pricing
        urgency = random.choice(urgencies)
        base_price = next(c["base_price"] for c in CATEGORIES if c["name"] == category)
        urgency_addon = {"low": 0, "medium": 20, "high": 45}[urgency]
        distance = random.uniform(1, 15)
        travel_fee = distance * 2.5
        estimated_price = round(base_price + urgency_addon + travel_fee, 2)
        
        # Rating (only for completed/rated services)
        rating = None
        if status in ["completed", "rated"]:
            rating = random.choices([3, 4, 5], weights=[10, 25, 65])[0]
        
        service = {
            "customer_id": str(customer_id),
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "technician_id": str(technician["_id"]) if status not in ["pending"] else None,
            "technician_name": technician["name"] if status not in ["pending"] else None,
            "category": category,
            "description": random.choice(SERVICE_DESCRIPTIONS.get(category, ["General repair needed"])),
            "urgency": urgency,
            "status": status,
            "location": {
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
            },
            "estimated_price": estimated_price,
            "final_price": estimated_price if status in ["completed", "rated"] else None,
            "rating": rating,
            "created_at": created_at,
            "updated_at": created_at + timedelta(hours=random.randint(1, 72)) if status != "pending" else created_at,
            "completed_at": created_at + timedelta(hours=random.randint(2, 96)) if status in ["completed", "rated"] else None,
            "notes": None,
            "payment_status": "paid" if status in ["completed", "rated"] else "pending",
        }
        
        result = services_collection.insert_one(service)
        service_count += 1
        
        # Create payment record for completed services
        if status in ["completed", "rated"]:
            payment = {
                "service_id": str(result.inserted_id),
                "customer_id": str(customer_id),
                "technician_id": str(technician["_id"]),
                "amount": estimated_price,
                "payment_method": random.choice(["card", "cash", "wallet"]),
                "status": "completed",
                "transaction_id": f"TXN{random.randint(100000, 999999)}",
                "created_at": service["completed_at"],
            }
            payments_collection.insert_one(payment)
        
        # Create feedback record for rated services
        if status == "rated" and rating:
            feedback = {
                "service_id": str(result.inserted_id),
                "customer_id": str(customer_id),
                "technician_id": str(technician["_id"]),
                "rating": rating,
                "comment": random.choice([
                    "Great service, very professional!",
                    "Quick and efficient work.",
                    "Solved the problem perfectly.",
                    "Very knowledgeable technician.",
                    "Would recommend to others.",
                    "Good value for money.",
                    "Arrived on time and finished quickly.",
                    "Excellent communication throughout.",
                    None,
                ]),
                "created_at": service["completed_at"] + timedelta(hours=random.randint(1, 24)),
            }
            feedback_collection.insert_one(feedback)
    
    print(f"  Created {service_count} services ✅")


def print_summary():
    print("\n" + "="*50)
    print("DATABASE SEED SUMMARY")
    print("="*50)
    print(f"Admin Users: 1")
    print(f"Customers: {users_collection.count_documents({'role': 'customer'})}")
    print(f"Technicians: {technicians_collection.count_documents({})}")
    print(f"Categories: {categories_collection.count_documents({})}")
    print(f"Services: {services_collection.count_documents({})}")
    print(f"Payments: {payments_collection.count_documents({})}")
    print(f"Feedback: {feedback_collection.count_documents({})}")
    print("="*50)
    print("\nLOGIN CREDENTIALS:")
    print("-"*50)
    print("Admin:    admin@repairgo.com / admin123")
    print("Customer: john.smith@email.com / password123")
    print("          (any customer email with password123)")
    print("Tech:     james.garcia@repairgo.com / tech123")
    print("          (any tech email with tech123)")
    print("="*50)


def main():
    print("\n🚀 Starting RepairGo Database Seed...\n")
    
    clear_data()
    seed_categories()
    seed_admin()
    customer_ids = seed_customers()
    technician_ids = seed_technicians()
    seed_services(customer_ids, technician_ids)
    print_summary()
    
    print("\n✅ Database seeding completed successfully!\n")


if __name__ == "__main__":
    main()
