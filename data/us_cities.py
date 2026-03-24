"""
US cities organized by state, with state abbreviations.
Covers major population centers for all 50 states.
"""

STATE_ABBREVS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

US_CITIES = {
    "Alabama": [
        "Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa",
        "Hoover", "Dothan", "Auburn", "Decatur", "Madison",
    ],
    "Alaska": [
        "Anchorage", "Fairbanks", "Juneau", "Sitka", "Ketchikan",
        "Wasilla", "Kenai", "Kodiak", "Bethel", "Palmer",
    ],
    "Arizona": [
        "Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale",
        "Glendale", "Gilbert", "Tempe", "Peoria", "Surprise",
        "Yuma", "Avondale", "Flagstaff", "Goodyear", "Lake Havasu City",
    ],
    "Arkansas": [
        "Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro",
        "North Little Rock", "Conway", "Rogers", "Pine Bluff", "Bentonville",
    ],
    "California": [
        "Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno",
        "Sacramento", "Long Beach", "Oakland", "Bakersfield", "Anaheim",
        "Santa Ana", "Riverside", "Stockton", "Irvine", "Chula Vista",
        "Fremont", "San Bernardino", "Modesto", "Fontana", "Oxnard",
        # Bay Area — Peninsula & South Bay
        "Palo Alto", "Los Altos", "Mountain View", "Sunnyvale", "Cupertino",
        "Los Gatos", "Saratoga", "Campbell", "Menlo Park", "Redwood City",
        "San Mateo", "Burlingame", "San Carlos", "Belmont", "East Palo Alto",
        "Atherton", "Foster City", "Millbrae", "San Bruno", "South San Francisco",
        # Bay Area — East & North Bay
        "Daly City", "Hayward", "Concord", "Antioch", "Richmond",
        "Berkeley", "Walnut Creek", "Pleasanton", "Livermore", "San Ramon",
        "Union City", "Newark", "Alameda", "El Cerrito", "Novato",
        "San Rafael", "Petaluma", "Santa Rosa", "Napa", "Vallejo",
        "Fairfield", "Vacaville",
        # Central Valley & Coast
        "Davis", "Woodland", "Chico", "Redding", "Roseville", "Elk Grove",
        "Folsom", "Rocklin", "Turlock", "Merced", "Visalia", "Hanford",
        "Santa Cruz", "Capitola", "Scotts Valley", "Monterey", "Salinas",
        "San Luis Obispo", "Paso Robles", "Santa Maria",
        # Southern California extras
        "Santa Barbara", "Ventura", "Thousand Oaks", "Simi Valley",
        "Glendale", "Pasadena", "Torrance", "Santa Monica", "Beverly Hills",
        "Burbank", "El Monte", "Pomona", "Rancho Cucamonga", "Victorville",
        "Garden Grove", "Fullerton", "Orange", "Tustin", "Mission Viejo",
        "Lake Forest", "El Cajon", "Escondido", "Oceanside", "Carlsbad",
        "Vista", "San Marcos", "Murrieta", "Temecula",
    ],
    "Colorado": [
        "Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood",
        "Thornton", "Arvada", "Westminster", "Pueblo", "Boulder",
        "Highlands Ranch", "Greeley", "Longmont", "Loveland", "Grand Junction",
    ],
    "Connecticut": [
        "Bridgeport", "New Haven", "Stamford", "Hartford", "Waterbury",
        "Norwalk", "Danbury", "New Britain", "West Hartford", "Greenwich",
    ],
    "Delaware": [
        "Wilmington", "Dover", "Newark", "Middletown", "Smyrna",
        "Milford", "Seaford", "Georgetown", "Elsmere", "New Castle",
    ],
    "Florida": [
        "Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg",
        "Hialeah", "Port St. Lucie", "Cape Coral", "Tallahassee", "Fort Lauderdale",
        "Pembroke Pines", "Hollywood", "Miramar", "Gainesville", "Coral Springs",
        "Palm Bay", "West Palm Beach", "Clearwater", "Lakeland", "Pompano Beach",
        "Boca Raton", "Davie", "Miami Gardens", "Deerfield Beach", "Deltona",
        "Palm Coast", "Plantation", "Sunrise", "Lauderhill", "Homestead",
        "Kissimmee", "Sanford", "Ocala", "Daytona Beach", "Melbourne",
        "Sarasota", "Bradenton", "Fort Myers", "Naples", "Bonita Springs",
        "Pensacola", "Panama City", "Tallahassee", "St. Cloud", "Apopka",
    ],
    "Georgia": [
        "Atlanta", "Columbus", "Augusta", "Macon", "Savannah",
        "Athens", "Sandy Springs", "Roswell", "Albany", "Johns Creek",
        "Warner Robins", "Alpharetta", "Marietta", "Valdosta", "Smyrna",
    ],
    "Hawaii": [
        "Honolulu", "Hilo", "Kailua", "Pearl City", "Waipahu",
        "Kaneohe", "Mililani Town", "Kahului", "Ewa Gentry", "Kihei",
    ],
    "Idaho": [
        "Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello",
        "Caldwell", "Coeur d'Alene", "Twin Falls", "Lewiston", "Post Falls",
    ],
    "Illinois": [
        "Chicago", "Aurora", "Joliet", "Rockford", "Springfield",
        "Elgin", "Peoria", "Champaign", "Waukegan", "Cicero",
        "Bloomington", "Naperville", "Evanston", "Decatur", "Bolingbrook",
    ],
    "Indiana": [
        "Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel",
        "Fishers", "Bloomington", "Hammond", "Gary", "Muncie",
        "Lafayette", "Terre Haute", "Kokomo", "Anderson", "Noblesville",
    ],
    "Iowa": [
        "Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City",
        "Waterloo", "Council Bluffs", "Ames", "West Des Moines", "Dubuque",
    ],
    "Kansas": [
        "Wichita", "Overland Park", "Kansas City", "Olathe", "Topeka",
        "Lawrence", "Shawnee", "Manhattan", "Lenexa", "Salina",
    ],
    "Kentucky": [
        "Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington",
        "Hopkinsville", "Richmond", "Florence", "Georgetown", "Henderson",
    ],
    "Louisiana": [
        "New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles",
        "Kenner", "Bossier City", "Monroe", "Alexandria", "Houma",
    ],
    "Maine": [
        "Portland", "Lewiston", "Bangor", "South Portland", "Auburn",
        "Biddeford", "Sanford", "Augusta", "Saco", "Westbrook",
    ],
    "Maryland": [
        "Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie",
        "Hagerstown", "Annapolis", "College Park", "Salisbury", "Laurel",
    ],
    "Massachusetts": [
        "Boston", "Worcester", "Springfield", "Lowell", "Cambridge",
        "New Bedford", "Brockton", "Quincy", "Lynn", "Fall River",
        "Newton", "Somerville", "Lawrence", "Framingham", "Haverhill",
    ],
    "Michigan": [
        "Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor",
        "Lansing", "Flint", "Dearborn", "Livonia", "Westland",
        "Troy", "Farmington Hills", "Kalamazoo", "Wyoming", "Southfield",
    ],
    "Minnesota": [
        "Minneapolis", "Saint Paul", "Rochester", "Duluth", "Bloomington",
        "Brooklyn Park", "Plymouth", "Saint Cloud", "Eagan", "Woodbury",
        "Maple Grove", "Coon Rapids", "Burnsville", "Blaine", "Lakeville",
    ],
    "Mississippi": [
        "Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi",
        "Meridian", "Tupelo", "Olive Branch", "Horn Lake", "Pearl",
    ],
    "Missouri": [
        "Kansas City", "Saint Louis", "Springfield", "Columbia", "Independence",
        "Lee's Summit", "O'Fallon", "Saint Joseph", "Saint Charles", "Blue Springs",
    ],
    "Montana": [
        "Billings", "Missoula", "Great Falls", "Bozeman", "Butte",
        "Helena", "Kalispell", "Havre", "Anaconda", "Miles City",
    ],
    "Nebraska": [
        "Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney",
        "Fremont", "Hastings", "North Platte", "Norfolk", "Columbus",
    ],
    "Nevada": [
        "Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks",
        "Carson City", "Fernley", "Elko", "Mesquite", "Boulder City",
    ],
    "New Hampshire": [
        "Manchester", "Nashua", "Concord", "Derry", "Dover",
        "Rochester", "Salem", "Merrimack", "Hudson", "Londonderry",
    ],
    "New Jersey": [
        "Newark", "Jersey City", "Paterson", "Elizabeth", "Edison",
        "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Trenton",
        "Clifton", "Camden", "Brick", "Cherry Hill", "Passaic",
    ],
    "New Mexico": [
        "Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell",
        "Farmington", "Clovis", "Hobbs", "Alamogordo", "Carlsbad",
    ],
    "New York": [
        "New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse",
        "Albany", "New Rochelle", "Mount Vernon", "Schenectady", "Utica",
        "White Plains", "Hempstead", "Troy", "Niagara Falls", "Binghamton",
        "Brooklyn", "Queens", "Bronx", "Staten Island", "Manhattan",
        "Long Island City", "Flushing", "Jamaica", "Astoria", "Harlem",
        "Ithaca", "Poughkeepsie", "Newburgh", "Middletown", "Kingston",
        "Saratoga Springs", "Plattsburgh", "Watertown", "Rome", "Oswego",
    ],
    "North Carolina": [
        "Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem",
        "Fayetteville", "Cary", "Wilmington", "High Point", "Concord",
        "Asheville", "Gastonia", "Chapel Hill", "Greenville", "Rocky Mount",
    ],
    "North Dakota": [
        "Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo",
        "Williston", "Dickinson", "Mandan", "Jamestown", "Wahpeton",
    ],
    "Ohio": [
        "Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron",
        "Dayton", "Parma", "Canton", "Youngstown", "Lorain",
        "Hamilton", "Springfield", "Kettering", "Elyria", "Lakewood",
    ],
    "Oklahoma": [
        "Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Lawton",
        "Edmond", "Moore", "Midwest City", "Enid", "Stillwater",
    ],
    "Oregon": [
        "Portland", "Salem", "Eugene", "Gresham", "Hillsboro",
        "Beaverton", "Bend", "Medford", "Springfield", "Corvallis",
    ],
    "Pennsylvania": [
        "Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading",
        "Scranton", "Bethlehem", "Lancaster", "Harrisburg", "York",
        "Altoona", "Wilkes-Barre", "Chester", "Norristown", "State College",
    ],
    "Rhode Island": [
        "Providence", "Cranston", "Warwick", "Pawtucket", "East Providence",
        "Woonsocket", "Coventry", "Cumberland", "North Providence", "West Warwick",
    ],
    "South Carolina": [
        "Columbia", "Charleston", "North Charleston", "Mount Pleasant", "Rock Hill",
        "Greenville", "Summerville", "Sumter", "Goose Creek", "Hilton Head Island",
    ],
    "South Dakota": [
        "Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown",
        "Mitchell", "Yankton", "Pierre", "Huron", "Vermillion",
    ],
    "Tennessee": [
        "Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville",
        "Murfreesboro", "Franklin", "Jackson", "Johnson City", "Bartlett",
        "Hendersonville", "Kingsport", "Collierville", "Smyrna", "Cleveland",
    ],
    "Texas": [
        "Houston", "San Antonio", "Dallas", "Austin", "Fort Worth",
        "El Paso", "Arlington", "Corpus Christi", "Plano", "Laredo",
        "Lubbock", "Garland", "Irving", "Amarillo", "Grand Prairie",
        "Brownsville", "McKinney", "Frisco", "Pasadena", "Mesquite",
        "Carrollton", "Killeen", "Midland", "Waco", "Denton",
        "Abilene", "Beaumont", "Round Rock", "Sugar Land", "League City",
        "Richardson", "Wichita Falls", "Tyler", "College Station", "Allen",
        "Pearland", "Odessa", "Lewisville", "San Angelo", "Edinburg",
        "Flower Mound", "Longview", "McAllen", "Cedar Park", "Georgetown",
        "Baytown", "North Richland Hills", "Mission", "Harlingen", "Rowlett",
    ],
    "Utah": [
        "Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem",
        "Sandy", "Ogden", "St. George", "Layton", "Millcreek",
    ],
    "Vermont": [
        "Burlington", "South Burlington", "Rutland", "Essex Junction", "Barre",
        "Montpelier", "Winooski", "St. Albans", "Newport", "Vergennes",
    ],
    "Virginia": [
        "Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News",
        "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk",
        "Lynchburg", "Harrisonburg", "Charlottesville", "Danville", "Manassas",
    ],
    "Washington": [
        "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue",
        "Kent", "Everett", "Renton", "Kirkland", "Bellingham",
        "Kennewick", "Federal Way", "Yakima", "Redmond", "Marysville",
    ],
    "West Virginia": [
        "Charleston", "Huntington", "Parkersburg", "Morgantown", "Wheeling",
        "Weirton", "Fairmont", "Martinsburg", "Beckley", "Clarksburg",
    ],
    "Wisconsin": [
        "Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine",
        "Appleton", "Waukesha", "Oshkosh", "Eau Claire", "Janesville",
        "West Allis", "La Crosse", "Sheboygan", "Wauwatosa", "Fond du Lac",
    ],
    "Wyoming": [
        "Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs",
        "Sheridan", "Green River", "Evanston", "Riverton", "Jackson",
    ],
}


def get_states():
    return sorted(US_CITIES.keys())


def get_cities(state):
    return sorted(US_CITIES.get(state, []))


def get_state_abbrev(state):
    return STATE_ABBREVS.get(state, "")
