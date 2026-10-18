# ---------------------------------------------------------------------------
# External service endpoints
# Defaults are for running directly on the host (dev).
# Inside Docker these are overridden via environment variables so the app
# talks to sibling containers by service name on maps_network.
# ---------------------------------------------------------------------------
import os
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPS_BASE_URL  = os.environ.get("OPS_BASE_URL", "http://localhost:5000")
ORS_BASE_URL  = os.environ.get("ORS_BASE_URL", "http://localhost:8082/ors/v2")

# ---------------------------------------------------------------------------
# ORS travel profile identifiers
# ---------------------------------------------------------------------------
ORS_PROFILES = {
    "Walk":   "foot-walking",
    "Cycle":  "cycling-regular",
    "Drive":  "driving-car",
}

# ---------------------------------------------------------------------------
# POI type catalogue  ->  OPS category IDs
# IDs sourced from openpoiservice/server/categories/categories.yml
# Use category_ids for precise filtering, category_group_ids for broad groups.
# ---------------------------------------------------------------------------
POI_TYPES = {
    # --- Accommodation ---
    "Hotel":                    {"category_ids": [108]},
    "Motel":                    {"category_ids": [109]},
    "Hostel":                   {"category_ids": [107]},
    "Guest house":              {"category_ids": [106]},
    "Apartment":                {"category_ids": [102]},
    "Camp site":                {"category_ids": [103]},
    "Caravan site":             {"category_ids": [104]},
    "Chalet":                   {"category_ids": [105]},
    "Alpine hut":               {"category_ids": [101]},
    "Wilderness hut":           {"category_ids": [110]},

    # --- Animals ---
    "Veterinary":               {"category_ids": [123]},
    "Pet shop":                 {"category_ids": [124]},
    "Animal boarding":          {"category_ids": [121]},
    "Animal shelter":           {"category_ids": [122]},

    # --- Arts & Culture ---
    "Library":                  {"category_ids": [133]},
    "Museum":                   {"category_ids": [134]},
    "Gallery":                  {"category_ids": [132]},
    "Arts centre":              {"category_ids": [131]},
    "Place of worship":         {"category_ids": [135]},
    "Studio":                   {"category_ids": [136]},

    # --- Education ---
    "Childcare / Kindergarten": {"category_ids": [153]},
    "Primary / High school":    {"category_ids": [156]},
    "University / College":     {"category_ids": [151, 157]},
    "Driving school":           {"category_ids": [152]},
    "Language school":          {"category_ids": [154]},
    "Music school":             {"category_ids": [155]},

    # --- Facilities ---
    "Toilets":                  {"category_ids": [179]},
    "Drinking water":           {"category_ids": [166]},
    "Internet cafe":            {"category_ids": [169]},
    "Recycling":                {"category_ids": [172]},
    "Shelter":                  {"category_ids": [175]},
    "Bench":                    {"category_ids": [162]},
    "Defibrillator":            {"category_ids": [165]},
    "Post box":                 {"category_ids": [171]},
    "Telephone":                {"category_ids": [178]},
    "Emergency phone":          {"category_ids": [163]},
    "Shower":                   {"category_ids": [176]},
    "Waste basket":             {"category_ids": [180]},
    "Waste disposal":           {"category_ids": [181]},
    "Compressed air":           {"category_ids": [161]},
    "Clock":                    {"category_ids": [164]},
    "Hunting stand":            {"category_ids": [168]},
    "Kneipp water cure":        {"category_ids": [170]},
    "Sanitary dump station":    {"category_ids": [174]},
    "Water point":              {"category_ids": [182]},
    "Fire hydrant":             {"category_ids": [167]},
    "Emergency access point":   {"category_ids": [205]},

    # --- Financial ---
    "ATM / Bank":               {"category_ids": [191, 192]},
    "Bureau de change":         {"category_ids": [193]},

    # --- Healthcare ---
    "Hospital":                 {"category_ids": [206]},
    "GP / Doctor / Clinic":     {"category_ids": [202, 204]},
    "Pharmacy":                 {"category_ids": [208]},
    "Dentist":                  {"category_ids": [203]},
    "Nursing home":             {"category_ids": [207]},
    "Retirement home":          {"category_ids": [209]},
    "Social facility":          {"category_ids": [210]},
    "Baby hatch":               {"category_ids": [201]},
    "Blood donation":           {"category_ids": [211]},
    "Vaccination":              {"category_ids": [212]},

    # --- Historic ---
    "Castle":                   {"category_ids": [224]},
    "Monument":                 {"category_ids": [240]},
    "Memorial":                 {"category_ids": [237]},
    "Ruins":                    {"category_ids": [243]},
    "Archaeological site":      {"category_ids": [223]},
    "Fort":                     {"category_ids": [232]},
    "Battlefield":              {"category_ids": [228]},
    "Aqueduct":                 {"category_ids": [222]},
    "Aircraft (historic)":      {"category_ids": [221]},
    "Cannon":                   {"category_ids": [225]},
    "City gate":                {"category_ids": [226]},
    "City walls":               {"category_ids": [227]},
    "Boundary stone":           {"category_ids": [229]},
    "Historic building":        {"category_ids": [230]},
    "Historic farm":            {"category_ids": [231]},
    "Gallows":                  {"category_ids": [233]},
    "Highwater mark":           {"category_ids": [234]},
    "Locomotive":               {"category_ids": [235]},
    "Manor":                    {"category_ids": [236]},
    "Milestone":                {"category_ids": [238]},
    "Monastery":                {"category_ids": [239]},
    "Optical telegraph":        {"category_ids": [241]},
    "Pillory":                  {"category_ids": [242]},
    "Rune stone":               {"category_ids": [244]},
    "Historic ship":            {"category_ids": [245]},
    "Tomb":                     {"category_ids": [246]},
    "Wayside cross":            {"category_ids": [247]},
    "Wayside shrine":           {"category_ids": [248]},
    "Wreck":                    {"category_ids": [249]},

    # --- Leisure & Entertainment ---
    "Park / Garden":            {"category_ids": [272, 279, 280]},   # garden, nature_reserve, park
    "Gym / Sports centre":      {"category_ids": [271, 288]},        # fitness_centre, sports_centre
    "Swimming pool":            {"category_ids": [292]},
    "Playground":               {"category_ids": [283]},
    "Cinema":                   {"category_ids": [299]},
    "Nightclub":                {"category_ids": [303]},
    "Casino":                   {"category_ids": [298]},
    "Theme park":               {"category_ids": [309]},
    "Zoo":                      {"category_ids": [310]},
    "Aquarium":                 {"category_ids": [308]},
    "Spa":                      {"category_ids": [306]},
    "Golf course":              {"category_ids": [273]},
    "Stadium":                  {"category_ids": [289]},
    "Marina":                   {"category_ids": [277]},
    "Ice rink":                 {"category_ids": [276]},
    "Dog park":                 {"category_ids": [268]},
    "Water park":               {"category_ids": [295]},
    "Horse riding":             {"category_ids": [275]},
    "Dive centre":              {"category_ids": [300]},
    "Sauna":                    {"category_ids": [286]},
    "Public bath":              {"category_ids": [285]},
    "Turkish bath":             {"category_ids": [294]},
    "Fishing (leisure)":        {"category_ids": [270]},
    "Pitch":                    {"category_ids": [282]},
    "Track":                    {"category_ids": [293]},
    "Picnic table":             {"category_ids": [281]},
    "Adult gaming centre":      {"category_ids": [261]},
    "Amusement arcade":         {"category_ids": [262]},
    "Beach resort":             {"category_ids": [263]},
    "Bandstand":                {"category_ids": [264]},
    "Bird hide":                {"category_ids": [265]},
    "Common":                   {"category_ids": [266]},
    "Dance":                    {"category_ids": [267]},
    "Firepit":                  {"category_ids": [269]},
    "Hackerspace":              {"category_ids": [274]},
    "Miniature golf":           {"category_ids": [278]},
    "Slipway":                  {"category_ids": [287]},
    "Summer camp":              {"category_ids": [290]},
    "Swimming area":            {"category_ids": [291]},
    "Wildlife hide":            {"category_ids": [296]},
    "Raceway":                  {"category_ids": [284]},
    "Brothel":                  {"category_ids": [297]},
    "Dojo":                     {"category_ids": [301]},
    "Gambling":                 {"category_ids": [302]},
    "Planetarium":              {"category_ids": [304]},
    "Social centre":            {"category_ids": [305]},
    "Strip club":               {"category_ids": [307]},

    # --- Natural ---
    "Beach":                    {"category_ids": [332]},
    "Mountain peak":            {"category_ids": [335]},
    "Cave entrance":            {"category_ids": [331]},
    "Volcano":                  {"category_ids": [339]},
    "Geyser":                   {"category_ids": [333]},
    "Spring":                   {"category_ids": [338]},
    "Rock":                     {"category_ids": [336]},
    "Saddle":                   {"category_ids": [337]},
    "Water body":               {"category_ids": [340]},

    # --- Public Places ---
    "Police":                   {"category_ids": [369]},
    "Fire station":             {"category_ids": [367]},
    "Townhall":                 {"category_ids": [374]},
    "Courthouse":               {"category_ids": [364]},
    "Embassy":                  {"category_ids": [361]},
    "Post office":              {"category_ids": [370]},
    "Community centre":         {"category_ids": [363]},
    "Coworking space":          {"category_ids": [365]},
    "Prison":                   {"category_ids": [371]},
    "Ranger station":           {"category_ids": [372]},
    "Rescue station":           {"category_ids": [373]},
    "Crematorium":              {"category_ids": [362]},
    "Crypt":                    {"category_ids": [366]},
    "Graveyard":                {"category_ids": [368]},

    # --- Service ---
    "Hairdresser":              {"category_ids": [395]},
    "Beauty salon":             {"category_ids": [391]},
    "Laundry":                  {"category_ids": [396]},
    "Dry cleaning":             {"category_ids": [393]},
    "Estate agent":             {"category_ids": [392]},
    "Massage":                  {"category_ids": [397]},
    "Tailor":                   {"category_ids": [399]},
    "Tattoo":                   {"category_ids": [400]},
    "Glaziery":                 {"category_ids": [394]},
    "Photo booth":              {"category_ids": [398]},

    # --- Shops (Food) ---
    "Supermarket":              {"category_ids": [518]},
    "Grocery / Food store":     {"category_ids": [451, 474, 475]},   # convenience, greengrocer, grocery
    "Shopping centre / Mall":   {"category_ids": [456, 492]},        # department_store, mall
    "Bakery":                   {"category_ids": [426]},
    "Butcher":                  {"category_ids": [434]},
    "Pastry":                   {"category_ids": [506]},
    "Confectionery":            {"category_ids": [450]},
    "Chocolate":                {"category_ids": [444]},
    "Cheese":                   {"category_ids": [442]},
    "Dairy":                    {"category_ids": [454]},
    "Deli":                     {"category_ids": [455]},
    "Seafood":                  {"category_ids": [511]},
    "Wine shop":                {"category_ids": [533]},
    "Alcohol shop":             {"category_ids": [422]},
    "Beverages":                {"category_ids": [428]},
    "Coffee shop":              {"category_ids": [448]},
    "Tea shop":                 {"category_ids": [520]},
    "Spices":                   {"category_ids": [515]},
    "Organic":                  {"category_ids": [503]},
    "Farm shop":                {"category_ids": [462]},
    "Marketplace":              {"category_ids": [493]},

    # --- Shops (Other) ---
    "Bookshop":                 {"category_ids": [430]},
    "Newsagent":                {"category_ids": [501]},
    "Stationery":               {"category_ids": [517]},
    "Clothes":                  {"category_ids": [447]},
    "Boutique":                 {"category_ids": [431]},
    "Fashion":                  {"category_ids": [463]},
    "Shoes":                    {"category_ids": [514]},
    "Bag shop":                 {"category_ids": [425]},
    "Jewelry":                  {"category_ids": [485]},
    "Watches":                  {"category_ids": [531]},
    "Leather":                  {"category_ids": [486]},
    "Cosmetics":                {"category_ids": [453]},
    "Perfumery":                {"category_ids": [507]},
    "Chemist":                  {"category_ids": [443]},
    "Optician":                 {"category_ids": [502]},
    "Hearing aids":             {"category_ids": [479]},
    "Medical supply":           {"category_ids": [494]},
    "Herbalist":                {"category_ids": [480]},
    "Nutrition supplements":    {"category_ids": [500]},
    "Florist":                  {"category_ids": [465]},
    "Garden centre":            {"category_ids": [469]},
    "Garden furniture":         {"category_ids": [470]},
    "Hardware":                 {"category_ids": [478]},
    "DIY":                      {"category_ids": [457]},
    "Paint":                    {"category_ids": [505]},
    "Tiles":                    {"category_ids": [522]},
    "Electrical":               {"category_ids": [458]},
    "Electronics":              {"category_ids": [459]},
    "Computer":                 {"category_ids": [449]},
    "Mobile phone":             {"category_ids": [495]},
    "Camera":                   {"category_ids": [436]},
    "Photo":                    {"category_ids": [508]},
    "Hifi":                     {"category_ids": [481]},
    "Music":                    {"category_ids": [498]},
    "Musical instrument":       {"category_ids": [499]},
    "Video":                    {"category_ids": [529]},
    "Video games":              {"category_ids": [530]},
    "Games":                    {"category_ids": [468]},
    "Toys":                     {"category_ids": [524]},
    "Sports shop":              {"category_ids": [516]},
    "Outdoor":                  {"category_ids": [504]},
    "Bicycle shop":             {"category_ids": [429]},
    "Hunting shop":             {"category_ids": [483]},
    "Fishing shop":             {"category_ids": [464]},
    "Weapons":                  {"category_ids": [532]},
    "Furniture":                {"category_ids": [467]},
    "Bed":                      {"category_ids": [427]},
    "Carpet":                   {"category_ids": [440]},
    "Curtain":                  {"category_ids": [441]},
    "Houseware":                {"category_ids": [482]},
    "Kitchen":                  {"category_ids": [489]},
    "Lamps":                    {"category_ids": [490]},
    "Interior decoration":      {"category_ids": [476]},
    "Antiques":                 {"category_ids": [423]},
    "Art shop":                 {"category_ids": [424]},
    "Candles":                  {"category_ids": [437]},
    "Gift shop":                {"category_ids": [473]},
    "Variety store":            {"category_ids": [527]},
    "Second hand":              {"category_ids": [512]},
    "Kiosk":                    {"category_ids": [488]},
    "Lottery":                  {"category_ids": [491]},
    "Tobacco":                  {"category_ids": [523]},
    "E-cigarette":              {"category_ids": [461]},
    "Erotic":                   {"category_ids": [460]},
    "Trophy":                   {"category_ids": [525]},
    "Funeral directors":        {"category_ids": [466]},
    "Locksmith":                {"category_ids": [487]},
    "Copyshop":                 {"category_ids": [452]},
    "Insurance":                {"category_ids": [484]},
    "Travel agency":            {"category_ids": [626]},
    "Ticket":                   {"category_ids": [521]},
    "Hairdresser supply":       {"category_ids": [477]},
    "Brewing supplies":         {"category_ids": [432]},
    "Business machines":        {"category_ids": [433]},
    "Agrarian":                 {"category_ids": [421]},
    "General store":            {"category_ids": [472]},
    "Gas shop":                 {"category_ids": [471]},
    "Pyrotechnics":             {"category_ids": [509]},
    "Radiotechnics":            {"category_ids": [510]},
    "Security shop":            {"category_ids": [513]},
    "Swimming pool shop":       {"category_ids": [519]},
    "Model shop":               {"category_ids": [496]},
    "Car shop":                 {"category_ids": [438]},
    "Car parts":                {"category_ids": [439]},
    "Tyres":                    {"category_ids": [526]},
    "Motorcycle shop":          {"category_ids": [497]},
    "Vending machine":          {"category_ids": [528]},

    # --- Sustenance ---
    "Restaurant":               {"category_ids": [570]},
    "Cafe":                     {"category_ids": [564]},
    "Fast food":                {"category_ids": [566]},
    "Pub / Bar":                {"category_ids": [561, 569]},
    "Biergarten":               {"category_ids": [563]},
    "Food court":               {"category_ids": [567]},
    "Ice cream":                {"category_ids": [568]},
    "BBQ":                      {"category_ids": [562]},

    # --- Transport ---
    "Train station":            {"category_ids": [604]},
    "Tram stop":                {"category_ids": [605]},
    "Bus stop / Station":       {"category_ids": [587, 588]},
    "Train halt":               {"category_ids": [597]},
    "Public transport stop":    {"category_ids": [607, 608, 609, 610]},
    "Airport":                  {"category_ids": [581]},
    "Helipad":                  {"category_ids": [598]},
    "Heliport":                 {"category_ids": [599]},
    "Ferry terminal":           {"category_ids": [595]},
    "Petrol station":           {"category_ids": [596]},
    "EV charging":              {"category_ids": [593, 594]},
    "Taxi":                     {"category_ids": [606]},
    "Car rental":               {"category_ids": [589]},
    "Car repair":               {"category_ids": [590]},
    "Car sharing":              {"category_ids": [591]},
    "Car wash":                 {"category_ids": [592]},
    "Bicycle parking":          {"category_ids": [583]},
    "Bicycle rental":           {"category_ids": [584]},
    "Bicycle repair station":   {"category_ids": [585]},
    "Boat sharing":             {"category_ids": [586]},
    "Motorcycle parking":       {"category_ids": [600]},
    "Parking":                  {"category_ids": [601, 602, 603]},

    # --- Tourism ---
    "Tourist attraction":       {"category_ids": [622]},
    "Viewpoint":                {"category_ids": [627]},
    "Artwork":                  {"category_ids": [621]},
    "Fountain":                 {"category_ids": [623]},
    "Tourist information":      {"category_ids": [624]},
    "Picnic site":              {"category_ids": [625]},
}

# ---------------------------------------------------------------------------
# Display colours — one per criterion, cycles if > 10 criteria added
# ---------------------------------------------------------------------------
CRITERION_COLORS = [
    "#3498DB",  # blue
    "#2ECC71",  # green
    "#E74C3C",  # red
    "#9B59B6",  # purple
    "#F39C12",  # orange
    "#1ABC9C",  # teal
    "#E91E63",  # pink
    "#795548",  # brown
    "#607D8B",  # steel blue
    "#FF5722",  # deep orange
]

INTERSECTION_COLOR        = "#1A1A2E"   # near-black for the "live here" zones
INTERSECTION_FILL_OPACITY = 0.55

# ---------------------------------------------------------------------------
# Computation limits
# ---------------------------------------------------------------------------
MAX_POIS_PER_CRITERION = 2000   # OPS result cap per criterion (server response_limit is 2000)
ORS_BATCH_SIZE         = 10   # locations per ORS isochrone POST request (matches maximum_locations)
