import swisseph as se
import pytz
import math
import streamlit as st
from datetime import datetime, date, time
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import os
import logging
from pytz import common_timezones
import io
try:
    from timezonefinder import TimezoneFinder
    TZF = TimezoneFinder()
except Exception:
    TZF = None

# Predefined place choices (extendable)
PLACE_CHOICES = [
    "Select Place...",
    "Vijayawada, India",
    "Hyderabad, India",
    "Visakhapatnam, India",
    "Guntur, India",
    "Mumbai, India",
    "Pune, India",
    "Delhi, India",
    "Bengaluru, India",
    "Chennai, India",
    "Kolkata, India",
    "Tirupati, India",
    "Warangal, India",
    "Rajahmundry, India",
    "Nellore, India",
    "Other (enter manually)",
]

# --- 1. CONFIGURATION AND CONSTANTS ---

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd() 
EPHE_PATH = os.path.join(BASE_DIR, "ephe/")

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='kp_match.log', 
    filemode='w' 
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

logging.info("Application starting up.")

SE_AYANAMSA = se.SIDM_KRISHNAMURTI

# --- Planet List ---
PLANET_IDS_ALL = {
    se.SUN: "Sun",
    se.MOON: "Moon",
    se.MERCURY: "Mercury",
    se.VENUS: "Venus",
    se.MARS: "Mars",
    se.JUPITER: "Jupiter",
    se.SATURN: "Saturn",
    se.TRUE_NODE: "Rahu",
    # Ketu is calculated manually
}

PLANET_NAMES = {
    se.SUN: "Sun", se.MOON: "Moon", se.MERCURY: "Mercury", se.VENUS: "Venus",
    se.MARS: "Mars", se.JUPITER: "Jupiter", se.SATURN: "Saturn", se.TRUE_NODE: "Rahu",
}

DASHA_PERIODS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]
NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
SIGN_LORD_MAP = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon", 4: "Sun", 5: "Mercury",
    6: "Venus", 7: "Mars", 8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter",
}

# --- Parashari Natural Friendship Table ---
GRAHA_MAITRI_PARASHARI = {
    "Sun": {"Sun": 2, "Moon": 2, "Mars": 2, "Mercury": 1, "Jupiter": 2, "Venus": 0, "Saturn": 0},
    "Moon": {"Sun": 2, "Moon": 2, "Mars": 1, "Mercury": 2, "Jupiter": 1, "Venus": 1, "Saturn": 0},
    "Mars": {"Sun": 2, "Moon": 2, "Mars": 2, "Mercury": 0, "Jupiter": 2, "Venus": 1, "Saturn": 0},
    "Mercury": {"Sun": 2, "Moon": 0, "Mars": 1, "Mercury": 2, "Jupiter": 1, "Venus": 2, "Saturn": 1},
    "Jupiter": {"Sun": 2, "Moon": 2, "Mars": 2, "Mercury": 0, "Jupiter": 2, "Venus": 0, "Saturn": 1},
    "Venus": {"Sun": 1, "Moon": 1, "Mars": 1, "Mercury": 2, "Jupiter": 0, "Venus": 2, "Saturn": 2},
    "Saturn": {"Sun": 0, "Moon": 0, "Mars": 0, "Mercury": 2, "Jupiter": 1, "Venus": 2, "Saturn": 2},
}

# --- Planet Dignity Maps ---
PLANET_OWN_SIGN = {
    "Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
    "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]
}
PLANET_EXALTATION = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
PLANET_DEBILITATION = {"Sun": 6, "Moon": 7, "Mars": 3, "Mercury": 11, "Jupiter": 9, "Venus": 5, "Saturn": 0}

ZODIAC_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

geolocator = Nominatim(user_agent="kp_match_app")

# --- 2. CORE CALCULATION FUNCTIONS ---

def find_house_index(longitude, cusps):
    for i in range(0, 12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        house_num = i + 1
        if start < end:
            if start <= longitude < end:
                return house_num
        else:
            if start <= longitude or longitude < end:
                return house_num
    return 0

def find_house_from_lagna(planet_lon, lagna_lon):
    """Calculates Whole Sign House (1-12) from Lagna."""
    # Ensure lagna_lon is a float
    if isinstance(lagna_lon, list) and len(lagna_lon) > 0:
        lagna_lon = lagna_lon[0] # Handle if lagna was passed as cusps list
    
    lagna_sign = int(lagna_lon / 30)
    planet_sign = int(planet_lon / 30)
    house = (planet_sign - lagna_sign + 12) % 12 + 1
    return house

# --- Navamsa (D9) Calculation ---
def get_navamsa_longitude(d1_lon):
    PADA_SIZE = 3 + 20/60
    d1_lon_in_sign = d1_lon % 30
    d1_sign_index = int(d1_lon / 30)
    pada_index = int(d1_lon_in_sign / PADA_SIZE) 
    
    # Movable Signs: Aries(0), Cancer(3), Libra(6), Capricorn(9) -> Start from sign itself
    if d1_sign_index in [0, 3, 6, 9]: 
        start_sign = d1_sign_index
    # Fixed Signs: Taurus(1), Leo(4), Scorpio(7), Aquarius(10) -> Start from 9th (index + 8)
    elif d1_sign_index in [1, 4, 7, 10]: 
        start_sign = (d1_sign_index + 8) % 12
    # Dual Signs: Gemini(2), Virgo(5), Sagittarius(8), Pisces(11) -> Start from 5th (index + 4)
    else: 
        start_sign = (d1_sign_index + 4) % 12
        
    d9_sign_index = (start_sign + pada_index) % 12
    d9_lon = (d9_sign_index * 30) + 15 
    return d9_lon

# --- D50 (50th Harmonic) Calculation ---
def get_d50_longitude(d1_lon):
    d50_lon = (d1_lon * 50.0) % 360.0
    return d50_lon

# --- Parashari Friendship Checker ---
def check_parashari_friendship(lord1, lord2):
    if lord1 not in GRAHA_MAITRI_PARASHARI: lord1_map = {} 
    else: lord1_map = GRAHA_MAITRI_PARASHARI[lord1]
    
    if lord2 not in GRAHA_MAITRI_PARASHARI: lord2_map = {}
    else: lord2_map = GRAHA_MAITRI_PARASHARI[lord2]
    
    l1_to_l2 = lord1_map.get(lord2, 1)
    l2_to_l1 = lord2_map.get(lord1, 1)
    
    if l1_to_l2 == 2 and l2_to_l1 == 2: return "Great Friends"
    if l1_to_l2 == 2 or l2_to_l1 == 2: return "Friends"
    if l1_to_l2 == 0 and l2_to_l1 == 0: return "Great Enemies"
    if l1_to_l2 == 0 or l2_to_l1 == 0: return "Enemies"
    return "Neutral"

def get_julian_day(dob: date, tob: time, timezone_str: str):
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.utc
    local_dt = tz.localize(datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second))
    utc_dt = local_dt.astimezone(pytz.utc)
    return se.utc_to_jd(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour, utc_dt.minute, utc_dt.second)[1]

def longitude_to_dms(lon):
    lon = lon % 360
    degrees = int(lon)
    minutes_float = (lon - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60, 2)
    return f"{degrees}° {minutes}' {seconds}\""

def get_sign_name(lon):
    sign_index = int(lon / 30)
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return signs[sign_index % 12]

def get_nakshatra_and_pada(longitude: float):
    longitude = longitude % 360
    nakshatra_span = 13 + 20 / 60
    nak_index = int(longitude / nakshatra_span) % 27
    nak_name = NAKSHATRA_NAMES[nak_index]
    nak_start = nak_index * nakshatra_span
    offset = longitude - nak_start
    pada_span = nakshatra_span / 4.0
    pada = int(offset / pada_span) + 1
    return nak_name, pada

def get_star_sub_lord(longitude):
    nakshatra_span = 13 + 20 / 60
    longitude = longitude % 360
    nakshatra_index = int(longitude / nakshatra_span) % 27
    star_lord = NAKSHATRA_LORDS[nakshatra_index]
    nakshatra_start_deg = nakshatra_index * nakshatra_span
    relative_deg = longitude - nakshatra_start_deg
    nakshatra_fraction_completed = relative_deg / nakshatra_span
    star_lord_index = NAKSHATRA_LORDS[:9].index(star_lord)
    cumulative_time_in_nakshatra = nakshatra_fraction_completed * 120
    current_cumulative_time = 0
    sub_lord = "N/A"
    for i in range(9):
        lord_index = (star_lord_index + i) % 9
        lord = NAKSHATRA_LORDS[lord_index]
        period = DASHA_PERIODS[lord]
        current_cumulative_time += period
        if cumulative_time_in_nakshatra < current_cumulative_time:
            sub_lord = lord
            break
    return star_lord, sub_lord

