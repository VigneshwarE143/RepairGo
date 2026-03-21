from database import technicians_collection
from bson import ObjectId

# Find assigned technician
tech = technicians_collection.find_one({'_id': ObjectId('699dad6817f0da66d3f27cd4')})
if tech:
    print(f"Assigned Technician: {tech['name']}")
    print(f"Email: {tech['email']}")
    print(f"Skills: {tech['skills']}")
else:
    print("Technician not found")
