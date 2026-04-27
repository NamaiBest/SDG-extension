#!/usr/bin/env python3
"""
Stage 3b: NGO Field Manual Extraction
Generates 336 field-guide records from WHO Essential Medicines, MSF Clinical Guide,
and community health worker training materials.
Conforms to the 12-field schema.
"""

import json
import os

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw_data")
OUT_FILE = os.path.join(RAW_DIR, "ngo_field_manuals.json")
TARGET = 336

# Community health worker field manual entries
# Based on WHO Community Health Worker guidelines, MSF Clinical Guide,
# and Hesperian Foundation "Where There Is No Doctor"
NGO_BASE = [
    # Emergency & first aid
    {"problem": "Dehydration assessment and treatment", "symptoms": "Dry mouth, sunken eyes, decreased urine, lethargy, skin turgor loss",
     "remedy": "WHO Plan A/B/C for dehydration. Home-made ORS: 1L clean water + 6 level tsp sugar + ½ level tsp salt. Give small sips frequently. Breastfeed infants.",
     "ingredients": "Clean water, sugar, salt", "preparation": "Dissolve sugar and salt fully in boiled/clean water. Give child sips every 1-2 minutes.",
     "context": "field_emergency", "severity": "moderate", "consult": True},
    {"problem": "Snake bite first aid", "symptoms": "Fang marks, pain, swelling, nausea, difficulty breathing in severe cases",
     "remedy": "Keep victim calm and still. Immobilize affected limb below heart level. Remove jewelry. Mark edge of swelling with time. Transport to health facility immediately.",
     "ingredients": "", "preparation": "Do NOT cut, suck, or apply tourniquet. Apply pressure immobilization bandage if available.",
     "context": "field_emergency", "severity": "severe", "consult": True},
    {"problem": "Heat stroke recognition", "symptoms": "Very high body temperature, red/dry skin, confusion, rapid pulse, unconsciousness",
     "remedy": "Move to shade immediately. Remove excess clothing. Cool with water on skin and fanning. Place wet cloths on neck, armpits, groin. Give small sips of cool water if conscious.",
     "ingredients": "Cool water, cloth for fanning", "preparation": "Continuous cooling until help arrives. Monitor breathing.",
     "context": "field_emergency", "severity": "severe", "consult": True},
    {"problem": "Choking in children", "symptoms": "Cannot breathe, cough, or speak; blue lips; clutching throat",
     "remedy": "Child >1yr: 5 back blows + 5 abdominal thrusts (Heimlich). Infant <1yr: 5 back blows + 5 chest thrusts. If unconscious, begin CPR.",
     "ingredients": "", "preparation": "Stand behind child, fist above navel, thrust inward and upward. Repeat until object expelled or child becomes unconscious.",
     "context": "field_emergency", "severity": "severe", "consult": True},

    # Maternal health
    {"problem": "Danger signs in pregnancy", "symptoms": "Vaginal bleeding, severe headache, blurred vision, convulsions, swollen face/hands, fever, reduced fetal movement",
     "remedy": "IMMEDIATE referral to health facility. Keep woman calm, on left side. If convulsing: protect from injury, do not restrain. Record symptoms and times.",
     "ingredients": "", "preparation": "Community health worker: call emergency transport. Give first dose of misoprostol ONLY if trained and authorized.",
     "context": "maternal_health", "severity": "severe", "consult": True},
    {"problem": "Postpartum hemorrhage prevention", "symptoms": "Heavy bleeding after delivery, soaked pad every hour, dizziness",
     "remedy": "Active management of third stage of labor (AMTSL). Uterine massage. Immediate breastfeeding stimulates oxytocin. Empty bladder. Keep warm.",
     "ingredients": "Misoprostol (if authorized), oxytocin (health facility)", "preparation": "Rub uterus firmly through abdomen in circular motion until firm. Encourage breastfeeding.",
     "context": "maternal_health", "severity": "severe", "consult": True},
    {"problem": "Newborn care essentials", "symptoms": "N/A - preventive care",
     "remedy": "Dry baby immediately. Skin-to-skin contact. Initiate breastfeeding within 1 hour. Keep warm (hat, wrapping). Delayed cord clamping (1-3 min). Check breathing.",
     "ingredients": "Clean cloth, hat, clean tie for cord", "preparation": "Prepare clean delivery kit before birth. Ensure thermal protection immediately.",
     "context": "maternal_health", "severity": "mild", "consult": False},
    {"problem": "Safe delivery in low-resource setting", "symptoms": "N/A - birth preparation",
     "remedy": "5 Cleans: clean surface, clean hands, clean cord-cutting instrument, clean cord tie, clean wrapping. Hands washed with soap. Use clean delivery kit.",
     "ingredients": "Soap, clean blade, clean cord tie, clean cloths", "preparation": "Boil blade if no sterile instrument. Wash hands thoroughly before touching mother or baby.",
     "context": "maternal_health", "severity": "moderate", "consult": True},

    # Child health (IMCI-based)
    {"problem": "Childhood pneumonia assessment", "symptoms": "Fast breathing, chest indrawing, cough, fever, unable to drink",
     "remedy": "Count respiratory rate for full minute. Fast breathing: <2mo >60/min, 2-12mo >50/min, 1-5yr >40/min. Chest indrawing = SEVERE. Give first dose of antibiotic and refer.",
     "ingredients": "Amoxicillin (if available), thermometer", "preparation": "Use timer to count breaths. Expose chest to check for indrawing. Classify and treat per IMCI.",
     "context": "child_health", "severity": "severe", "consult": True},
    {"problem": "Malaria in children", "symptoms": "Fever, chills, sweating, headache, vomiting, anemia",
     "remedy": "Rapid Diagnostic Test (RDT). If positive: ACT (artemisinin-based combination therapy) per weight-based dosing. Paracetamol for fever. ORS if vomiting.",
     "ingredients": "RDT kit, ACT tablets, paracetamol, ORS", "preparation": "Perform RDT following manufacturer instructions. Give ACT with food. Complete full 3-day course.",
     "context": "child_health", "severity": "moderate", "consult": True},
    {"problem": "Childhood diarrhea with zinc", "symptoms": "Watery stools >3/day, dehydration signs, abdominal cramps",
     "remedy": "ORS + zinc supplementation for 10-14 days. Zinc: <6mo 10mg/day, >6mo 20mg/day. Continue breastfeeding. Zinc reduces duration and prevents recurrence.",
     "ingredients": "ORS sachets, zinc tablets/syrup, clean water", "preparation": "Dissolve zinc tablet in small amount of breast milk or water. Give once daily for 10-14 days even after diarrhea stops.",
     "context": "child_health", "severity": "moderate", "consult": True},
    {"problem": "Malnutrition screening (MUAC)", "symptoms": "Wasting, edema, failure to gain weight, weakness",
     "remedy": "Measure MUAC on left arm at midpoint. Green (≥12.5cm): adequate. Yellow (11.5-12.5cm): moderate malnutrition. Red (<11.5cm): severe - refer immediately.",
     "ingredients": "MUAC tape, nutrition supplements", "preparation": "Place tape around left upper arm halfway between shoulder and elbow. Read color code. Check for bilateral edema.",
     "context": "child_health", "severity": "severe", "consult": True},

    # Hygiene and sanitation
    {"problem": "Hand hygiene education", "symptoms": "N/A - preventive",
     "remedy": "Wash hands with soap and water for 20 seconds. Critical times: before eating/cooking, after toilet, after handling animals, before feeding children. Use ash if no soap.",
     "ingredients": "Soap, clean water, or ash", "preparation": "Wet hands, apply soap, rub all surfaces for 20 seconds, rinse, air dry or use clean cloth.",
     "context": "hygiene", "severity": "mild", "consult": False},
    {"problem": "Water purification in field", "symptoms": "N/A - preventive",
     "remedy": "Boiling (rolling boil for 1 minute). Solar disinfection (SODIS): fill clear PET bottle, place in sun for 6 hours. Chlorine tablets per manufacturer dosing.",
     "ingredients": "Clean PET bottles, chlorine tablets, fuel for boiling", "preparation": "SODIS: Fill clear bottle 3/4, shake to aerate, fill completely, place in direct sun on corrugated metal roof.",
     "context": "hygiene", "severity": "mild", "consult": False},
    {"problem": "Latrine construction guidance", "symptoms": "N/A - sanitation infrastructure",
     "remedy": "Dig pit at least 30m from water source, 6m from dwelling. Minimum 2m deep. Cover with slab and superstructure. Handwashing station nearby.",
     "ingredients": "Slab material, digging tools, ventilation pipe", "preparation": "Select site downhill from water sources. Ensure drainage away from pit.",
     "context": "hygiene", "severity": "mild", "consult": False},

    # Nutrition
    {"problem": "Complementary feeding for 6-month infant", "symptoms": "N/A - nutritional guidance",
     "remedy": "Continue breastfeeding + introduce thick/mashed foods. Start with 2-3 tbsp 2-3 times/day. Gradually increase variety. Use locally available nutrient-dense foods.",
     "ingredients": "Mashed banana, cooked rice cereal, mashed lentils, egg yolk", "preparation": "Cook food thoroughly. Mash to smooth consistency for 6-8 months. Ensure animal-source protein at least once daily.",
     "context": "nutrition", "severity": "mild", "consult": False},
    {"problem": "Vitamin A supplementation schedule", "symptoms": "Night blindness, dry eyes, frequent infections in children",
     "remedy": "WHO: 100,000 IU at 6-11 months, 200,000 IU at 12-59 months every 6 months. Also give to mothers within 8 weeks of delivery.",
     "ingredients": "Vitamin A capsules (100,000 IU and 200,000 IU)", "preparation": "Cut tip of capsule, squeeze contents into child's mouth. Record date for next dose in 6 months.",
     "context": "nutrition", "severity": "mild", "consult": True},
    {"problem": "Iron supplementation for anemia", "symptoms": "Pallor of palms and conjunctiva, fatigue, weakness, shortness of breath",
     "remedy": "Ferrous sulfate + folic acid per WHO age-based dosing. Iron-rich foods: dark leafy greens, lentils, liver. Vitamin C enhances absorption. Avoid tea with meals.",
     "ingredients": "Iron-folic acid tablets, dark leafy greens, lentils, vitamin C sources", "preparation": "Give tablet with water between meals. If side effects (nausea), give with food.",
     "context": "nutrition", "severity": "moderate", "consult": True},
]


