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
    
    if d1_sign_index in [0, 3, 6, 9]: start_sign = 0
    elif d1_sign_index in [1, 4, 7, 10]: start_sign = 9
    else: start_sign = 6
        
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
    planet_sign_index = int(planet_lon / 30)
    planet_owner = SIGN_LORD_MAP.get(planet_sign_index)
    star_lord_lookup = star_lord_name
    if star_lord_name in ["Rahu", "Ketu"]:
        node_sign_lon = chart_planets.get(star_lord_name)
        if node_sign_lon is not None:
            star_lord_sign_index = int(node_sign_lon / 30)
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
                sign_index = int(cusp_lon / 30)
                sign_lord = SIGN_LORD_MAP.get(sign_index)
                if sign_lord == star_lord_lookup:
                    s1_s2_significators.add(i + 1)
    planet_house = find_house_index(planet_lon, all_cusps)
    if planet_house > 0:
        s3_s4_significators.add(planet_house)
    for i in range(0, 12):
        cusp_lon = all_cusps[i]
        sign_index = int(cusp_lon / 30)
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
    
    def get_varna(rasi_index):
        if rasi_index in [2, 5, 6, 9]: return 0
        if rasi_index in [0, 4, 7, 10]: return 1
        return 2
    if get_varna(moon_rasi_index_c1) <= get_varna(moon_rasi_index_c2): total_score += 1
    
    def get_vashya(rasi_index):
        if rasi_index in [0, 1]: return 0
        if rasi_index in [2, 5, 6]: return 1
        if rasi_index in [3]: return 2
        if rasi_index in [4]: return 3
        return 4
    v1, v2 = get_vashya(moon_rasi_index_c1), get_vashya(moon_rasi_index_c2)
    if v1 == v2: total_score += 2
    elif (v1==0 and v2==3) or (v1==3 and v2==0): total_score += 0
    else: total_score += 1
    
    dist = (nak_index_c2 - nak_index_c1 + 27) % 27
    dist2 = (nak_index_c1 - nak_index_c2 + 27) % 27
    t_score = 0
    if (dist + 1) % 9 not in [3, 5, 7]: t_score += 1.5
    if (dist2 + 1) % 9 not in [3, 5, 7]: t_score += 1.5
    total_score += t_score
    
    def get_yoni(nak_index):
        yoni_map = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 14, 14: 1, 15: 2, 16: 3, 17: 4, 18: 5, 19: 6, 20: 7, 21: 8, 22: 9, 23: 10, 24: 11, 25: 12, 26: 13}
        return yoni_map.get(nak_index, 0)
    y1, y2 = get_yoni(nak_index_c1), get_yoni(nak_index_c2)
    if y1 == y2: total_score += 4
    elif (y1 + y2) % 2 == 0: total_score += 3
    
    rasi_lord_map = {0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon", 4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars", 8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"}
    l1, l2 = rasi_lord_map.get(moon_rasi_index_c1), rasi_lord_map.get(moon_rasi_index_c2)
    
    def get_graha_maitri(lord1, lord2):
        if lord1 == lord2: return 5
        friendly_pairs = [("Sun", "Moon"), ("Sun", "Mars"), ("Sun", "Jupiter"), ("Moon", "Mars"), ("Moon", "Jupiter"),
                         ("Mars", "Jupiter"), ("Mars", "Sun"), ("Mercury", "Venus"), ("Mercury", "Saturn"),
                         ("Jupiter", "Sun"), ("Jupiter", "Moon"), ("Jupiter", "Mars"), ("Jupiter", "Saturn"),
                         ("Venus", "Mercury"), ("Venus", "Saturn"), ("Saturn", "Mercury"), ("Saturn", "Jupiter"), ("Saturn", "Venus")]
        if (lord1, lord2) in friendly_pairs and (lord2, lord1) in friendly_pairs: return 5
        if (lord1, lord2) in friendly_pairs or (lord2, lord1) in friendly_pairs: return 4
        if lord1 in ["Sun", "Moon"] and lord2 in ["Saturn", "Venus"]: return 0
        return 1
    total_score += get_graha_maitri(l1, l2)
    
    def get_gana(nak_index):
        if nak_index in [0, 4, 6, 7, 12, 14, 16, 21, 26]: return 0 
        if nak_index in [1, 3, 5, 10, 11, 19, 20, 24, 25]: return 1 
        return 2 
    g1, g2 = get_gana(nak_index_c1), get_gana(nak_index_c2)
    if g1 == g2: total_score += 6
    elif (g1==0 and g2==1) or (g1==1 and g2==0): total_score += 5
    elif (g1==1 and g2==2) or (g1==2 and g2==1): total_score += 1
    
    d_bhakoot = (moon_rasi_index_c2 - moon_rasi_index_c1 + 12) % 12
    if d_bhakoot not in [2, 10, 5, 9, 6, 8]: total_score += 7
    
    if (nak_index_c1 % 3) != (nak_index_c2 % 3): total_score += 8
    
    return min(max(round(total_score), 0), 36)

def calculate_supplementary_factors(chart1_data, chart2_data):
    def check_affliction(sigs, houses):
        return any(h in sigs for h in houses)

    results = {}
    
    c1_dosha = chart1_data["mars_dosha_status"]["Total"] == "Afflicted"
    c2_dosha = chart2_data["mars_dosha_status"]["Total"] == "Afflicted"

    if c1_dosha == c2_dosha:
        results['Kuja_Dosha_Parity'] = "Matched (Dosha Parity)"
    elif c1_dosha and not c2_dosha:
        results['Kuja_Dosha_Parity'] = f"Unmatched (Dosha in {chart1_data['name']})"
    elif c2_dosha and not c1_dosha:
        results['Kuja_Dosha_Parity'] = f"Unmatched (Dosha in {chart2_data['name']})"
    else:
        results['Kuja_Dosha_Parity'] = "Clean" 

    c1_ayur_risk = check_affliction(chart1_data["csl_significators"], [8, 12])
    c2_ayur_risk = check_affliction(chart2_data["csl_significators"], [8, 12])
    results['Ayurvriddhi_Match'] = "Poor (Shared Risk)" if c1_ayur_risk and c2_ayur_risk else "Good"
    results['Vaidhavya_Risk'] = "High" if c1_ayur_risk and c2_ayur_risk else "Low"
    results['Pitra_Dosha_Match'] = "Present in Both" if chart1_data["pitra_dosha_present"] and chart2_data["pitra_dosha_present"] else "Mixed"
    c1_prog_promise = check_affliction(chart1_data["csl_significators"], [5, 11])
    c2_prog_promise = check_affliction(chart2_data["csl_significators"], [5, 11])
    results['Progeny_Match'] = "Strong" if c1_prog_promise and c2_prog_promise else "Weak/Mixed"
    c1_dhana = check_affliction(chart1_data["csl_significators"], [2, 11])
    c2_dhana = check_affliction(chart2_data["csl_significators"], [2, 11])
    results['Financial_Match'] = "Strong" if c1_dhana and c2_dhana else "Average"
    c1_karaka = check_affliction(chart1_data["jupiter_significators"], [7, 11])
    c2_karaka = check_affliction(chart2_data["venus_significators"], [7, 11])
    results['Karaka_Compatibility'] = "High" if c1_karaka and c2_karaka else "Moderate"
    c1_7th_lord_ok = not check_affliction(chart1_data["csl_significators"], [6, 8, 12])
    c2_7th_lord_ok = not check_affliction(chart2_data["csl_significators"], [6, 8, 12])
    results['7th_Lord_Strength'] = "Good" if c1_7th_lord_ok and c2_7th_lord_ok else "Weak/Afflicted"
    c1_sat_8th = 8 in chart1_data["saturn_significators"]
    c2_sat_8th = 8 in chart2_data["saturn_significators"]
    results['Ashtama_Shani_Effect'] = "High Risk (Natal)" if c1_sat_8th or c2_sat_8th else "Low Risk"
    results['Dasha_Synchronization'] = "Favorable" if chart1_data["marriage_promise"] != "DENIAL" and chart2_data["marriage_promise"] != "DENIAL" else "Unfavorable"
    results['Rasi_Navamsa_Match'] = f"Moon Rasi Lords: {chart1_data['rasi_lord']} vs {chart2_data['rasi_lord']}"
    c1_lagna_lord = SIGN_LORD_MAP.get(int(chart1_data["cusps"][0] / 30) % 12)
    c2_lagna_lord = SIGN_LORD_MAP.get(int(chart2_data["cusps"][0] / 30) % 12)
    results['Lagna_Lord_Friendship'] = f"Lords are {c1_lagna_lord} & {c2_lagna_lord}"
    
    results['D9_Lagna_Lord_Friendship'] = check_parashari_friendship(
        chart1_data["d9_lagna_lord"], chart2_data["d9_lagna_lord"]
    )

    return results

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
    if mars_sign_index in [4, 8, 11]: return True, "Cancelled (Benefic Sign D1)"

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

        result = se.houses(jd, latitude, longitude, b"P")
        cusps = list(result[0])[0:12]
        
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
        d9_lagna_lord = SIGN_LORD_MAP[int(d9_lagna_lon / 30)]
        
        # D50 Calculation (Full)
        d50_planets = {}
        for p_name, p_lon in planets.items():
             if p_name == "Lagna":
                 d50_planets["Lagna"] = get_d50_longitude(cusps[0])
             else:
                 d50_planets[p_name] = get_d50_longitude(p_lon)
        
        d50_lagna_lon = d50_planets["Lagna"]
        d50_lagna_lord = SIGN_LORD_MAP[int(d50_lagna_lon / 30)]
        
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
        if (9 in get_significators(planets["Rahu"], cusps, planets) or 
            9 in get_significators(planets["Ketu"], cusps, planets) or 
            rahu_house == 9 or sun_house == 9):
            pitra_dosha_present = True

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

        d1_7th_lord_name = SIGN_LORD_MAP[int(cusps[6] / 30)]
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

    supplementary_results = calculate_supplementary_factors(chart1["analysis_data"], chart2["analysis_data"])
    guna_score = calculate_ashtakoota(chart1["analysis_data"], chart2["analysis_data"])

    # Dasha & CSL Logic
    c1_11_link = 11 in chart1["csl_significators"]
    c2_11_link = 11 in chart2["csl_significators"]
    c1_family_link = any(h in chart1["csl_significators"] for h in [2, 5])
    c2_family_link = any(h in chart2["csl_significators"] for h in [2, 5])
    c1_affliction = any(h in chart1["csl_significators"] for h in [8, 12])
    c2_affliction = any(h in chart2["csl_significators"] for h in [8, 12])

    c1_md_lord = chart1["md_lord"]
    c1_ad_lord = chart1["ad_lord"]
    c1_pd_lord = chart1["pd_lord"]
    c1_md_sigs = chart1["planet_significators"].get(c1_md_lord, [])
    c1_ad_sigs = chart1["planet_significators"].get(c1_ad_lord, [])
    c1_pd_sigs = chart1["planet_significators"].get(c1_pd_lord, [])
    c2_md_lord = chart2["md_lord"]
    c2_ad_lord = chart2["ad_lord"]
    c2_pd_lord = chart2["pd_lord"]
    c2_md_sigs = chart2["planet_significators"].get(c2_md_lord, [])
    c2_ad_sigs = chart2["planet_significators"].get(c2_ad_lord, [])
    c2_pd_sigs = chart2["planet_significators"].get(c2_pd_lord, [])
    c1_md_status = check_dasha_marriage_potential(c1_md_sigs)
    c1_ad_status = check_dasha_marriage_potential(c1_ad_sigs)
    c1_pd_status = check_dasha_marriage_potential(c1_pd_sigs)
    c2_md_status = check_dasha_marriage_potential(c2_md_sigs)
    c2_ad_status = check_dasha_marriage_potential(c2_ad_sigs)
    c2_pd_status = check_dasha_marriage_potential(c2_pd_sigs)
    c1_marriage_support = (c1_ad_status == "STRONG_PROMISE" or c1_pd_status == "STRONG_PROMISE")
    c2_marriage_support = (c2_ad_status == "STRONG_PROMISE" or c2_pd_status == "STRONG_PROMISE")
    c1_denial_active = (c1_ad_status == "DENIAL_PERIOD" or c1_pd_status == "DENIAL_PERIOD")
    c2_denial_active = (c2_ad_status == "DENIAL_PERIOD" or c2_pd_status == "DENIAL_PERIOD")
    natal_dosha_denial = (chart1["mars_dosha_status"]["Total"] == "Afflicted" and 
                          chart2["mars_dosha_status"]["Total"] == "Afflicted" and
                          supplementary_results['Kuja_Dosha_Parity'] != "Matched (Dosha Parity)")
    if c1_denial_active or c2_denial_active:
        dasha_verdict = "DENIAL: Current Dasha period strongly signifies denial houses (1, 6, 10)."
    elif natal_dosha_denial and not (c1_marriage_support and c2_marriage_support):
         dasha_verdict = "DENIAL: Severe natal affliction (unmatched Dosha) blocks marriage."
    elif c1_marriage_support and c2_marriage_support:
        dasha_verdict = "STRONGLY SUPPORTIVE: Dasha periods support marriage in both charts."
    elif c1_marriage_support or c2_marriage_support:
         dasha_verdict = "MIXED: Dasha supports marriage for only one native."
    else:
        dasha_verdict = "WEAK/NEUTRAL: Current Dasha relies heavily on natal promise."
    supplementary_results['Dasha_Synchronization'] = dasha_verdict

    styles = getSampleStyleSheet()
    story = []
    table_style_data = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ])

    story.append(Paragraph("KP and Vedic Match-Making Compatibility Report (D1-D9-D50)", styles["h1"]))
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
        ["7th Cusp Sub-Lord", chart1["7th_csl"], chart2["7th_csl"]],
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


    story.append(Paragraph("3. Planetary Positional Analysis (Rasi-Star-Sub)", styles["h2"]))
    position_header = ["Graha", "Rasi Lord", "Star Lord", "Sub Lord", "Longitude", "Nakshatra", "Pada"]
    c1_position_data = [position_header] + chart1["kp_positions"]
    story.append(Paragraph(f"Native 1 ({chart1['name']}) Positions:", styles["h3"]))
    c1_pos_table = Table(c1_position_data, colWidths=[60, 80, 80, 80, 120, 100, 60])
    c1_pos_table.setStyle(table_style_data)
    story.append(c1_pos_table)
    story.append(Spacer(1, 12))
    c2_position_data = [position_header] + chart2["kp_positions"]
    story.append(Paragraph(f"Native 2 ({chart2['name']}) Positions:", styles["h3"]))
    c2_pos_table = Table(c2_position_data, colWidths=[60, 80, 80, 80, 120, 100, 60])
    c2_pos_table.setStyle(table_style_data)
    story.append(c2_pos_table)
    story.append(Spacer(1, 24))

    story.append(Paragraph("4. Major Dosha Analysis", styles["h2"]))
    dosha_data = [
        ["Dosha Check", chart1["name"], chart2["name"], "Severity"],
        ["Kuja Dosha", chart1["mars_dosha_status"]["Total"], chart2["mars_dosha_status"]["Total"], "Affliction from 3 points is severe."],
        ["Pitra Dosha", "Present" if chart1["pitra_dosha_present"] else "Clean", "Present" if chart2["pitra_dosha_present"] else "Clean", "Indicates issues with destiny/ancestral blessings."],
        ["Rahu/Ketu Affliction", chart1["rahu_dosha_status"]["Total"], chart2["rahu_dosha_status"]["Total"], "Indicates unpredictable challenges."],
    ]
    story.append(Table(dosha_data, colWidths=[160, 130, 130, 90], style=table_style_data))
    story.append(Spacer(1, 12))
    fav_data = [
        ["Graha", "Jupiter", "Saturn", "Venus", "Sun"],
        [f"Fav/Unfav (KP Sigs) - {chart1['name']}", chart1["planet_favorability"]["Jupiter"], chart1["planet_favorability"]["Saturn"], chart1["planet_favorability"]["Venus"], chart1["planet_favorability"]["Sun"]],
        [f"Fav/Unfav (KP Sigs) - {chart2['name']}", chart2["planet_favorability"]["Jupiter"], chart2["planet_favorability"]["Saturn"], chart2["planet_favorability"]["Venus"], chart2["planet_favorability"]["Sun"]],
    ]
    story.append(Paragraph("Planetary Strength & Favorability (KP Significators)", styles["h3"]))
    story.append(Table(fav_data, colWidths=[130, 90, 90, 90, 90], style=table_style_data))
    story.append(Spacer(1, 18))
    
    story.append(Paragraph("5. Vedic Guna Milan & Dasha Synchronization", styles["h2"]))
    promise_data = [
        ["Factor", chart1["name"], chart2["name"], "Verdict/Score"],
        ["KP Promise (2, 7, 11)", chart1["marriage_promise"], chart2["marriage_promise"], "Should be STRONG in both."],
        ["CSL Sigs", str(chart1["csl_significators"]), str(chart2["csl_significators"]), "KP House Links"],
        ["Vedic Guna Milan (36)", f"{guna_score} / 36", f"{guna_score} / 36", "36 max. 18+ is usually acceptable."],
    ]
    story.append(Table(promise_data, colWidths=[130, 90, 90, 190], style=table_style_data))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph(f"Current Vimsottari Dasha Period ({datetime.now().strftime('%Y-%m-%d')}) Match:", styles["h3"]))
    dasha_table_data = [
        ["Dasha Lord", f"Native 1 ({chart1['name']})", f"Native 2 ({chart2['name']})", "Status (N1)", "Status (N2)"],
        ["Maha Dasha (MD)", chart1["md_lord"], chart2["md_lord"], c1_md_status, c2_md_status],
        ["Antardasha (AD)", chart1["ad_lord"], chart2["ad_lord"], c1_ad_status, c2_ad_status],
        ["Pratyantardasha (PD)", chart1["pd_lord"], chart2["pd_lord"], c1_pd_status, c2_pd_status],
    ]
    dasha_table = Table(dasha_table_data, colWidths=[110, 85, 85, 110, 110])
    dasha_table.setStyle(table_style_data)
    story.append(dasha_table) 
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Dasha Synchronization Verdict: {dasha_verdict}", styles["Normal"]))

    story.append(PageBreak())
    story.append(Paragraph("6. Supplementary Factors Summary", styles["h2"]))
    
    twenty_one_data = [
        ["Factor", chart1['name'] + " Status", chart2['name'] + " Status", "Compatibility Verdict"],
        ["Kuja Dosha Parity", chart1["mars_dosha_status"]["Total"], chart2["mars_dosha_status"]["Total"], supplementary_results['Kuja_Dosha_Parity']],
        ["Ayurvriddhi (Longevity)", "Good" if not any(h in chart1["csl_significators"] for h in [8, 12]) else "Risk", "Good" if not any(h in chart2["csl_significators"] for h in [8, 12]) else "Risk", supplementary_results['Ayurvriddhi_Match']],
        ["Vaidhavya Dosha", supplementary_results['Vaidhavya_Risk'], supplementary_results['Vaidhavya_Risk'], supplementary_results['Vaidhavya_Risk']],
        ["Pitra Dosha Match", "Present" if chart1["pitra_dosha_present"] else "Clean", "Present" if chart2["pitra_dosha_present"] else "Clean", supplementary_results['Pitra_Dosha_Match']],
        ["Santana (Progeny)", "Promising" if any(h in chart1["csl_significators"] for h in [2, 5, 11]) else "Weak", "Promising" if any(h in chart2["csl_significators"] for h in [2, 5, 11]) else "Weak", supplementary_results['Progeny_Match']],
        ["Financial Match", "Strong" if any(h in chart1["csl_significators"] for h in [2, 11]) else "Average", "Strong" if any(h in chart2["csl_significators"] for h in [2, 11]) else "Average", supplementary_results['Financial_Match']],
        ["Karaka Graha", supplementary_results['Karaka_Compatibility'], supplementary_results['Karaka_Compatibility'], supplementary_results['Karaka_Compatibility']],
        ["7th Lord Strength", supplementary_results['7th_Lord_Strength'], supplementary_results['7th_Lord_Strength'], supplementary_results['7th_Lord_Strength']],
        ["Ashtama Shani", "8th Link" if 8 in chart1["saturn_significators"] else "Clean", "8th Link" if 8 in chart2["saturn_significators"] else "Clean", supplementary_results['Ashtama_Shani_Effect']],
        ["Rasi Lord Match", chart1["rasi_lord"], chart2["rasi_lord"], supplementary_results['Rasi_Navamsa_Match']],
        ["Ascendant Lord Friendship", SIGN_LORD_MAP.get(int(chart1["kp_positions"][0][4].split()[0].split('°')[0]) // 30), SIGN_LORD_MAP.get(int(chart2["kp_positions"][0][4].split()[0].split('°')[0]) // 30), supplementary_results['Lagna_Lord_Friendship']],
        ["D9 Lagna Lord Friendship", chart1["analysis_data"]["d9_lagna_lord"], chart2["analysis_data"]["d9_lagna_lord"], supplementary_results['D9_Lagna_Lord_Friendship']],
    ]
    story.append(Table(twenty_one_data, colWidths=[150, 100, 100, 160], style=table_style_data))
    
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
        lord1 = SIGN_LORD_MAP[int(s1_lon / 30)]
        lord2 = SIGN_LORD_MAP[int(s2_lon / 30)]
        
        # Get Bhava
        lagna1 = chart_dict1.get("Lagna", 0)
        bhava1 = find_house_from_lagna(s1_lon, lagna1)
        lagna2 = chart_dict2.get("Lagna", 0)
        bhava2 = find_house_from_lagna(s2_lon, lagna2)
        
        friendship = check_parashari_friendship(lord1, lord2)
        
        display1 = f"{sign1} ({lord1}) [{bhava1}H]"
        display2 = f"{sign2} ({lord2}) [{bhava2}H]"
        
        return [planet_key, display1, display2, friendship]

    def build_match_table(title, dict1, dict2):
        story.append(PageBreak())
        story.append(Paragraph(title, styles["h2"]))
        story.append(Spacer(1, 6))
        
        # Visual Charts for this section
        c1_data = get_south_chart_data(dict1, f"{chart1['name']}\n{title.split()[2]}")
        c2_data = get_south_chart_data(dict2, f"{chart2['name']}\n{title.split()[2]}")
        t1 = Table(c1_data, colWidths=[40,40,40,40], rowHeights=[40,40,40,40])
        t1.setStyle(chart_style)
        t2 = Table(c2_data, colWidths=[40,40,40,40], rowHeights=[40,40,40,40])
        t2.setStyle(chart_style)
        story.append(Table([[t1, Spacer(20, 20), t2]]))
        story.append(Spacer(1, 12))

        header = ["Planet", f"{chart1['name']} Sign [Bhava]", f"{chart2['name']} Sign [Bhava]", "Lords Friendship"]
        rows = [header]
        friendly_count = 0
        total_checked = 0
        
        planets_to_check = ["Lagna", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
        
        if title.startswith("7."): 
            d1_dict1 = dict1.copy(); d1_dict1["Lagna"] = chart1["analysis_data"]["cusps"][0]
            d1_dict2 = dict2.copy(); d1_dict2["Lagna"] = chart2["analysis_data"]["cusps"][0]
            final_d1 = d1_dict1
            final_d2 = d1_dict2
        else:
            final_d1 = dict1
            final_d2 = dict2

        for p in planets_to_check:
            row = get_chart_match_row(p, final_d1, final_d2)
            if row:
                rows.append(row)
                if "Friend" in row[3]: friendly_count += 1
                total_checked += 1
        
        t = Table(rows, colWidths=[60, 160, 160, 120], style=table_style_data)
        story.append(t)
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Compatibility Score: {friendly_count} / {total_checked} Friendly Pairs", styles["h3"]))
        return friendly_count

    # 7. D1 Match
    d1_score = build_match_table("7. Full D1 (Rasi) Match", chart1["analysis_data"]["planets"], chart2["analysis_data"]["planets"])
    
    # 8. D9 Match
    d9_score = build_match_table("8. Full D9 (Navamsa) Match", chart1["analysis_data"]["d9_planets"], chart2["analysis_data"]["d9_planets"])
    
    # 9. D50 Match
    d50_score = build_match_table("9. Full D50 (50th Harmonic) Match", chart1["analysis_data"]["d50_planets"], chart2["analysis_data"]["d50_planets"])
    
    story.append(Spacer(1, 24))
    
    # --- Section 10: Final Verdict ---
    story.append(Paragraph("10. FINAL MATCH VERDICT", styles["h1"]))
    story.append(Spacer(1, 12))

    c1_promise = chart1['marriage_promise']
    c2_promise = chart2['marriage_promise']
    kp_promise_status = "Good"
    if c1_promise == "DENIAL" or c2_promise == "DENIAL": kp_promise_status = "DENIAL"
    elif c1_promise == "STRONG" and c2_promise == "STRONG": kp_promise_status = "Strong"
    elif c1_promise == "MIXED" and c2_promise == "MIXED": kp_promise_status = "Mixed"
    else: kp_promise_status = "Average"

    kp_dasha_status = "Good"
    if dasha_verdict.startswith("DENIAL"): kp_dasha_status = "DENIAL"
    elif dasha_verdict.startswith("STRONGLY SUPPORTIVE"): kp_dasha_status = "Strong"
    elif dasha_verdict in ["MIXED", "WEAK/NEUTRAL"]: kp_dasha_status = "Mixed"

    good_factors = 0
    supp_results = supplementary_results
    
    if "Unmatched" not in supp_results['Kuja_Dosha_Parity']: good_factors += 1
    if supp_results['Ayurvriddhi_Match'] == "Good": good_factors += 1
    if supp_results['Vaidhavya_Risk'] == "Low": good_factors += 1
    if supp_results['Pitra_Dosha_Match'] != "Present in Both": good_factors += 1
    if supp_results['Progeny_Match'] == "Strong": good_factors += 1
    if supp_results['Financial_Match'] == "Strong": good_factors += 1
    if supp_results['Karaka_Compatibility'] == "High": good_factors += 1
    if supp_results['7th_Lord_Strength'] == "Good": good_factors += 1
    if supp_results['Ashtama_Shani_Effect'] == "Low Risk": good_factors += 1
    
    # Add Chart Scores to Factors
    if d1_score >= 5: good_factors += 1
    if d9_score >= 5: good_factors += 1
    if d50_score >= 5: good_factors += 1
        
    total_factors_checked = 12 
    fold_summary_status = "Average"
    if good_factors >= 9: fold_summary_status = "Strong"
    elif good_factors < 6: fold_summary_status = "Weak"
    fold_summary_text = f"{fold_summary_status} ({good_factors}/{total_factors_checked} favorable)"

    final_verdict_text = "PROCEED"
    reasons_to_fail = []
    verdict_notes = []

    if kp_promise_status == "DENIAL": reasons_to_fail.append("Natal KP promise shows DENIAL.")
    if kp_dasha_status == "DENIAL": reasons_to_fail.append("Current Dasha indicates strong DENIAL.")
    if guna_score < 18: reasons_to_fail.append(f"Guna Milan ({guna_score}/36) below 18.")
    if fold_summary_status == "Weak": reasons_to_fail.append(f"Supplementary Match is Weak.")

    if reasons_to_fail:
        final_verdict_text = "TRY ANOTHER MATCH"
        verdict_notes = reasons_to_fail
    else:
        reasons_for_caution = []
        if kp_promise_status != "Strong": reasons_for_caution.append(f"Natal Promise is {kp_promise_status}.")
        if kp_dasha_status != "Strong": reasons_for_caution.append(f"Dasha Timing is {kp_dasha_status}.")
        if fold_summary_status != "Strong": reasons_for_caution.append(f"Supplementary Match is {fold_summary_text}.")
        
        if reasons_for_caution:
            final_verdict_text = "PROCEED (With Caution)"
            verdict_notes = reasons_for_caution
        else:
            final_verdict_text = "PROCEED (Strongly Recommended)"
            verdict_notes.append("All major parameters (KP, D9, D50, Dasha, Guna) are favorable.")
    
    verdict_summary_data = [
        ["Parameter", "Status", "Notes"],
        ["KP Natal Promise", kp_promise_status, f"{c1_promise} (N1) / {c2_promise} (N2)"],
        ["KP Dasha Timing", kp_dasha_status, dasha_verdict.split(':')[0]],
        ["Vedic Guna Milan", f"{guna_score}/36", "Good" if guna_score >= 18 else "FAIL"],
        ["D1 Match (Sign/Bhava)", f"{d1_score}/10", "Friendly Sign Lords"],
        ["D9 Match (Sign/Bhava)", f"{d9_score}/10", "Friendly Sign Lords"],
        ["D50 Match (Sign/Bhava)", f"{d50_score}/10", "Friendly Sign Lords"],
        ["Supplementary", fold_summary_text, f"Combined Score"],
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

def build_tz_options(current_tz):
    base = ["Select Timezone..."] + sorted(common_timezones)
    if current_tz and current_tz not in base:
        base.insert(1, current_tz)
    return base

def main():
    st.set_page_config(page_title="KP Astrology Match-Making", layout="wide")
    st.title("KP Astrology Match-Making Software")

    # Initialize session state for widgets to avoid default-value conflicts
    if "n1_lat" not in st.session_state: st.session_state["n1_lat"] = 0.0
    if "n1_lon" not in st.session_state: st.session_state["n1_lon"] = 0.0
    if "n2_lat" not in st.session_state: st.session_state["n2_lat"] = 0.0
    if "n2_lon" not in st.session_state: st.session_state["n2_lon"] = 0.0
    if "n1_tz" not in st.session_state: st.session_state["n1_tz"] = "Select Timezone..."
    if "n2_tz" not in st.session_state: st.session_state["n2_tz"] = "Select Timezone..."
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
        n1_dob = st.date_input("Date of Birth", value=None, min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="n1_dob")
        n1_tob = st.time_input("Time of Birth", value=None, step=60, key="n1_tob")
        n1_pob_choice = st.selectbox("Place of Birth", PLACE_CHOICES, key="n1_pob_choice")
        n1_pob = n1_pob_choice if n1_pob_choice != "Other (enter manually)" else st.text_input("Place of Birth (City, Country)", value="", placeholder="City, Country", key="n1_pob")
        
        if st.button("Fetch Coordinates (Boy)", key="n1_fetch"):
            lat, lon = fetch_lat_lon(n1_pob)
            if lat is not None:
                st.session_state.n1_lat = lat
                st.session_state.n1_lon = lon
                tzname = get_timezone_from_coords(lat, lon)
                if tzname:
                    st.session_state.n1_tz = tzname
                    st.success(f"Found: {lat:.4f}, {lon:.4f} | Timezone: {tzname}")
                else:
                    st.success(f"Found: {lat:.4f}, {lon:.4f}")
            else:
                st.error("Could not find coordinates.")
        
        n1_lat = st.number_input("Latitude", format="%.4f", key="n1_lat")
        n1_lon = st.number_input("Longitude", format="%.4f", key="n1_lon")
        
        common_tz_list = sorted(common_timezones)
        tz_options = ["Select Timezone..."] + common_tz_list
        n1_tz = st.selectbox("Timezone", build_tz_options(st.session_state.get('n1_tz')), key="n1_tz")

    with col2:
        st.subheader("Girl (Native 2) Details")
        n2_name = st.text_input("Name", value="", placeholder="Enter name", key="n2_name")
        n2_dob = st.date_input("Date of Birth", value=None, min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="n2_dob")
        n2_tob = st.time_input("Time of Birth", value=None, step=60, key="n2_tob")
        n2_pob_choice = st.selectbox("Place of Birth", PLACE_CHOICES, key="n2_pob_choice")
        n2_pob = n2_pob_choice if n2_pob_choice != "Other (enter manually)" else st.text_input("Place of Birth (City, Country)", value="", placeholder="City, Country", key="n2_pob")

        if st.button("Fetch Coordinates (Girl)", key="n2_fetch"):
            lat, lon = fetch_lat_lon(n2_pob)
            if lat is not None:
                st.session_state.n2_lat = lat
                st.session_state.n2_lon = lon
                tzname = get_timezone_from_coords(lat, lon)
                if tzname:
                    st.session_state.n2_tz = tzname
                    st.success(f"Found: {lat:.4f}, {lon:.4f} | Timezone: {tzname}")
                else:
                    st.success(f"Found: {lat:.4f}, {lon:.4f}")
            else:
                st.error("Could not find coordinates.")

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
                            file_name=f"KPMatch_{n1_name}_{n2_name}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Failed to generate PDF report.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
            logging.error(f"Analysis Error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
