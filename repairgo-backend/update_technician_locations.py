"""
Update all technician locations to Chennai and nearby areas.
"""

from database import technicians_collection
import random

# Chennai and nearby locations with coordinates
CHENNAI_LOCATIONS = [
    {"name": "Navallur", "lat": 12.8458, "lng": 80.2275},
    {"name": "Sholinganallur", "lat": 12.8996, "lng": 80.2275},
    {"name": "Avadi", "lat": 13.1067, "lng": 80.1097},
    {"name": "Anna Nagar", "lat": 13.0850, "lng": 80.2101},
    {"name": "Tambaram", "lat": 12.9249, "lng": 80.1000},
    {"name": "T. Nagar", "lat": 13.0418, "lng": 80.2341},
    {"name": "Velachery", "lat": 12.9815, "lng": 80.2180},
    {"name": "Adyar", "lat": 13.0012, "lng": 80.2565},
    {"name": "Porur", "lat": 13.0382, "lng": 80.1565},
    {"name": "Guindy", "lat": 13.0067, "lng": 80.2206},
    {"name": "Chromepet", "lat": 12.9516, "lng": 80.1462},
    {"name": "Pallavaram", "lat": 12.9675, "lng": 80.1491},
    {"name": "Perambur", "lat": 13.1188, "lng": 80.2320},
    {"name": "Kodambakkam", "lat": 13.0524, "lng": 80.2255},
    {"name": "Mylapore", "lat": 13.0368, "lng": 80.2676},
    {"name": "Egmore", "lat": 13.0732, "lng": 80.2609},
    {"name": "Nungambakkam", "lat": 13.0569, "lng": 80.2425},
    {"name": "Thiruvanmiyur", "lat": 12.9830, "lng": 80.2594},
    {"name": "Medavakkam", "lat": 12.9188, "lng": 80.1924},
    {"name": "Perungudi", "lat": 12.9641, "lng": 80.2478},
    {"name": "Thoraipakkam", "lat": 12.9324, "lng": 80.2278},
    {"name": "OMR (Karapakkam)", "lat": 12.9276, "lng": 80.2312},
    {"name": "Palavanthangal", "lat": 12.9667, "lng": 80.1983},
    {"name": "Nanganallur", "lat": 12.9833, "lng": 80.1833},
    {"name": "Madipakkam", "lat": 12.9623, "lng": 80.1986},
    {"name": "Besant Nagar", "lat": 13.0002, "lng": 80.2668},
    {"name": "Kilpauk", "lat": 13.0833, "lng": 80.2417},
    {"name": "Ashok Nagar", "lat": 13.0359, "lng": 80.2121},
    {"name": "Vadapalani", "lat": 13.0520, "lng": 80.2121},
    {"name": "Saidapet", "lat": 13.0227, "lng": 80.2231},
    {"name": "Kotturpuram", "lat": 13.0145, "lng": 80.2428},
    {"name": "Alwarpet", "lat": 13.0339, "lng": 80.2512},
    {"name": "Teynampet", "lat": 13.0445, "lng": 80.2520},
    {"name": "Royapettah", "lat": 13.0550, "lng": 80.2640},
    {"name": "Triplicane", "lat": 13.0589, "lng": 80.2769},
    {"name": "Chetpet", "lat": 13.0722, "lng": 80.2453},
    {"name": "Purasawalkam", "lat": 13.0897, "lng": 80.2567},
    {"name": "Villivakkam", "lat": 13.1107, "lng": 80.2050},
    {"name": "Ambattur", "lat": 13.0986, "lng": 80.1620},
    {"name": "Padi", "lat": 13.1053, "lng": 80.1925},
]


def update_technician_locations():
    """Update all technician locations to Chennai areas."""
    
    technicians = list(technicians_collection.find({}))
    
    print(f"Found {len(technicians)} technicians to update")
    
    updated_count = 0
    
    for i, tech in enumerate(technicians):
        # Assign a location (cycle through if more technicians than locations)
        location = CHENNAI_LOCATIONS[i % len(CHENNAI_LOCATIONS)]
        
        # Add small random offset to avoid exact same coordinates
        lat_offset = random.uniform(-0.005, 0.005)
        lng_offset = random.uniform(-0.005, 0.005)
        
        # Update technician with new location
        result = technicians_collection.update_one(
            {"_id": tech["_id"]},
            {
                "$set": {
                    "latitude": location["lat"] + lat_offset,
                    "longitude": location["lng"] + lng_offset,
                    "home_latitude": tech.get("home_latitude", location["lat"] + lat_offset),
                    "home_longitude": tech.get("home_longitude", location["lng"] + lng_offset),
                    "location": {
                        "type": "Point",
                        "coordinates": [
                            location["lng"] + lng_offset,
                            location["lat"] + lat_offset
                        ]
                    },
                    "area": location["name"],
                    "city": "Chennai"
                }
            }
        )
        
        if result.modified_count > 0:
            updated_count += 1
            print(f"✅ Updated {tech.get('name', 'Unknown')} → {location['name']} ({location['lat']:.4f}, {location['lng']:.4f})")
    
    print(f"\n✅ Successfully updated {updated_count} technician locations to Chennai areas")
    
    # Verify updates
    print("\n--- Verification ---")
    for tech in technicians_collection.find({}).limit(10):
        area = tech.get("area", "N/A")
        lat = tech.get("latitude", 0)
        lng = tech.get("longitude", 0)
        print(f"{tech.get('name')}: {area} - [{lat:.4f}, {lng:.4f}]")
    
    return updated_count


if __name__ == "__main__":
    update_technician_locations()