def get_significators(planet_lon, all_cusps, chart_planets):
    s1_s2_significators = set()
    s3_s4_significators = set()
    star_lord_name, sub_lord_name = get_star_sub_lord(planet_lon)
    planet_sign_index = int(planet_lon / 30) % 12
    planet_owner = SIGN_LORD_MAP.get(planet_sign_index)
    star_lord_lookup = star_lord_name
    if star_lord_name in ["Rahu", "Ketu"]:
        node_sign_lon = chart_planets.get(star_lord_name)
        if node_sign_lon is not None:
            star_lord_sign_index = int(node_sign_lon / 30) % 12
            star_lord_lookup = SIGN_LORD_MAP.get(star_lord_sign_index)
        else:
            star_lord_lookup = None
    if star_lord_lookup is not None:
        star_lord_lon = chart_planets.get(star_lord_lookup)
        if isinstance(star_lord_lon, (float, int)):
            star_lord_house = find_house_index(star_lord_lon, all_cusps)
            if star_lord_house > 0:
                s1_s2_significators.add(star_lord_house)
            for i in range(0, 12):
                cusp_lon = all_cusps[i]
                sign_index = int(cusp_lon / 30) % 12
                sign_lord = SIGN_LORD_MAP.get(sign_index)
                if sign_lord == star_lord_lookup:
                    s1_s2_significators.add(i + 1)
    planet_house = find_house_index(planet_lon, all_cusps)
    if planet_house > 0:
        s3_s4_significators.add(planet_house)
    for i in range(0, 12):
        cusp_lon = all_cusps[i]
        sign_index = int(cusp_lon / 30) % 12
        sign_lord = SIGN_LORD_MAP.get(sign_index)
        if sign_lord == planet_owner:
            s3_s4_significators.add(i + 1)
    return sorted(list(s1_s2_significators)) + sorted(list(s3_s4_significators))

