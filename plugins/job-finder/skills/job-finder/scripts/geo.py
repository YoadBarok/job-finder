"""Major cities -> country, so a location like "Berlin" or "Budapest" is understood (lowercase keys)."""
CITY_COUNTRY = {
    # EU / EEA / Europe
    "vienna": "austria", "graz": "austria", "linz": "austria", "brussels": "belgium", "antwerp": "belgium", "ghent": "belgium",
    "sofia": "bulgaria", "plovdiv": "bulgaria", "zagreb": "croatia", "split": "croatia", "nicosia": "cyprus", "limassol": "cyprus",
    "prague": "czechia", "praha": "czechia", "brno": "czechia", "ostrava": "czechia", "copenhagen": "denmark", "aarhus": "denmark",
    "tallinn": "estonia", "tartu": "estonia", "helsinki": "finland", "espoo": "finland", "tampere": "finland",
    "paris": "france", "lyon": "france", "marseille": "france", "toulouse": "france", "nantes": "france", "bordeaux": "france", "lille": "france", "nice": "france",
    "berlin": "germany", "munich": "germany", "münchen": "germany", "hamburg": "germany", "frankfurt": "germany", "cologne": "germany",
    "köln": "germany", "stuttgart": "germany", "düsseldorf": "germany", "dusseldorf": "germany", "leipzig": "germany", "dresden": "germany",
    "hannover": "germany", "nuremberg": "germany", "nürnberg": "germany", "karlsruhe": "germany", "bonn": "germany",
    "athens": "greece", "thessaloniki": "greece", "budapest": "hungary", "debrecen": "hungary", "dublin": "ireland", "cork": "ireland", "galway": "ireland",
    "rome": "italy", "milan": "italy", "milano": "italy", "turin": "italy", "torino": "italy", "bologna": "italy", "florence": "italy", "naples": "italy",
    "riga": "latvia", "vilnius": "lithuania", "kaunas": "lithuania", "luxembourg city": "luxembourg", "valletta": "malta",
    "amsterdam": "netherlands", "rotterdam": "netherlands", "utrecht": "netherlands", "the hague": "netherlands", "eindhoven": "netherlands",
    "warsaw": "poland", "krakow": "poland", "kraków": "poland", "wroclaw": "poland", "wrocław": "poland", "gdansk": "poland", "gdańsk": "poland",
    "poznan": "poland", "poznań": "poland", "lodz": "poland", "łódź": "poland", "katowice": "poland",
    "lisbon": "portugal", "lisboa": "portugal", "porto": "portugal", "braga": "portugal", "bucharest": "romania", "cluj-napoca": "romania", "cluj": "romania", "iasi": "romania",
    "bratislava": "slovakia", "kosice": "slovakia", "ljubljana": "slovenia", "madrid": "spain", "barcelona": "spain", "valencia": "spain",
    "seville": "spain", "malaga": "spain", "málaga": "spain", "bilbao": "spain", "stockholm": "sweden", "gothenburg": "sweden", "malmö": "sweden", "malmo": "sweden",
    "oslo": "norway", "bergen": "norway", "reykjavik": "iceland", "zurich": "switzerland", "zürich": "switzerland", "geneva": "switzerland",
    "basel": "switzerland", "lausanne": "switzerland", "bern": "switzerland",
    "london": "united kingdom", "manchester": "united kingdom", "edinburgh": "united kingdom", "glasgow": "united kingdom", "bristol": "united kingdom",
    "cambridge, uk": "united kingdom", "oxford": "united kingdom", "leeds": "united kingdom", "birmingham, uk": "united kingdom", "belfast": "united kingdom",
    "kyiv": "ukraine", "kiev": "ukraine", "lviv": "ukraine", "belgrade": "serbia", "novi sad": "serbia", "sarajevo": "bosnia", "skopje": "north macedonia",
    "tirana": "albania", "chisinau": "moldova", "istanbul": "turkey", "ankara": "turkey",
    # Middle East / Africa
    "tel aviv": "israel", "tel aviv-yafo": "israel", "jerusalem": "israel", "haifa": "israel", "herzliya": "israel", "ramat gan": "israel", "petah tikva": "israel",
    "dubai": "united arab emirates", "abu dhabi": "united arab emirates", "riyadh": "saudi arabia", "cairo": "egypt",
    "lagos": "nigeria", "nairobi": "kenya", "cape town": "south africa", "johannesburg": "south africa",
    # Americas
    "new york": "united states", "nyc": "united states", "san francisco": "united states", "seattle": "united states", "austin": "united states",
    "boston": "united states", "chicago": "united states", "los angeles": "united states", "denver": "united states", "atlanta": "united states",
    "miami": "united states", "washington, dc": "united states", "san diego": "united states", "portland": "united states", "dallas": "united states",
    "toronto": "canada", "vancouver": "canada", "montreal": "canada", "ottawa": "canada", "calgary": "canada",
    "mexico city": "mexico", "são paulo": "brazil", "sao paulo": "brazil", "rio de janeiro": "brazil", "buenos aires": "argentina",
    "bogotá": "colombia", "bogota": "colombia", "medellín": "colombia", "medellin": "colombia", "santiago": "chile", "lima": "peru",
    # Asia-Pacific
    "bangalore": "india", "bengaluru": "india", "mumbai": "india", "delhi": "india", "new delhi": "india", "hyderabad": "india", "pune": "india", "chennai": "india",
    "singapore": "singapore", "tokyo": "japan", "seoul": "south korea", "hong kong": "hong kong", "taipei": "taiwan", "manila": "philippines",
    "sydney": "australia", "melbourne": "australia", "brisbane": "australia", "auckland": "new zealand",
}


def country_of(place: str) -> str | None:
    p = place.lower().strip()
    if p in CITY_COUNTRY:
        return CITY_COUNTRY[p]
    for city, country in CITY_COUNTRY.items():
        if p.startswith(city + " ") or p.endswith(" " + city):
            return country
    return None