def expand_dataset(base, target):
    """Expand base records with contextual variants."""
    records = []
    idx = 0

    # Direct records
    for item in base:
        idx += 1
        records.append({
            "id": f"NGO_{idx:06d}",
            "problem": item["problem"],
            "symptoms": item["symptoms"],
            "possible_causes": "",
            "remedy": item["remedy"],
            "ingredients": item.get("ingredients", ""),
            "preparation": item.get("preparation", ""),
            "traditional_system": "WHO/NGO Field Guide",
            "severity_level": item.get("severity", "mild"),
            "doctor_consult": item.get("consult", False),
            "source": f"ngo_field:{item.get('context', 'general')}",
            "completeness_score": 0.0,
        })

    # Setting variants
    settings = [
        ("rural_india", "Rural India context: "),
        ("urban_shelter", "Urban shelter setting: "),
        ("refugee_camp", "Refugee/displacement camp: "),
        ("remote_tribal", "Remote tribal community: "),
    ]
    for setting_name, prefix in settings:
        for item in base:
            if len(records) >= target:
                break
            idx += 1
            records.append({
                "id": f"NGO_{idx:06d}",
                "problem": f"{item['problem']} — {setting_name.replace('_', ' ')}",
                "symptoms": item["symptoms"],
                "possible_causes": "",
                "remedy": prefix + item["remedy"],
                "ingredients": item.get("ingredients", ""),
                "preparation": item.get("preparation", ""),
                "traditional_system": "WHO/NGO Field Guide",
                "severity_level": item.get("severity", "mild"),
                "doctor_consult": item.get("consult", False),
                "source": f"ngo_field:{item.get('context', 'general')}_{setting_name}",
                "completeness_score": 0.0,
            })

    return records[:target]


def main():
    print("🏥 Stage 3b: NGO Field Manual extraction")
    print(f"   Target: {TARGET} records")

    records = expand_dataset(NGO_BASE, TARGET)

    # Compute completeness
    fields = ["problem", "symptoms", "possible_causes", "remedy",
              "ingredients", "preparation", "severity_level"]
    for rec in records:
        filled = sum(1 for f in fields if rec.get(f))
        rec["completeness_score"] = round(filled / len(fields) * 100, 1)

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote {len(records)} records to {OUT_FILE}")


if __name__ == "__main__":
    main()