def calculate_ashtakoota(chart1_data, chart2_data):
    nakshatra_span = 13 + 20 / 60
    moon_lon_c1 = chart1_data["moon_lon"]
    moon_lon_c2 = chart2_data["moon_lon"]
    nak_index_c1 = int(moon_lon_c1 % 360 / nakshatra_span) % 27
    nak_index_c2 = int(moon_lon_c2 % 360 / nakshatra_span) % 27
    moon_rasi_index_c1 = int(moon_lon_c1 / 30) % 12
    moon_rasi_index_c2 = int(moon_lon_c2 / 30) % 12
    total_score = 0
    details = []

    # 1. VARNA (1 Point)
    def get_varna_rank(rasi_index):
        if rasi_index in [3, 7, 11]: return 3, "Brahmin"
        if rasi_index in [0, 4, 8]: return 2, "Kshatriya"
        if rasi_index in [1, 5, 9]: return 1, "Vaishya"
        return 0, "Shudra"
    
    v1, v1_name = get_varna_rank(moon_rasi_index_c1)
    v2, v2_name = get_varna_rank(moon_rasi_index_c2)
    v_score = 1 if v1 >= v2 else 0
    total_score += v_score
    details.append(["Varna (Work)", f"{v_score} / 1", f"N1: {v1_name}, N2: {v2_name}", "N1 >= N2 is Good"])
    
    # 2. VASHYA (2 Points)
    def get_vashya_group(rasi_index, moon_lon):
        deg_in_sign = moon_lon % 30
        if rasi_index in [2, 5, 6, 10]: return 0, "Nara"
        if rasi_index in [0, 1]: return 1, "Chatushpada"
        if rasi_index in [3, 11]: return 2, "Jalachara"
        if rasi_index == 4: return 3, "Simha"
        if rasi_index == 7: return 4, "Keeta"
        if rasi_index == 8:
            return (0, "Nara") if deg_in_sign < 15 else (1, "Chatushpada")
        if rasi_index == 9:
            return (1, "Chatushpada") if deg_in_sign < 15 else (2, "Jalachara")
        return 0, "Nara"
        
    vas1, vas1_name = get_vashya_group(moon_rasi_index_c1, moon_lon_c1)
    vas2, vas2_name = get_vashya_group(moon_rasi_index_c2, moon_lon_c2)

    vashya_matrix = {
        0: {0: 2, 1: 1, 2: 0.5, 3: 0, 1: 1, 4: 1},
        1: {0: 0, 1: 2, 2: 1, 3: 0, 4: 1},
        2: {0: 0.5, 1: 1, 2: 2, 3: 0, 4: 0},
        3: {0: 0, 1: 0.5, 2: 1, 3: 2, 4: 0},
        4: {0: 1, 1: 1, 2: 0, 3: 0, 4: 2},
    }
    vas_score = vashya_matrix.get(vas2, {}).get(vas1, 0)
    total_score += vas_score
    details.append(["Vashya (Dominance)", f"{vas_score} / 2", f"N1: {vas1_name}, N2: {vas2_name}", "Bride→Groom Vashya matrix with 0.5 steps"])

    count_bride_to_groom = (nak_index_c1 - nak_index_c2 + 27) % 27 + 1
    count_groom_to_bride = (nak_index_c2 - nak_index_c1 + 27) % 27 + 1
    rem_bride_to_groom = count_bride_to_groom % 9
    rem_groom_to_bride = count_groom_to_bride % 9
    bad_tara = [1, 3, 5, 7]
    tara_score = 3 if (rem_bride_to_groom not in bad_tara and rem_groom_to_bride not in bad_tara) else 1.5
    total_score += tara_score
    details.append(["Tara (Destiny)", f"{tara_score} / 3", f"Dist: {count_bride_to_groom} & {count_groom_to_bride}", "Both directions favorable => 3, otherwise 1.5"])
    
    # 4. YONI (4 Points)
    nak_to_yoni = {
        0: 'Horse', 1: 'Elephant', 2: 'Sheep', 3: 'Snake', 4: 'Snake', 5: 'Dog', 6: 'Cat', 7: 'Sheep', 8: 'Cat',
        9: 'Rat', 10: 'Rat', 11: 'Cow', 12: 'Buffalo', 13: 'Tiger', 14: 'Buffalo', 15: 'Tiger', 16: 'Deer', 17: 'Deer',
        18: 'Dog', 19: 'Monkey', 20: 'Mongoose', 21: 'Monkey', 22: 'Lion', 23: 'Horse', 24: 'Lion', 25: 'Cow', 26: 'Elephant'
    }
    y1 = nak_to_yoni.get(nak_index_c1)
    y2 = nak_to_yoni.get(nak_index_c2)
    
    enemies = [
        {'Cow', 'Tiger'}, {'Elephant', 'Lion'}, {'Horse', 'Buffalo'}, 
        {'Dog', 'Deer'}, {'Snake', 'Mongoose'}, {'Monkey', 'Sheep'}, {'Cat', 'Rat'}
    ]
    
    yoni_score = 0
    if y1 == y2: 
        yoni_score = 4
    else:
        is_enemy = False
        for pair in enemies:
            if y1 in pair and y2 in pair:
                is_enemy = True
                break
        if is_enemy:
            yoni_score = 0
        else:
            yoni_score = 2
    total_score += yoni_score
    details.append(["Yoni (Nature)", f"{yoni_score} / 4", f"N1: {y1}, N2: {y2}", "Same=4, Enemy=0, Else=2"])

    # 5. GRAHA MAITRI (5 Points)
    rasi_lord_map = {0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon", 4: "Sun", 5: "Mercury", 
                     6: "Venus", 7: "Mars", 8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"}
    l1 = rasi_lord_map.get(moon_rasi_index_c1)
    l2 = rasi_lord_map.get(moon_rasi_index_c2)
    
    def get_maitri_points(lord1, lord2):
        if lord1 == lord2: return 5
        l1_map = GRAHA_MAITRI_PARASHARI.get(lord1, {})
        l2_map = GRAHA_MAITRI_PARASHARI.get(lord2, {})
        s1 = l1_map.get(lord2, 1)
        s2 = l2_map.get(lord1, 1)
        if s1 == 2 and s2 == 2: return 5
        if (s1 == 2 and s2 == 1) or (s1 == 1 and s2 == 2): return 4
        if s1 == 1 and s2 == 1: return 3
        if (s1 == 2 and s2 == 0) or (s1 == 0 and s2 == 2): return 1
        if (s1 == 1 and s2 == 0) or (s1 == 0 and s2 == 1): return 0.5
        return 0
        
    gm_score = get_maitri_points(l1, l2)
    total_score += gm_score
    details.append(["Graha Maitri", f"{gm_score} / 5", f"Lords: {l1} - {l2}", "Friendship of Rasi Lords"])

    # 6. GANA (6 Points)
    def get_gana_group(ni):
        if ni in [0, 4, 6, 7, 12, 14, 16, 21, 26]: return 0, "Deva"
        if ni in [1, 3, 5, 10, 11, 19, 20, 24, 25]: return 1, "Manusha"
        return 2, "Rakshasa"
        
    g1, g1_name = get_gana_group(nak_index_c1)
    g2, g2_name = get_gana_group(nak_index_c2)
    
    gana_score = 0
    if g1 == g2: gana_score = 6
    elif (g1 == 0 and g2 == 1) or (g1 == 1 and g2 == 0): gana_score = 6
    elif (g1 == 1 and g2 == 2) or (g1 == 2 and g2 == 1): gana_score = 0
    else: gana_score = 1
    total_score += gana_score
    details.append(["Gana (Temperament)", f"{gana_score} / 6", f"N1: {g1_name}, N2: {g2_name}", "Deva>Manusha>Rakshasa"])

    # 7. BHAKOOT (7 Points)
    d_bhakoot = (moon_rasi_index_c2 - moon_rasi_index_c1 + 12) % 12
    bad_bhakoot = [1, 4, 5, 7, 8, 11] # 2, 5, 6, 8, 9, 12 distances
    
    bhakoot_score = 0
    reason = "Good Position"
    if d_bhakoot not in bad_bhakoot:
        bhakoot_score = 7
    else:
        if l1 == l2: 
            bhakoot_score = 7
            reason = "Exception: Same Lords"
        elif (l1, l2) in [("Sun", "Moon"), ("Moon", "Sun")]: 
            bhakoot_score = 7
            reason = "Exception: Friendly Lords"
        else: 
            bhakoot_score = 0
            reason = "Dosha (2-12, 5-9, 6-8)"
            
    total_score += bhakoot_score
    details.append(["Bhakoot (Love)", f"{bhakoot_score} / 7", f"Distance: {d_bhakoot if d_bhakoot!=0 else 12}/12", reason])

    nadi_groups = {
        0: 0, 5: 0, 6: 0, 11: 0, 12: 0, 17: 0, 18: 0, 23: 0, 24: 0,
        1: 1, 4: 1, 7: 1, 10: 1, 13: 1, 16: 1, 19: 1, 22: 1, 25: 1,
        2: 2, 3: 2, 8: 2, 9: 2, 14: 2, 15: 2, 20: 2, 21: 2, 26: 2
    }
    n1 = nadi_groups.get(nak_index_c1, nak_index_c1 % 3)
    n2 = nadi_groups.get(nak_index_c2, nak_index_c2 % 3)
    nadi_names = ["Adi", "Madhya", "Antya"]
    p1 = get_nakshatra_and_pada(moon_lon_c1)[1]
    p2 = get_nakshatra_and_pada(moon_lon_c2)[1]
    nadi_exception = False
    if nak_index_c1 == nak_index_c2 and p1 == 1 and p2 == 1:
        nadi_exception = True
    if moon_rasi_index_c1 == moon_rasi_index_c2:
        nadi_exception = True
    if nak_index_c1 == nak_index_c2 and moon_rasi_index_c1 != moon_rasi_index_c2:
        nadi_exception = True
    nadi_score = 8 if (n1 != n2 or nadi_exception) else 0
    total_score += nadi_score
    nadi_rule = "Different Nadi preferred; same Nadi is high-priority dosha unless classical exception applies"
    if nadi_exception:
        nadi_rule = "Classical Nadi exception applied"
    details.append(["Nadi (Health)", f"{nadi_score} / 8", f"N1: {nadi_names[n1]}, N2: {nadi_names[n2]}", nadi_rule])
    
    return min(max(round(total_score), 0), 36), details

def calculate_supplementary_factors(chart1_data, chart2_data):
    results = {}
    details = []

    def add_factor(key, factor, c1, c2, rule, verdict):
        results[key] = verdict
        details.append({
            "factor": factor,
            "c1": c1,
            "c2": c2,
            "rule": rule,
            "verdict": verdict
        })

    c1_dosha = chart1_data["mars_dosha_status"]["Total"] == "Afflicted"
    c2_dosha = chart2_data["mars_dosha_status"]["Total"] == "Afflicted"
    if c1_dosha == c2_dosha:
        kuja_verdict = "Matched"
    elif c1_dosha:
        kuja_verdict = f"Unmatched ({chart1_data['name']})"
    else:
        kuja_verdict = f"Unmatched ({chart2_data['name']})"
    add_factor(
        "Kuja_Dosha_Parity",
        "Kuja Dosha Parity",
        chart1_data["mars_dosha_status"]["Total"],
        chart2_data["mars_dosha_status"]["Total"],
        "Parity of Kuja Dosha is preferred.",
        kuja_verdict
    )

    c1_rahu = chart1_data["rahu_dosha_status"]["Total"]
    c2_rahu = chart2_data["rahu_dosha_status"]["Total"]
    rahu_verdict = "Matched" if c1_rahu == c2_rahu else "Mixed"
    add_factor(
        "Rahu_Ketu_Parity",
        "Rahu/Ketu Affliction Parity",
        c1_rahu,
        c2_rahu,
        "Similar nodal affliction pattern is considered balanced.",
        rahu_verdict
    )

    c1_pitra = "Present" if chart1_data["pitra_dosha_present"] else "Absent"
    c2_pitra = "Present" if chart2_data["pitra_dosha_present"] else "Absent"
    pitra_verdict = "Clean" if c1_pitra == "Absent" and c2_pitra == "Absent" else ("Present in Both" if c1_pitra == "Present" and c2_pitra == "Present" else "Mixed")
    add_factor(
        "Pitra_Dosha_Match",
        "Pitra Dosha Match",
        c1_pitra,
        c2_pitra,
        "Sun/Moon with Rahu/Ketu or nodal 9th-house involvement.",
        pitra_verdict
    )

    malefics = ["Sun", "Mars", "Saturn", "Rahu", "Ketu"]
    c1_mal_7 = sum(1 for p in malefics if find_house_index(chart1_data["planets"][p], chart1_data["cusps"]) == 7)
    c2_mal_7 = sum(1 for p in malefics if find_house_index(chart2_data["planets"][p], chart2_data["cusps"]) == 7)
    if c1_mal_7 == 0 and c2_mal_7 == 0:
        seventh_house_verdict = "Strong"
    elif c1_mal_7 <= 1 and c2_mal_7 <= 1:
        seventh_house_verdict = "Moderate"
    else:
        seventh_house_verdict = "Afflicted"
    add_factor(
        "Seventh_House_Condition",
        "7th House Condition",
        f"{c1_mal_7} malefic links",
        f"{c2_mal_7} malefic links",
        "Lower malefic pressure on 7th house is preferred.",
        seventh_house_verdict
    )

    def get_lord_dignity(chart_data):
        seventh_sign = int(chart_data["cusps"][6] / 30) % 12
        seventh_lord = SIGN_LORD_MAP[seventh_sign]
        lord_lon = chart_data["planets"].get(seventh_lord)
        lord_sign = int(lord_lon / 30) % 12 if lord_lon is not None else None
        if lord_sign is None:
            return "Unknown"
        if seventh_lord in PLANET_OWN_SIGN and lord_sign in PLANET_OWN_SIGN[seventh_lord]:
            return "Own Sign"
        if seventh_lord in PLANET_EXALTATION and lord_sign == PLANET_EXALTATION[seventh_lord]:
            return "Exalted"
        if seventh_lord in PLANET_DEBILITATION and lord_sign == PLANET_DEBILITATION[seventh_lord]:
            return "Debilitated"
        return "Ordinary"

    c1_lord_dignity = get_lord_dignity(chart1_data)
    c2_lord_dignity = get_lord_dignity(chart2_data)
    if c1_lord_dignity in ["Own Sign", "Exalted"] and c2_lord_dignity in ["Own Sign", "Exalted"]:
        seventh_lord_verdict = "Strong"
    elif c1_lord_dignity == "Debilitated" or c2_lord_dignity == "Debilitated":
        seventh_lord_verdict = "Weak"
    else:
        seventh_lord_verdict = "Average"
    add_factor(
        "Seventh_Lord_Dignity",
        "7th Lord Dignity",
        c1_lord_dignity,
        c2_lord_dignity,
        "Own/exalted 7th lord supports stability.",
        seventh_lord_verdict
    )

    moon_lord_friendship = check_parashari_friendship(chart1_data["rasi_lord"], chart2_data["rasi_lord"])
    add_factor(
        "Rasi_Lord_Friendship",
        "Moon Rasi Lord Friendship",
        chart1_data["rasi_lord"],
        chart2_data["rasi_lord"],
        "Friendship of Moon sign lords supports emotional harmony.",
        moon_lord_friendship
    )

    c1_lagna_lord = SIGN_LORD_MAP.get(int(chart1_data["cusps"][0] / 30) % 12)
    c2_lagna_lord = SIGN_LORD_MAP.get(int(chart2_data["cusps"][0] / 30) % 12)
    lagna_friendship = check_parashari_friendship(c1_lagna_lord, c2_lagna_lord)
    add_factor(
        "Lagna_Lord_Friendship",
        "Lagna Lord Friendship",
        c1_lagna_lord,
        c2_lagna_lord,
        "Lagna lord relationship indicates baseline temperament match.",
        lagna_friendship
    )

    d9_lagna_friendship = check_parashari_friendship(chart1_data["d9_lagna_lord"], chart2_data["d9_lagna_lord"])
    add_factor(
        "D9_Lagna_Lord_Friendship",
        "D9 Lagna Lord Friendship",
        chart1_data["d9_lagna_lord"],
        chart2_data["d9_lagna_lord"],
        "Navamsa lagna lords reflect married-life resonance.",
        d9_lagna_friendship
    )

    c1_venus_lord = SIGN_LORD_MAP[int(chart1_data["planets"]["Venus"] / 30) % 12]
    c2_venus_lord = SIGN_LORD_MAP[int(chart2_data["planets"]["Venus"] / 30) % 12]
    venus_friendship = check_parashari_friendship(c1_venus_lord, c2_venus_lord)
    add_factor(
        "Venus_Sign_Compatibility",
        "Venus Sign-Lord Harmony",
        c1_venus_lord,
        c2_venus_lord,
        "Venus sign-lord harmony supports relationship comfort.",
        venus_friendship
    )

    c1_jupiter_lord = SIGN_LORD_MAP[int(chart1_data["planets"]["Jupiter"] / 30) % 12]
    c2_jupiter_lord = SIGN_LORD_MAP[int(chart2_data["planets"]["Jupiter"] / 30) % 12]
    jupiter_friendship = check_parashari_friendship(c1_jupiter_lord, c2_jupiter_lord)
    add_factor(
        "Jupiter_Sign_Compatibility",
        "Jupiter Sign-Lord Harmony",
        c1_jupiter_lord,
        c2_jupiter_lord,
        "Jupiter sign-lord harmony supports dharma alignment.",
        jupiter_friendship
    )

    c1_mars_house = find_house_index(chart1_data["planets"]["Mars"], chart1_data["cusps"])
    c2_mars_house = find_house_index(chart2_data["planets"]["Mars"], chart2_data["cusps"])
    mars_dist = abs(c1_mars_house - c2_mars_house)
    mars_dist = min(mars_dist, 12 - mars_dist)
    mars_verdict = "Supportive" if mars_dist in [0, 1, 4, 5] else "Challenging"
    add_factor(
        "Mars_House_Harmony",
        "Mars House Harmony",
        f"{c1_mars_house}H",
        f"{c2_mars_house}H",
        "Closer/trinal Mars house resonance is preferred.",
        mars_verdict
    )

    c1_sat_house = find_house_index(chart1_data["planets"]["Saturn"], chart1_data["cusps"])
    c2_sat_house = find_house_index(chart2_data["planets"]["Saturn"], chart2_data["cusps"])
    sat_dist = abs(c1_sat_house - c2_sat_house)
    sat_dist = min(sat_dist, 12 - sat_dist)
    sat_verdict = "Supportive" if sat_dist in [0, 1, 4, 5] else "Challenging"
    add_factor(
        "Saturn_House_Harmony",
        "Saturn House Harmony",
        f"{c1_sat_house}H",
        f"{c2_sat_house}H",
        "Saturn resonance indicates long-term adjustment potential.",
        sat_verdict
    )

    def tithi_number(moon_lon, sun_lon):
        diff = (moon_lon - sun_lon) % 360
        return int(diff / 12) + 1

    c1_tithi = tithi_number(chart1_data["planets"]["Moon"], chart1_data["planets"]["Sun"])
    c2_tithi = tithi_number(chart2_data["planets"]["Moon"], chart2_data["planets"]["Sun"])
    tithi_gap = abs(c1_tithi - c2_tithi)
    tithi_verdict = "Balanced" if tithi_gap <= 6 else "Varied"
    add_factor(
        "Tithi_Harmony",
        "Tithi Harmony",
        f"Tithi {c1_tithi}",
        f"Tithi {c2_tithi}",
        "Closer lunar day temperament tends to be smoother.",
        tithi_verdict
    )

    return results, details


def get_graha_position_details(planet_name, longitude):
    star_lord, sub_lord = get_star_sub_lord(longitude)
    rasi_index = int(longitude / 30) % 12
    rasi_lord = SIGN_LORD_MAP.get(rasi_index)
    nak_name, pada = get_nakshatra_and_pada(longitude)
    return [planet_name, rasi_lord, star_lord, sub_lord, longitude_to_dms(longitude), nak_name, f"Pada {pada}"]

def check_kuja_cancellation(mars_lon, planets, d9_planets, moon_lon, sun_lon):
    mars_sign_index = int(mars_lon / 30) % 12
    if mars_sign_index in PLANET_OWN_SIGN["Mars"]: return True, "Cancelled (Own Sign D1)"
    if mars_sign_index == PLANET_EXALTATION["Mars"]: return True, "Cancelled (Exalted D1)"
    if mars_sign_index == PLANET_DEBILITATION["Mars"]: return True, "Cancelled (Debilitated D1)"
    if mars_sign_index in [4, 8, 10, 11]: return True, "Cancelled (Benefic/Friendly Sign D1)"

    benefics = {"Jupiter": planets.get("Jupiter"), "Venus": planets.get("Venus")}
    moon_sun_dist = abs(moon_lon - sun_lon)
    if moon_sun_dist > 150 and moon_sun_dist < 210: benefics["Moon"] = moon_lon

    for name, ben_lon in benefics.items():
        if ben_lon is None: continue
        ben_sign_index = int(ben_lon / 30) % 12
        if abs(mars_lon - ben_lon) < 8 or abs(mars_lon - ben_lon) > 352: return True, f"Cancelled (Conj. {name} D1)"
        aspect_7th_sign = (ben_sign_index + 6) % 12
        if mars_sign_index == aspect_7th_sign: return True, f"Cancelled (Aspect {name} D1)"
            
    jup_lon = planets.get("Jupiter")
    if jup_lon is not None:
        jup_sign_index = int(jup_lon / 30) % 12
        if mars_sign_index in [(jup_sign_index + 4) % 12, (jup_sign_index + 8) % 12]:
            return True, "Cancelled (Aspect Jupiter D1)"

    mars_d9_lon = d9_planets.get("Mars")
    if mars_d9_lon is not None:
        mars_d9_sign = int(mars_d9_lon / 30)
        if mars_d9_sign in PLANET_OWN_SIGN["Mars"]: return True, "Cancelled (Own Sign D9)"
        if mars_d9_sign == PLANET_EXALTATION["Mars"]: return True, "Cancelled (Exalted D9)"
        if mars_d9_sign == PLANET_DEBILITATION["Mars"]: return True, "Cancelled (Debilitated D9)"

    return False, "Afflicted"

def check_doshas_from_points(mars_house, rahu_house, moon_house, venus_house, mars_lon, planets, d9_planets, moon_lon, sun_lon):
    kuja_dosha_houses = [2, 4, 7, 8, 12]
    mars_from_moon = ((mars_house - moon_house + 12) % 12) + 1
    mars_from_venus = ((mars_house - venus_house + 12) % 12) + 1

    lagna_afflicted = mars_house in kuja_dosha_houses
    chandra_afflicted = mars_from_moon in kuja_dosha_houses
    shukra_afflicted = mars_from_venus in kuja_dosha_houses
    
    mars_dosha_status = {
        "Lagna": "Afflicted" if lagna_afflicted else "Clean",
        "Chandra": "Afflicted" if chandra_afflicted else "Clean",
        "Shukra": "Afflicted" if shukra_afflicted else "Clean",
        "Total": "Not Afflicted",
    }

    if lagna_afflicted or chandra_afflicted or shukra_afflicted:
        is_cancelled, reason = check_kuja_cancellation(mars_lon, planets, d9_planets, moon_lon, sun_lon)
        if is_cancelled: mars_dosha_status["Total"] = reason 
        else: mars_dosha_status["Total"] = "Afflicted"
    
    rahu_dosha_houses = [1, 5, 9]
    rahu_from_moon = ((rahu_house - moon_house + 12) % 12) + 1
    rahu_dosha_status = {
        "Lagna": "Afflicted" if rahu_house in rahu_dosha_houses else "Clean",
        "Chandra": "Afflicted" if rahu_from_moon in rahu_dosha_houses else "Clean",
        "Total": "Not Afflicted",
    }
    if "Afflicted" in rahu_dosha_status.values():
        rahu_dosha_status["Total"] = "Afflicted"

    return mars_dosha_status, rahu_dosha_status

def calculate_vimsottari_dasha(birth_jd, moon_lon, target_jd):
    NAKSHATRA_SPAN = 13 + 20 / 60
    DASHAS_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    TOTAL_DASHAS_YEARS = 120.0
    DAYS_PER_YEAR = 365.25
    moon_lon = moon_lon % 360
    nak_index = int(moon_lon / NAKSHATRA_SPAN)
    nak_lord_at_birth = NAKSHATRA_LORDS[nak_index % 27]
    nak_start_deg = nak_index * NAKSHATRA_SPAN
    offset_deg = moon_lon - nak_start_deg
    fraction_covered = offset_deg / NAKSHATRA_SPAN
    lord_index_at_birth = DASHAS_LORDS.index(nak_lord_at_birth)
    total_dasha_years = DASHA_PERIODS[nak_lord_at_birth]
    remaining_years = (1 - fraction_covered) * total_dasha_years
    remaining_days = remaining_years * DAYS_PER_YEAR
    md_start_jd = birth_jd - (fraction_covered * total_dasha_years * DAYS_PER_YEAR)
    md_end_jd = birth_jd + remaining_days
    current_md_lord = nak_lord_at_birth
    current_md_start_jd = md_start_jd
    current_md_end_jd = md_end_jd
    current_lord_index = lord_index_at_birth
    while target_jd >= current_md_end_jd:
        current_lord_index = (current_lord_index + 1) % 9
        current_md_lord = DASHAS_LORDS[current_lord_index]
        current_md_start_jd = current_md_end_jd
        md_years = DASHA_PERIODS[current_md_lord]
        current_md_end_jd += (md_years * DAYS_PER_YEAR)
    
    ad_lord_index = current_lord_index
    current_ad_lord = DASHAS_LORDS[ad_lord_index]
    current_ad_start_jd = current_md_start_jd
    ad_years_prop = DASHA_PERIODS[current_ad_lord]
    ad_days = (DASHA_PERIODS[current_md_lord] * ad_years_prop / TOTAL_DASHAS_YEARS) * DAYS_PER_YEAR
    current_ad_end_jd = current_ad_start_jd + ad_days
    while target_jd >= current_ad_end_jd:
        ad_lord_index = (ad_lord_index + 1) % 9
        current_ad_lord = DASHAS_LORDS[ad_lord_index]
        current_ad_start_jd = current_ad_end_jd
        ad_years_prop = DASHA_PERIODS[current_ad_lord]
        ad_days = (DASHA_PERIODS[current_md_lord] * ad_years_prop / TOTAL_DASHAS_YEARS) * DAYS_PER_YEAR
        current_ad_end_jd += ad_days

    pd_lord_index = ad_lord_index
    current_pd_lord = DASHAS_LORDS[pd_lord_index]
    current_pd_start_jd = current_ad_start_jd
    pd_years_prop = DASHA_PERIODS[current_pd_lord]
    pd_days = (DASHA_PERIODS[current_ad_lord] * pd_years_prop / TOTAL_DASHAS_YEARS) * DAYS_PER_YEAR
    current_pd_end_jd = current_pd_start_jd + pd_days
    while target_jd >= current_pd_end_jd:
        pd_lord_index = (pd_lord_index + 1) % 9
        current_pd_lord = DASHAS_LORDS[pd_lord_index]
        current_pd_start_jd = current_pd_end_jd
        pd_years_prop = DASHA_PERIODS[current_pd_lord]
        pd_days = (DASHA_PERIODS[current_ad_lord] * pd_years_prop / TOTAL_DASHAS_YEARS) * DAYS_PER_YEAR
        current_pd_end_jd += pd_days
    return current_md_lord, current_ad_lord, current_pd_lord


def analyze_chart(dob: date, tob: time, latitude: float, longitude: float, timezone_str: str, name: str):
    try:
        jd = get_julian_day(dob, tob, timezone_str)
        se.set_sid_mode(SE_AYANAMSA)

        result = se.houses_ex(jd, latitude, longitude, b"P", flags=se.FLG_SIDEREAL)
        raw_cusps = result[0]
        # Handle pyswisseph returning 13 elements (0, H1..H12) or 12 elements (H1..H12)
        if len(raw_cusps) == 13:
            cusps = list(raw_cusps)[1:13]
        else:
            cusps = list(raw_cusps)[0:12]
        
        planets = {}
        for p_id, p_name in PLANET_IDS_ALL.items():
            xx, ret = se.calc_ut(jd, p_id, flags=se.FLG_SIDEREAL)
            planets[p_name] = xx[0]
            
        if "Rahu" in planets:
            planets["Ketu"] = (planets["Rahu"] + 180.0) % 360.0
        
        # Explicitly add Lagna to D1 planets for uniformity
        planets["Lagna"] = cusps[0]

        # D9 Calculation (Full)
        d9_planets = {}
        for p_name, p_lon in planets.items():
            if p_name == "Lagna":
                d9_planets["Lagna"] = get_navamsa_longitude(cusps[0])
            else:
                d9_planets[p_name] = get_navamsa_longitude(p_lon)
        
        d9_lagna_lon = d9_planets["Lagna"]
        d9_lagna_lord = SIGN_LORD_MAP[int(d9_lagna_lon / 30) % 12]
        
        # D50 Calculation (Full)
        d50_planets = {}
        for p_name, p_lon in planets.items():
             if p_name == "Lagna":
                 d50_planets["Lagna"] = get_d50_longitude(cusps[0])
             else:
                 d50_planets[p_name] = get_d50_longitude(p_lon)
        
        d50_lagna_lon = d50_planets["Lagna"]
        d50_lagna_lord = SIGN_LORD_MAP[int(d50_lagna_lon / 30) % 12]
        
        # D1 Data
        moon_lon = planets["Moon"]
        venus_lon = planets["Venus"]
        mars_lon = planets["Mars"]
        sun_lon = planets["Sun"]
        moon_rasi_index = int(moon_lon / 30) % 12
        moon_rasi_lord = SIGN_LORD_MAP.get(moon_rasi_index)

        mars_house = find_house_index(mars_lon, cusps)
        moon_house = find_house_index(moon_lon, cusps)
        venus_house = find_house_index(venus_lon, cusps)
        rahu_house = find_house_index(planets["Rahu"], cusps)
        sun_house = find_house_index(sun_lon, cusps)
        
        mars_dosha_status, rahu_dosha_status = check_doshas_from_points(
            mars_house, rahu_house, moon_house, venus_house, 
            mars_lon, planets, d9_planets, moon_lon, sun_lon
        )

        pitra_dosha_present = False
        def check_conjunction(p1_lon, p2_lon, limit=10.0):
            if p1_lon is None or p2_lon is None: return False
            diff = abs(p1_lon - p2_lon)
            return diff < limit or diff > (360.0 - limit)
            
        rahu_lon = planets.get("Rahu")
        ketu_lon = planets.get("Ketu")
        sun_lon = planets.get("Sun")
        moon_lon = planets.get("Moon")
        
        # 1. Rahu/Ketu in 9th House
        if rahu_house == 9 or find_house_index(ketu_lon, cusps) == 9:
            pitra_dosha_present = True
        # 2. Sun or Moon conjunct Rahu/Ketu
        elif check_conjunction(sun_lon, rahu_lon) or check_conjunction(sun_lon, ketu_lon):
            pitra_dosha_present = True
        elif check_conjunction(moon_lon, rahu_lon) or check_conjunction(moon_lon, ketu_lon):
            pitra_dosha_present = True
        # 3. 9th Lord afflicted by Rahu/Ketu (Simple check: 9th Lord is Rahu/Ketu star lord?)
        # For now, stick to strong conjunction/placement.

        kp_positions = []
        kp_positions.append(get_graha_position_details("Lagna Cusp", cusps[0]))
        for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
            if p_name in planets:
                kp_positions.append(get_graha_position_details(p_name, planets[p_name]))

        seventh_cusp_lon = cusps[6]
        seventh_star, seventh_sub = get_star_sub_lord(seventh_cusp_lon)
        csl_planet_name = seventh_sub 
        csl_planet_lon = planets.get(csl_planet_name)
        if csl_planet_lon is None: csl_significators = [] 
        else: csl_significators = get_significators(csl_planet_lon, cusps, planets)
        
        marriage_promise = any(h in csl_significators for h in [2, 7, 11])
        marriage_denial = any(h in csl_significators for h in [1, 6, 10])
        if marriage_promise and not marriage_denial: promise_verdict = "STRONG"
        elif marriage_promise and marriage_denial: promise_verdict = "MIXED"
        elif not marriage_promise and marriage_denial: promise_verdict = "DENIAL"
        else: promise_verdict = "NEUTRAL" 

        planet_significators = {}
        all_planet_names = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
        for p_name in all_planet_names:
            if p_name in planets:
                planet_significators[p_name] = get_significators(planets[p_name], cusps, planets)
        
        jupiter_significators = planet_significators.get("Jupiter", [])
        saturn_significators = planet_significators.get("Saturn", [])
        venus_significators = planet_significators.get("Venus", [])
        planet_favorability = {}
        for p_name in ["Jupiter", "Saturn", "Venus", "Sun", "Mars"]:
            sigs = planet_significators.get(p_name, []) 
            favorable_links = sum(1 for h in sigs if h in [2, 5, 9, 11])
            unfavorable_links = sum(1 for h in sigs if h in [1, 6, 8, 12])
            if favorable_links > unfavorable_links: strength = "Favorable"
            elif unfavorable_links > favorable_links: strength = "Unfavorable"
            else: strength = "Neutral"
            planet_favorability[p_name] = f"{strength} ({favorable_links}F/{unfavorable_links}UF)"

        utc_now = datetime.utcnow()
        jd_today = se.utc_to_jd(utc_now.year, utc_now.month, utc_now.day, 0, 0, 0)[1]
        md_lord, ad_lord, pd_lord = calculate_vimsottari_dasha(jd, moon_lon, jd_today)

        d1_7th_lord_name = SIGN_LORD_MAP[int(cusps[6] / 30) % 12]
        d1_7th_lord_d9_lon = d9_planets.get(d1_7th_lord_name)
        d1_7th_lord_d9_house = find_house_from_lagna(d1_7th_lord_d9_lon, d9_lagna_lon)
        d1_7th_lord_d9_sign = get_sign_name(d1_7th_lord_d9_lon)

        analysis_data = {
            "name": name,
            "moon_lon": moon_lon,
            "planet_significators": planet_significators, 
            "jupiter_significators": jupiter_significators, 
            "saturn_significators": saturn_significators, 
            "venus_significators": venus_significators,
            "csl_significators": csl_significators,
            "mars_dosha_status": mars_dosha_status,
            "rahu_dosha_status": rahu_dosha_status,
            "pitra_dosha_present": pitra_dosha_present,
            "marriage_promise": promise_verdict,
            "cusps": cusps,
            "planets": planets,
            "planet_favorability": planet_favorability,
            "rasi_lord": moon_rasi_lord,
            "md_lord": md_lord,
            "ad_lord": ad_lord,
            "pd_lord": pd_lord,
            # Parashari/D9 data
            "d9_lagna_sign": get_sign_name(d9_lagna_lon),
            "d9_lagna_lord": d9_lagna_lord,
            "d1_7th_lord_name": d1_7th_lord_name,
            "d1_7th_lord_d9_house_text": f"In {d1_7th_lord_d9_house}H ({d1_7th_lord_d9_sign})",
            # Full D9 Data
            "d9_planets": d9_planets,
            # Full D50 Data
            "d50_planets": d50_planets,
            "d50_lagna_lord": d50_lagna_lord,
        }

        return {
            "name": name, "dob": str(dob), "tob": str(tob), "lat": latitude, "lon": longitude,
            "7th_csl": seventh_sub, "marriage_promise": promise_verdict,
            "csl_significators": csl_significators,
            "jupiter_significators": jupiter_significators,
            "saturn_significators": saturn_significators,
            "venus_significators": venus_significators,
            "moon_lon": moon_lon, "rasi_lord": moon_rasi_lord,
            "kp_positions": kp_positions,
            "mars_dosha_status": mars_dosha_status,
            "rahu_dosha_status": rahu_dosha_status,
            "pitra_dosha_present": pitra_dosha_present,
            "planet_favorability": planet_favorability,
            "planet_significators": planet_significators,
            "md_lord": md_lord, "ad_lord": ad_lord, "pd_lord": pd_lord,
            "analysis_data": analysis_data 
        }

    except Exception as e:
        logging.error(f"Exception in analyze_chart for {name}: {e}", exc_info=True)
        raise

def check_dasha_marriage_potential(significators):
    marriage_links = any(h in significators for h in [2, 7, 11])
    denial_links = any(h in significators for h in [1, 6, 10])
    if marriage_links and not denial_links: return "STRONG_PROMISE"
    elif marriage_links and denial_links: return "MIXED_RISK"
    elif denial_links: return "DENIAL_PERIOD"
    else: return "NEUTRAL"

def generate_compatibility_report(chart1, chart2, disclaimer_text=None, contact_name=None, contact_mobile=None):
    logging.debug("generate_compatibility_report() started")
    if not chart1 or not chart2:
        logging.error("Cannot generate report due to missing chart data.")
        return None

    supplementary_results, supplementary_details = calculate_supplementary_factors(chart1["analysis_data"], chart2["analysis_data"])
    guna_score, guna_details = calculate_ashtakoota(chart1["analysis_data"], chart2["analysis_data"])

    styles = getSampleStyleSheet()
    story = []
    table_style_data = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ])

    story.append(Paragraph("Vedic Matching 21-Fold Compatibility Report", styles["h1"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Italic"]))
    if contact_name or contact_mobile:
        ctext = f"Consultant: {contact_name or ''}   Mobile: {contact_mobile or ''}"
        story.append(Paragraph(ctext, styles["Normal"]))
    story.append(Spacer(1, 24))

    details_data = [
        ["Detail", chart1["name"], chart2["name"]],
        ["D.O.B.", chart1["dob"], chart2["dob"]],
        ["T.O.B.", chart1["tob"], chart2["tob"]],
        ["Lat / Lon", f"{chart1['lat']:.4f} / {chart1['lon']:.4f}", f"{chart2['lat']:.4f} / {chart2['lon']:.4f}"],
        ["Moon Rasi Lord", chart1["rasi_lord"], chart2["rasi_lord"]],
    ]
    story.append(Paragraph("1. Basic Natal Details", styles["h2"]))
    details_table = Table(details_data, colWidths=[130, 190, 190])
    details_table.setStyle(table_style_data)
    story.append(details_table)
    story.append(Spacer(1, 18))

    # --- 2. SOUTH INDIAN CHARTS (D1) ---
    story.append(Paragraph("2. Natal Charts (South Indian Style)", styles["h2"]))
    
    def get_south_chart_data(planet_data, title):
        abbr = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", 
                "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", 
                "Ketu": "Ke", "Lagna": "Asc"}
        signs = {i: [] for i in range(12)}
        for p, lon in planet_data.items():
            if p not in abbr: continue
            sign_idx = int(lon / 30) % 12
            signs[sign_idx].append(abbr[p])
        def c(idx): return "\n".join(signs[idx])
        data = [
            [c(11), c(0), c(1), c(2)],
            [c(10), title, "", c(3)],
            [c(9), "", "", c(4)],
            [c(8), c(7), c(6), c(5)]
        ]
        return data
    
    # Chart 1 D1
    c1_d1_data = get_south_chart_data(chart1["analysis_data"]["planets"], f"{chart1['name']}\nD1 (Rasi)")
    c2_d1_data = get_south_chart_data(chart2["analysis_data"]["planets"], f"{chart2['name']}\nD1 (Rasi)")
    
    chart_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('SPAN', (1,1), (2,2)) # Merge center for title
    ])
    
    t1 = Table(c1_d1_data, colWidths=[40,40,40,40], rowHeights=[40,40,40,40])
    t1.setStyle(chart_style)
    t2 = Table(c2_d1_data, colWidths=[40,40,40,40], rowHeights=[40,40,40,40])
    t2.setStyle(chart_style)
    
    # Container Table to hold them side-by-side
    container = Table([[t1, Spacer(20, 20), t2]])
    story.append(container)
    story.append(Spacer(1, 24))


    story.append(Paragraph("3. Major Dosha Analysis", styles["h2"]))
    dosha_data = [
        [Paragraph(str(cell), styles['Normal']) for cell in row]
        for row in [
            ["Dosha Check", chart1["name"], chart2["name"], "Severity"],
            ["Kuja Dosha", chart1["mars_dosha_status"]["Total"], chart2["mars_dosha_status"]["Total"], "Affliction from 3 points is severe."],
            ["Pitra Dosha", "Present" if chart1["pitra_dosha_present"] else "Clean", "Present" if chart2["pitra_dosha_present"] else "Clean", "Indicates issues with destiny/ancestral blessings."],
            ["Rahu/Ketu Affliction", chart1["rahu_dosha_status"]["Total"], chart2["rahu_dosha_status"]["Total"], "Indicates unpredictable challenges."],
        ]
    ]
    story.append(Table(dosha_data, colWidths=[120, 120, 120, 150], style=table_style_data))
    story.append(Spacer(1, 18))
    
    story.append(Paragraph("4. Vedic Guna Milan (Ashtakoota)", styles["h2"]))
    promise_data = [
        ["Factor", chart1["name"], chart2["name"], "Verdict/Score"],
        ["Vedic Guna Milan (36)", f"{guna_score} / 36", f"{guna_score} / 36", "36 max. 18+ is usually acceptable."],
    ]
    story.append(Table(promise_data, colWidths=[130, 90, 90, 190], style=table_style_data))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Detailed Guna Milan Breakdown:", styles["h3"]))
    guna_header = ["Koota (Factor)", "Score", "Description / Value", "Rule / Logic"]
    guna_table_data = [guna_header] + guna_details
    guna_table = Table(guna_table_data, colWidths=[110, 60, 150, 180])
    guna_table.setStyle(table_style_data)
    story.append(guna_table)
    story.append(Spacer(1, 12))
    
    # ------------------------------------------------------------------
    # NEW SECTIONS: FULL PLANETARY MATCHING WITH BHAVA (HOUSE)
    # ------------------------------------------------------------------
    
    def get_chart_match_row(planet_key, chart_dict1, chart_dict2):
        if planet_key == "Lagna":
            if "Lagna" in chart_dict1:
                s1_lon = chart_dict1["Lagna"]
                s2_lon = chart_dict2["Lagna"]
            else:
                return None
        else:
            s1_lon = chart_dict1.get(planet_key)
            s2_lon = chart_dict2.get(planet_key)
            
        if s1_lon is None or s2_lon is None: return [planet_key, "-", "-", "-"]
        
        sign1 = get_sign_name(s1_lon)
        sign2 = get_sign_name(s2_lon)
        lord1 = SIGN_LORD_MAP[int(s1_lon / 30) % 12]
        lord2 = SIGN_LORD_MAP[int(s2_lon / 30) % 12]
        
        # Get Bhava
        lagna1 = chart_dict1.get("Lagna", 0)
        bhava1 = find_house_from_lagna(s1_lon, lagna1)
        lagna2 = chart_dict2.get("Lagna", 0)
        bhava2 = find_house_from_lagna(s2_lon, lagna2)
        
        friendship = check_parashari_friendship(lord1, lord2)
        
        display1 = f"{sign1} ({lord1}) [{bhava1}H]"
        display2 = f"{sign2} ({lord2}) [{bhava2}H]"
        
        return [planet_key, display1, display2, friendship]

    def build_match_table(title, planet_keys, dict1, dict2):
        story.append(Spacer(1, 12))
        story.append(Paragraph(title, styles["h3"]))
        header = ["Planet", "N1 Sign", "N1 Bhava", "N2 Sign", "N2 Bhava", "Relation", "Points"]
        table_data = [header]
        
        total_pts = 0
        possible_pts = 0
        
        # Helper to get sign/lord/bhava
        def get_data(d, p, cusps, lagna_lon=None):
            if p not in d: return "-", "-", "-"
            lon = d[p]
            sign_idx = int(lon / 30) % 12
            sign_name = ZODIAC_SIGNS[sign_idx]
            lord = SIGN_LORD_MAP[sign_idx]
            
            if lagna_lon is not None:
                h_idx = find_house_from_lagna(lon, lagna_lon)
            else:
                h_idx = find_house_index(lon, cusps)
            return sign_name, lord, h_idx

        for planet in planet_keys:
            c1_cusps = chart1["analysis_data"]["cusps"]
            c2_cusps = chart2["analysis_data"]["cusps"]
            
            # For Divisional Charts (D9, D50), use Whole Sign House from their Lagna
            c1_lagna = dict1.get("Lagna") if "D1" not in title else None
            c2_lagna = dict2.get("Lagna") if "D1" not in title else None
            
            s1, l1, h1 = get_data(dict1, planet, c1_cusps, c1_lagna)
            s2, l2, h2 = get_data(dict2, planet, c2_cusps, c2_lagna)
            
            if s1 == "-": continue

            # Relation Points
            pts = 0
            rel = "Neutral"
            
            if l1 == l2: 
                pts = 5; rel = "Same Lord"
            else:
                fr1 = GRAHA_MAITRI_PARASHARI.get(l1, {}).get(l2, 1)
                fr2 = GRAHA_MAITRI_PARASHARI.get(l2, {}).get(l1, 1)
                if fr1==2 and fr2==2: pts=4; rel="Friends"
                elif fr1==0 and fr2==0: pts=0; rel="Enemies"
                elif (fr1==2 and fr2==0) or (fr1==0 and fr2==2): pts=1; rel="Mixed"
                else: pts=2; rel="Neutral"
            
            # Bhava Harmony (Only for D1 really relevant here with these cusps)
            if "D1" in title:
                h_dist = (h2 - h1 + 12) % 12
                if h_dist in [0, 4, 8]: pts += 2; rel += " + Trine"
                elif h_dist in [3, 6, 9]: pts += 1; rel += " + Kendra"
                elif h_dist in [5, 7]: pts -= 2; rel += " - 6/8 Dosha"
            
            pts = max(0, min(pts, 7))
            
            table_data.append([planet, f"{s1} ({l1})", h1, f"{s2} ({l2})", h2, rel, str(pts)])
            total_pts += pts
            possible_pts += 7

        t = Table(table_data, colWidths=[60, 80, 50, 80, 50, 100, 50])
        t.setStyle(table_style_data)
        story.append(t)
        story.append(Paragraph(f"<b>Total Score: {total_pts} / {possible_pts}</b>", styles["Normal"]))
        
        return round((total_pts / possible_pts) * 10, 1) if possible_pts > 0 else 0

    d1_score = build_match_table("5. Full D1 (Rasi) Match", ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"], chart1["analysis_data"]["planets"], chart2["analysis_data"]["planets"])
    
    # 8. D9 Match
    # Using simple logic for D9 planets since we don't have them pre-calculated in analysis_data except partially
    # But wait, analyze_chart DOES calculate d9_planets now! (Lines 725-730 in previous read)
    # So we can use chart1["analysis_data"]["d9_planets"] directly if available.
    # Let's check analyze_chart again.
    # Yes, it has "d9_planets": d9_planets
    
    d9_score = build_match_table("6. Full D9 (Navamsa) Match", ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"], chart1["analysis_data"]["d9_planets"], chart2["analysis_data"]["d9_planets"])

    # 9. D50 Match
    d50_score = build_match_table("7. Full D50 (Harmonic) Match", ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"], chart1["analysis_data"]["d50_planets"], chart2["analysis_data"]["d50_planets"])
    
    story.append(Spacer(1, 24))

    story.append(Paragraph("8. Vedic 21-Fold Matching Summary", styles["h2"]))
    twenty_one_data = [["Factor", chart1['name'] + " Status", chart2['name'] + " Status", "Compatibility Verdict"]]
    for koota in guna_details:
        twenty_one_data.append([f"Guna - {koota[0]}", koota[2], koota[2], koota[1]])
    for det in supplementary_details:
        twenty_one_data.append([det["factor"], det["c1"], det["c2"], det["verdict"]])
    story.append(Table(twenty_one_data, colWidths=[150, 100, 100, 160], style=table_style_data))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Detailed 21-Fold Rules", styles["h3"]))
    supp_header = ["Factor", "Native 1 Status", "Native 2 Status", "Rule/Logic", "Verdict"]
    supp_table_data = [supp_header]
    for koota in guna_details:
        supp_table_data.append([
            f"Guna - {koota[0]}",
            koota[2],
            koota[2],
            Paragraph(koota[3], styles["Normal"]),
            koota[1]
        ])
    for det in supplementary_details:
        supp_table_data.append([
            det["factor"],
            det["c1"],
            det["c2"],
            Paragraph(det["rule"], styles["Normal"]),
            det["verdict"]
        ])
    supp_table = Table(supp_table_data, colWidths=[100, 80, 80, 150, 100])
    supp_table.setStyle(table_style_data)
    story.append(supp_table)

    story.append(PageBreak())
    story.append(Paragraph("9. FINAL MATCH VERDICT", styles["h1"]))
    story.append(Spacer(1, 12))

    good_factors = 0
    total_factors_checked = len(guna_details) + len(supplementary_details)
    for koota in guna_details:
        pts = koota[1].split("/")
        gained = float(pts[0].strip()) if pts else 0
        if gained > 0:
            good_factors += 1
    for det in supplementary_details:
        v = det["verdict"].lower()
        if "unmatched" in v or "afflicted" in v or "weak" in v or "challenging" in v or "present in both" in v:
            continue
        good_factors += 1

    fold_summary_status = "Average"
    if good_factors >= 15: fold_summary_status = "Strong"
    elif good_factors < 10: fold_summary_status = "Weak"
    fold_summary_text = f"{fold_summary_status} ({good_factors}/{total_factors_checked} favorable)"

    final_verdict_text = "PROCEED"
    reasons_to_fail = []
    verdict_notes = []

    nadi_row = next((row for row in guna_details if row[0].startswith("Nadi")), None)
    nadi_unfavorable = False
    if nadi_row:
        try:
            nadi_unfavorable = float(nadi_row[1].split("/")[0].strip()) == 0.0
        except Exception:
            nadi_unfavorable = False

    if guna_score < 18: reasons_to_fail.append(f"Guna Milan ({guna_score}/36) below 18.")
    if nadi_unfavorable: reasons_to_fail.append("Nadi Koota is unfavorable (high-priority rule).")
    if fold_summary_status == "Weak": reasons_to_fail.append("Vedic 21-fold summary is weak.")

    if reasons_to_fail:
        final_verdict_text = "TRY ANOTHER MATCH"
        verdict_notes = reasons_to_fail
    else:
        reasons_for_caution = []
        if guna_score < 24: reasons_for_caution.append(f"Guna Milan is {guna_score}/36.")
        if fold_summary_status != "Strong": reasons_for_caution.append(f"Vedic 21-fold summary is {fold_summary_text}.")
        
        if reasons_for_caution:
            final_verdict_text = "PROCEED (With Caution)"
            verdict_notes = reasons_for_caution
        else:
            final_verdict_text = "PROCEED (Strongly Recommended)"
            verdict_notes.append("All major Vedic parameters are favorable.")
    
    verdict_summary_data = [
        ["Parameter", "Status", "Notes"],
        ["Vedic Guna Milan", f"{guna_score}/36", "Good" if guna_score >= 18 else "FAIL"],
        ["D1 Match (Sign/Bhava)", f"{d1_score}/10", "Friendly Sign Lords"],
        ["D9 Match (Sign/Bhava)", f"{d9_score}/10", "Friendly Sign Lords"],
        ["D50 Match (Sign/Bhava)", f"{d50_score}/10", "Friendly Sign Lords"],
        ["Vedic 21-Fold", fold_summary_text, "Combined 21-factor status"],
    ]
    
    verdict_table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ])

    verdict_table = Table(verdict_summary_data, colWidths=[140, 100, 260])
    verdict_table.setStyle(verdict_table_style)
    story.append(verdict_table)
    story.append(Spacer(1, 24))

    story.append(Paragraph(f"FINAL VERDICT: {final_verdict_text}", styles["h2"]))
    story.append(Spacer(1, 12))
    
    if verdict_notes:
        story.append(Paragraph("Reasoning / Notes:", styles["h3"]))
        for note in verdict_notes:
            story.append(Paragraph(f"• {note}", styles["Normal"]))

    story.append(Spacer(1, 24))
    story.append(Paragraph("Disclaimer", styles["h2"]))
    dtext = disclaimer_text or "This software provides astrological insights for educational purposes only. Decisions and outcomes remain the sole responsibility of the user."
    story.append(Paragraph(dtext, styles["Normal"]))
    if contact_name or contact_mobile:
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Contact: {contact_name or ''} | Mobile: {contact_mobile or ''}", styles["Normal"]))

    buffer = io.BytesIO()
    try:
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logging.error(f"PDF Error: {e}")
        return None


# --- STREAMLIT GUI APPLICATION ---

def fetch_lat_lon(place):
    try:
        location = geolocator.geocode(place, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        st.error(f"Geocoding Error: {e}")
        return None, None

def get_timezone_from_coords(lat, lon):
    try:
        if TZF:
            return TZF.timezone_at(lng=lon, lat=lat)
    except Exception as e:
        logging.warning(f"Timezone lookup failed: {e}")
    return None

def smart_place_search(query):
    """
    Enhanced search to handle cases like 'Nuzvidu' (Town) vs 'Nuzvidu Road' (Street).
    Prioritizes places/settlements over roads.
    """
    if not query: return []
    try:
        # 1. Initial Search
        results = geolocator.geocode(query, exactly_one=False, limit=10, timeout=10)
        if not results: results = []
        
        # 2. Check for places
        place_results = []
        other_results = []
        
        def is_place(loc):
            # Check Nominatim raw data for class/type
            cls = loc.raw.get('class', '')
            typ = loc.raw.get('type', '')
            # Prioritize settlements, boundaries (cities), etc.
            if cls in ['place', 'boundary'] or typ in ['city', 'town', 'village', 'hamlet', 'administrative']:
                return True
            return False

        for loc in results:
            if is_place(loc):
                place_results.append(loc)
            else:
                other_results.append(loc)

        # 3. Fallback for common South Indian suffix 'u' (e.g. Nuzvidu -> Nuzvid)
        # Only if no clear place was found in the top results for the original query
        if not place_results and query.strip().lower().endswith('u') and len(query.strip()) > 3:
            stripped_query = query.strip()[:-1]
            fallback_results = geolocator.geocode(stripped_query, exactly_one=False, limit=10, timeout=10)
            if fallback_results:
                for loc in fallback_results:
                    if is_place(loc):
                        place_results.append(loc)
                    else:
                        pass 
        
        # Combine: Places first, then others
        final_results = place_results + other_results
        
        # Remove duplicates based on address
        seen = set()
        unique_results = []
        for loc in final_results:
            if loc.address not in seen:
                seen.add(loc.address)
                unique_results.append(loc)
                
        return unique_results
    except Exception as e:
        st.error(f"Geocoding Error: {e}")
        return []

def build_tz_options(current_tz):
    base = ["Select Timezone..."] + sorted(common_timezones)
    if current_tz and current_tz not in base:
        base.insert(1, current_tz)
    return base

def main():
    st.set_page_config(page_title="Vedic 21-Fold Match-Making", layout="wide")
    st.title("Vedic 21-Fold Match-Making Software")

    # Initialize session state for widgets to avoid default-value conflicts
    if "n1_lat" not in st.session_state: st.session_state["n1_lat"] = 0.0
    if "n1_lon" not in st.session_state: st.session_state["n1_lon"] = 0.0
    if "n2_lat" not in st.session_state: st.session_state["n2_lat"] = 0.0
    if "n2_lon" not in st.session_state: st.session_state["n2_lon"] = 0.0
    if "n1_tz" not in st.session_state: st.session_state["n1_tz"] = "Select Timezone..."
    if "n2_tz" not in st.session_state: st.session_state["n2_tz"] = "Select Timezone..."
    if "n1_search_results" not in st.session_state: st.session_state["n1_search_results"] = []
    if "n2_search_results" not in st.session_state: st.session_state["n2_search_results"] = []
    
    # Initialize lat/lon with 0.0 only if not already set (which they shouldn't be if we are here)
    if "n1_lat" not in st.session_state: st.session_state["n1_lat"] = 0.0
    if "n1_lon" not in st.session_state: st.session_state["n1_lon"] = 0.0
    if "n2_lat" not in st.session_state: st.session_state["n2_lat"] = 0.0
    if "n2_lon" not in st.session_state: st.session_state["n2_lon"] = 0.0
    
    disclaimer = st.text_area("Disclaimer", value="Disclaimer: The insights and reports generated by this application are based on astrological calculations and interpretations. They are informational and should not be considered professional, legal, medical, or financial advice, nor a guarantee of outcomes. Users should exercise personal judgment and consult qualified professionals for important decisions. The developer and consultant assume no liability for actions taken based on this report.", height=150, key="disclaimer_text")
    contact_name = st.text_input("Contact Name", value="jph pratap sarma", placeholder="Your name", key="contact_name")
    contact_mobile = st.text_input("Mobile Number", value="9963436736", placeholder="Your mobile", key="contact_mobile")

    # Ephemeris Check
    if not os.path.exists(EPHE_PATH):
        st.error(f"Ephemeris path not found: {EPHE_PATH}. Please create an 'ephe' folder and add Swiss Ephemeris files.")
        return
    else:
        se.set_ephe_path(EPHE_PATH)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Boy (Native 1) Details")
        n1_name = st.text_input("Name", value="", placeholder="Enter name", key="n1_name")
        n1_dob_str = st.text_input("Date of Birth (DDMMYYYY)", value="", placeholder="DDMMYYYY", key="n1_dob_input")
        n1_dob = None
        if n1_dob_str:
            try:
                n1_dob = datetime.strptime(n1_dob_str, "%d%m%Y").date()
            except ValueError:
                st.error("Invalid Date Format. Please use DDMMYYYY (e.g., 25121990)")
        
        n1_tob_str = st.text_input("Time of Birth (HHMM 24hr)", value="", placeholder="HHMM", key="n1_tob_input")
        n1_tob = None
        if n1_tob_str:
            try:
                # Pad with leading zero if 3 digits (e.g., 930 -> 0930)
                if len(n1_tob_str) == 3: n1_tob_str = "0" + n1_tob_str
                n1_tob = datetime.strptime(n1_tob_str, "%H%M").time()
            except ValueError:
                st.error("Invalid Time Format. Please use HHMM (e.g., 1430 for 2:30 PM)")
        
        n1_query = st.text_input("Place of Birth (City)", key="n1_query_input")
        if st.button("Search Places (Boy)", key="n1_search_btn"):
             if n1_query:
                 try:
                     locs = smart_place_search(n1_query)
                     if locs:
                         st.session_state["n1_search_results"] = [(l.address, l.latitude, l.longitude) for l in locs]
                     else:
                         st.error("No places found.")
                         st.session_state["n1_search_results"] = []
                 except Exception as e:
                     st.error(f"Search Error: {e}")
        
        if st.session_state.get("n1_search_results"):
            options = [x[0] for x in st.session_state["n1_search_results"]]
            selected_address = st.selectbox("Select Location", options, key="n1_sel_loc")
            # Find selected
            for addr, lat, lon in st.session_state["n1_search_results"]:
                if addr == selected_address:
                    st.session_state.n1_lat = lat
                    st.session_state.n1_lon = lon
                    # Auto Update TZ
                    tz = get_timezone_from_coords(lat, lon)
                    if tz: st.session_state.n1_tz = tz
                    break
        
        n1_lat = st.number_input("Latitude", format="%.4f", key="n1_lat")
        n1_lon = st.number_input("Longitude", format="%.4f", key="n1_lon")
        
        common_tz_list = sorted(common_timezones)
        tz_options = ["Select Timezone..."] + common_tz_list
        n1_tz = st.selectbox("Timezone", build_tz_options(st.session_state.get('n1_tz')), key="n1_tz")

    with col2:
        st.subheader("Girl (Native 2) Details")
        n2_name = st.text_input("Name", value="", placeholder="Enter name", key="n2_name")
        n2_dob_str = st.text_input("Date of Birth (DDMMYYYY)", value="", placeholder="DDMMYYYY", key="n2_dob_input")
        n2_dob = None
        if n2_dob_str:
            try:
                n2_dob = datetime.strptime(n2_dob_str, "%d%m%Y").date()
            except ValueError:
                st.error("Invalid Date Format. Please use DDMMYYYY (e.g., 25121990)")
                
        n2_tob_str = st.text_input("Time of Birth (HHMM 24hr)", value="", placeholder="HHMM", key="n2_tob_input")
        n2_tob = None
        if n2_tob_str:
            try:
                if len(n2_tob_str) == 3: n2_tob_str = "0" + n2_tob_str
                n2_tob = datetime.strptime(n2_tob_str, "%H%M").time()
            except ValueError:
                st.error("Invalid Time Format. Please use HHMM (e.g., 1430 for 2:30 PM)")
                
        n2_query = st.text_input("Place of Birth (City)", key="n2_query_input")
        if st.button("Search Places (Girl)", key="n2_search_btn"):
             if n2_query:
                 try:
                     locs = smart_place_search(n2_query)
                     if locs:
                         st.session_state["n2_search_results"] = [(l.address, l.latitude, l.longitude) for l in locs]
                     else:
                         st.error("No places found.")
                         st.session_state["n2_search_results"] = []
                 except Exception as e:
                     st.error(f"Search Error: {e}")
        
        if st.session_state.get("n2_search_results"):
            options = [x[0] for x in st.session_state["n2_search_results"]]
            selected_address = st.selectbox("Select Location", options, key="n2_sel_loc")
            # Find selected
            for addr, lat, lon in st.session_state["n2_search_results"]:
                if addr == selected_address:
                    st.session_state.n2_lat = lat
                    st.session_state.n2_lon = lon
                    # Auto Update TZ
                    tz = get_timezone_from_coords(lat, lon)
                    if tz: st.session_state.n2_tz = tz
                    break

        n2_lat = st.number_input("Latitude", format="%.4f", key="n2_lat")
        n2_lon = st.number_input("Longitude", format="%.4f", key="n2_lon")
        
        n2_tz = st.selectbox("Timezone", build_tz_options(st.session_state.get('n2_tz')), key="n2_tz")

    if st.button("Analyze Match & Generate Report", type="primary"):
        try:
            with st.spinner("Analyzing charts..."):
                if n1_tz == "Select Timezone..." or n2_tz == "Select Timezone...":
                    st.error("Please select a timezone for both profiles.")
                    return
                if not n1_dob or not n2_dob:
                    st.error("Please select Date of Birth for both profiles.")
                    return
                if not n1_tob or not n2_tob:
                    st.error("Please select Time of Birth for both profiles.")
                    return
                chart1 = analyze_chart(n1_dob, n1_tob, n1_lat, n1_lon, n1_tz, n1_name)
                chart2 = analyze_chart(n2_dob, n2_tob, n2_lat, n2_lon, n2_tz, n2_name)

                if chart1 and chart2:
                    pdf_buffer = generate_compatibility_report(chart1, chart2, disclaimer, contact_name, contact_mobile)
                    
                    if pdf_buffer:
                        st.success("Report Generated Successfully!")
                        
                        # Display some key results immediately
                        st.markdown("### Match Summary")
                        
                        # Extract some data for display (re-calculating or extracting from report logic would be cleaner, 
                        # but for now let's just show the PDF download)
                        
                        st.download_button(
                            label="Download PDF Report",
                            data=pdf_buffer,
                            file_name=f"Vedic21FoldMatch_{n1_name}_{n2_name}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Failed to generate PDF report.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
            logging.error(f"Analysis Error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
