"""
knowledge.py - static reference data for the Trader Dashboard.

Everything that is *data about the market* (universes, sector maps, names,
macro-event rules) lives here so the engine / UI files stay clean.
"""

# ------------------------------------------------------------------------------
# Indices & sectors (kept from the original app)
# ------------------------------------------------------------------------------
SEC = {
    "Bank": "^NSEBANK", "IT": "^CNXIT", "Auto": "^CNXAUTO", "Pharma": "^CNXPHARMA",
    "FMCG": "^CNXFMCG", "Metal": "^CNXMETAL", "Energy": "^CNXENERGY", "Realty": "^CNXREALTY",
    "Media": "^CNXMEDIA", "Infra": "^CNXINFRA", "PSE": "^CNXPSE",
}
IX = {"^NSEI": "Nifty 50", "^BSESN": "Sensex", "^NSEBANK": "Bank Nifty", "^INDIAVIX": "India VIX"}
IDX = {
    **{k.upper(): v for k, v in SEC.items()},
    **{"NIFTY " + k.upper(): v for k, v in SEC.items()},
    "NIFTY": "^NSEI", "NIFTY 50": "^NSEI", "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK", "BANK NIFTY": "^NSEBANK", "NIFTYBANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT", "INDIA VIX": "^INDIAVIX", "VIX": "^INDIAVIX",
}
BENCH = "^NSEI"
INDEX_NAMES = {**{v: f"Nifty {k}" for k, v in SEC.items()}, **IX}

# ------------------------------------------------------------------------------
# Stock universes (original categories kept, each one widened so that 6-8 BUY and
# 6-8 SELL setups can actually be found in every category / style).
# Symbols that fail to download are skipped automatically.
# ------------------------------------------------------------------------------
UNI = {
    "Largecap": (
        "RELIANCE TCS HDFCBANK INFY ICICIBANK SBIN BHARTIARTL ITC LT HINDUNILVR AXISBANK MARUTI "
        "SUNPHARMA ULTRACEMCO KOTAKBANK BAJFINANCE BAJAJFINSV ASIANPAINT TITAN NESTLEIND HCLTECH "
        "WIPRO TECHM NTPC POWERGRID ONGC COALINDIA TATASTEEL JSWSTEEL ADANIENT ADANIPORTS M&M "
        "BRITANNIA CIPLA DRREDDY EICHERMOT GRASIM HEROMOTOCO HINDALCO INDUSINDBK APOLLOHOSP "
        "DIVISLAB BPCL TATACONSUM SBILIFE HDFCLIFE BAJAJ-AUTO SHRIRAMFIN TRENT LTIM"
    ),
    "Midcap": (
        "PERSISTENT POLYCAB COFORGE MPHASIS LUPIN AUROPHARMA FEDERALBNK GODREJPROP BHARATFORG "
        "CUMMINSIND VOLTAS ASTRAL IDFCFIRSTB AUBANK MAXHEALTH OBEROIRLTY PRESTIGE INDHOTEL JUBLFOOD "
        "PIIND DIXON KPITTECH TATAELXSI SUPREMEIND ASHOKLEY TVSMOTOR BALKRISIND MRF SAIL NMDC "
        "JINDALSTEL RECLTD PFC HAL BEL IRCTC ZYDUSLIFE ALKEM TORNTPHARM COLPAL MARICO DABUR "
        "GODREJCP PAGEIND CROMPTON HAVELLS SRF UPL TATACOMM"
    ),
    "Smallcap": (
        "CDSL CAMS ANGELONE RADICO KARURVYSYA NATCOPHARM ZENSARTECH SONATSOFTW KFINTECH CASTROLIND "
        "IEX MCX REDINGTON RBLBANK CANFINHOME GRANULES LAURUSLABS AARTIIND DEEPAKNTR NAVINFLUOR "
        "TATACHEM CHAMBLFERT JKCEMENT RAMCOCEM KEC NBCC RVNL IRCON HUDCO SJVN NHPC COCHINSHIP "
        "MAZDOCK CYIENT BSOFT"
    ),
    "F&O": (
        "TATASTEEL JSWSTEEL HINDALCO ONGC NTPC POWERGRID COALINDIA BAJFINANCE ADANIPORTS DLF "
        "INDUSINDBK WIPRO GRASIM VEDL SAIL BANKBARODA PNB CANBK IDFCFIRSTB TATAPOWER GAIL IOC BPCL "
        "HINDPETRO BHEL BEL HAL TVSMOTOR ASHOKLEY INDIGO LICHSGFIN RECLTD PFC MUTHOOTFIN CHOLAFIN "
        "LTIM NAUKRI PIDILITIND HAVELLS GODREJPROP AMBUJACEM"
    ),
    "Banks & Finance": (
        "HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK BAJFINANCE BAJAJFINSV PNB BANKBARODA CHOLAFIN "
        "HDFCLIFE SBILIFE CANBK UNIONBANK INDUSINDBK FEDERALBNK IDFCFIRSTB AUBANK BANDHANBNK "
        "MUTHOOTFIN SHRIRAMFIN LICHSGFIN RECLTD PFC ICICIPRULI ICICIGI SBICARD MANAPPURAM"
    ),
    "IT & Pharma": (
        "TCS INFY WIPRO HCLTECH TECHM LTIM SUNPHARMA CIPLA DRREDDY DIVISLAB LUPIN PERSISTENT COFORGE "
        "MPHASIS LTTS OFSS KPITTECH TATAELXSI AUROPHARMA ZYDUSLIFE TORNTPHARM ALKEM GLENMARK BIOCON "
        "MANKIND APOLLOHOSP MAXHEALTH"
    ),
    "Auto & Metals": (
        "MARUTI M&M TMPV TATAMOTORS BHARATFORG TATASTEEL JSWSTEEL HINDALCO VEDL JINDALSTEL EICHERMOT "
        "HEROMOTOCO BAJAJ-AUTO TVSMOTOR ASHOKLEY MOTHERSON BOSCHLTD BALKRISIND MRF APOLLOTYRE SAIL "
        "NMDC NATIONALUM JSL"
    ),
}

# Sector -> constituents used by the FII / DII sector radar.
SECTOR_STOCKS = {
    "Financial Services": "HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK BAJFINANCE BAJAJFINSV SHRIRAMFIN PNB BANKBARODA",
    "Information Technology": "TCS INFY HCLTECH WIPRO TECHM LTIM PERSISTENT COFORGE MPHASIS",
    "Healthcare & Pharma": "SUNPHARMA DRREDDY CIPLA DIVISLAB LUPIN APOLLOHOSP TORNTPHARM ZYDUSLIFE",
    "Automobile & Auto Components": "MARUTI M&M EICHERMOT BAJAJ-AUTO HEROMOTOCO TVSMOTOR BHARATFORG MOTHERSON",
    "Oil, Gas & Energy": "RELIANCE ONGC BPCL IOC GAIL COALINDIA",
    "FMCG": "HINDUNILVR ITC NESTLEIND BRITANNIA DABUR TATACONSUM GODREJCP MARICO",
    "Metals & Mining": "TATASTEEL JSWSTEEL HINDALCO VEDL JINDALSTEL SAIL NMDC",
    "Telecommunication": "BHARTIARTL INDUSTOWER TATACOMM",
    "Capital Goods & Infra": "LT SIEMENS ABB BHEL HAL BEL CUMMINSIND POLYCAB",
    "Power & Utilities": "NTPC POWERGRID TATAPOWER NHPC ADANIPOWER JSWENERGY",
    "Construction Materials": "ULTRACEMCO GRASIM AMBUJACEM SHREECEM JKCEMENT",
    "Realty": "DLF GODREJPROP OBEROIRLTY PRESTIGE LODHA",
    "Consumer Durables & Retail": "TITAN ASIANPAINT TRENT HAVELLS VOLTAS DIXON PAGEIND",
    "Chemicals": "PIDILITIND SRF UPL PIIND DEEPAKNTR",
    "Services (Ports, Aviation)": "ADANIPORTS INDIGO IRCTC",
}
SECTOR_STOCKS = {k: v.split() for k, v in SECTOR_STOCKS.items()}

# NSDL fortnightly sector names -> our sector keys (substring match, first hit wins)
NSDL_SECTOR_MAP = [
    ("financial", "Financial Services"), ("information tech", "Information Technology"),
    ("health", "Healthcare & Pharma"), ("auto", "Automobile & Auto Components"),
    ("oil", "Oil, Gas & Energy"), ("fast moving", "FMCG"), ("fmcg", "FMCG"),
    ("metals", "Metals & Mining"), ("telecom", "Telecommunication"),
    ("capital goods", "Capital Goods & Infra"), ("construction materials", "Construction Materials"),
    ("construction", "Capital Goods & Infra"), ("power", "Power & Utilities"),
    ("realty", "Realty"), ("consumer durables", "Consumer Durables & Retail"),
    ("consumer services", "Consumer Durables & Retail"), ("chemicals", "Chemicals"),
    ("services", "Services (Ports, Aviation)"),
]

# Keywords people use (English / Hinglish) -> sector key. Used by chat + news.
SECTOR_KEYWORDS = {
    "Financial Services": ["bank", "banking", "finance", "financial", "nbfc", "banks"],
    "Information Technology": ["it ", " it", "tech", "software", "technology", "it sector"],
    "Healthcare & Pharma": ["pharma", "healthcare", "health", "hospital", "drug"],
    "Automobile & Auto Components": ["auto", "automobile", "car", "vehicle", "ev "],
    "Oil, Gas & Energy": ["oil", "gas", "energy", "crude", "petroleum"],
    "FMCG": ["fmcg", "consumer goods", "staples"],
    "Metals & Mining": ["metal", "steel", "mining", "aluminium", "copper"],
    "Telecommunication": ["telecom", "5g", "telco"],
    "Capital Goods & Infra": ["infra", "capital goods", "defence", "railway", "capex", "engineering"],
    "Power & Utilities": ["power", "utility", "utilities", "renewable", "solar"],
    "Construction Materials": ["cement", "construction material"],
    "Realty": ["realty", "real estate", "property", "housing"],
    "Consumer Durables & Retail": ["durable", "retail", "consumer"],
    "Chemicals": ["chemical", "specialty chem"],
    "Services (Ports, Aviation)": ["aviation", "airline", "port", "logistics"],
}

STOCK_NAMES = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services", "HDFCBANK": "HDFC Bank",
    "INFY": "Infosys", "ICICIBANK": "ICICI Bank", "SBIN": "State Bank of India",
    "BHARTIARTL": "Bharti Airtel", "ITC": "ITC Limited", "LT": "Larsen & Toubro",
    "HINDUNILVR": "Hindustan Unilever", "AXISBANK": "Axis Bank", "MARUTI": "Maruti Suzuki",
    "SUNPHARMA": "Sun Pharmaceutical", "ULTRACEMCO": "UltraTech Cement", "KOTAKBANK": "Kotak Mahindra Bank",
    "JSWSTEEL": "JSW Steel", "TATASTEEL": "Tata Steel", "TECHM": "Tech Mahindra",
    "GRASIM": "Grasim Industries", "DRREDDY": "Dr. Reddy's Laboratories", "TRENT": "Trent Limited",
    "WIPRO": "Wipro", "SBILIFE": "SBI Life Insurance", "HDFCLIFE": "HDFC Life Insurance",
    "TMPV": "Tata Motors Passenger Vehicles", "NESTLEIND": "Nestle India", "ADANIPORTS": "Adani Ports & SEZ",
    "BAJAJFINSV": "Bajaj Finserv", "ONGC": "Oil & Natural Gas Corp", "M&M": "Mahindra & Mahindra",
    "POWERGRID": "Power Grid Corp", "NTPC": "NTPC Limited", "BAJFINANCE": "Bajaj Finance",
    "COALINDIA": "Coal India", "DLF": "DLF Limited", "CIPLA": "Cipla", "DIVISLAB": "Divi's Laboratories",
    "ASIANPAINT": "Asian Paints", "TITAN": "Titan Company", "HCLTECH": "HCL Technologies",
    "ADANIENT": "Adani Enterprises", "BRITANNIA": "Britannia Industries", "EICHERMOT": "Eicher Motors",
    "HEROMOTOCO": "Hero MotoCorp", "HINDALCO": "Hindalco Industries", "INDUSINDBK": "IndusInd Bank",
    "APOLLOHOSP": "Apollo Hospitals", "BPCL": "Bharat Petroleum", "TATACONSUM": "Tata Consumer Products",
    "BAJAJ-AUTO": "Bajaj Auto", "SHRIRAMFIN": "Shriram Finance", "LTIM": "LTIMindtree",
    "PERSISTENT": "Persistent Systems", "POLYCAB": "Polycab India", "COFORGE": "Coforge",
    "MPHASIS": "Mphasis", "LUPIN": "Lupin", "AUROPHARMA": "Aurobindo Pharma", "FEDERALBNK": "Federal Bank",
    "GODREJPROP": "Godrej Properties", "BHARATFORG": "Bharat Forge", "CUMMINSIND": "Cummins India",
    "VOLTAS": "Voltas", "ASTRAL": "Astral Limited", "IDFCFIRSTB": "IDFC First Bank", "AUBANK": "AU Small Finance Bank",
    "MAXHEALTH": "Max Healthcare", "OBEROIRLTY": "Oberoi Realty", "PRESTIGE": "Prestige Estates",
    "INDHOTEL": "Indian Hotels", "JUBLFOOD": "Jubilant FoodWorks", "PIIND": "PI Industries",
    "DIXON": "Dixon Technologies", "KPITTECH": "KPIT Technologies", "TATAELXSI": "Tata Elxsi",
    "SUPREMEIND": "Supreme Industries", "ASHOKLEY": "Ashok Leyland", "TVSMOTOR": "TVS Motor",
    "BALKRISIND": "Balkrishna Industries", "MRF": "MRF Limited", "SAIL": "Steel Authority of India",
    "NMDC": "NMDC Limited", "JINDALSTEL": "Jindal Steel & Power", "RECLTD": "REC Limited",
    "PFC": "Power Finance Corp", "HAL": "Hindustan Aeronautics", "BEL": "Bharat Electronics",
    "IRCTC": "IRCTC", "ZYDUSLIFE": "Zydus Lifesciences", "ALKEM": "Alkem Laboratories",
    "TORNTPHARM": "Torrent Pharma", "COLPAL": "Colgate-Palmolive India", "MARICO": "Marico",
    "DABUR": "Dabur India", "GODREJCP": "Godrej Consumer Products", "PAGEIND": "Page Industries",
    "CROMPTON": "Crompton Greaves Consumer", "HAVELLS": "Havells India", "SRF": "SRF Limited",
    "UPL": "UPL Limited", "TATACOMM": "Tata Communications", "CDSL": "CDSL", "CAMS": "CAMS",
    "ANGELONE": "Angel One", "RADICO": "Radico Khaitan", "KARURVYSYA": "Karur Vysya Bank",
    "NATCOPHARM": "Natco Pharma", "ZENSARTECH": "Zensar Technologies", "SONATSOFTW": "Sonata Software",
    "KFINTECH": "KFin Technologies", "CASTROLIND": "Castrol India", "IEX": "Indian Energy Exchange",
    "MCX": "Multi Commodity Exchange", "REDINGTON": "Redington", "RBLBANK": "RBL Bank",
    "CANFINHOME": "Can Fin Homes", "GRANULES": "Granules India", "LAURUSLABS": "Laurus Labs",
    "AARTIIND": "Aarti Industries", "DEEPAKNTR": "Deepak Nitrite", "NAVINFLUOR": "Navin Fluorine",
    "TATACHEM": "Tata Chemicals", "CHAMBLFERT": "Chambal Fertilisers", "JKCEMENT": "JK Cement",
    "RAMCOCEM": "Ramco Cements", "KEC": "KEC International", "NBCC": "NBCC India", "RVNL": "Rail Vikas Nigam",
    "IRCON": "IRCON International", "HUDCO": "HUDCO", "SJVN": "SJVN", "NHPC": "NHPC",
    "COCHINSHIP": "Cochin Shipyard", "MAZDOCK": "Mazagon Dock", "CYIENT": "Cyient", "BSOFT": "Birlasoft",
    "VEDL": "Vedanta", "BANKBARODA": "Bank of Baroda", "PNB": "Punjab National Bank", "CANBK": "Canara Bank",
    "TATAPOWER": "Tata Power", "GAIL": "GAIL India", "IOC": "Indian Oil Corp", "HINDPETRO": "Hindustan Petroleum",
    "BHEL": "BHEL", "INDIGO": "InterGlobe Aviation (IndiGo)", "LICHSGFIN": "LIC Housing Finance",
    "MUTHOOTFIN": "Muthoot Finance", "CHOLAFIN": "Cholamandalam Investment", "NAUKRI": "Info Edge (Naukri)",
    "PIDILITIND": "Pidilite Industries", "AMBUJACEM": "Ambuja Cements", "UNIONBANK": "Union Bank of India",
    "BANDHANBNK": "Bandhan Bank", "ICICIPRULI": "ICICI Prudential Life", "ICICIGI": "ICICI Lombard",
    "SBICARD": "SBI Cards", "MANAPPURAM": "Manappuram Finance", "LTTS": "L&T Technology Services",
    "OFSS": "Oracle Financial Services", "GLENMARK": "Glenmark Pharma", "BIOCON": "Biocon",
    "MANKIND": "Mankind Pharma", "TATAMOTORS": "Tata Motors", "MOTHERSON": "Samvardhana Motherson",
    "BOSCHLTD": "Bosch Limited", "APOLLOTYRE": "Apollo Tyres", "NATIONALUM": "National Aluminium",
    "JSL": "Jindal Stainless", "INDUSTOWER": "Indus Towers", "SIEMENS": "Siemens India", "ABB": "ABB India",
    "ADANIPOWER": "Adani Power", "JSWENERGY": "JSW Energy", "SHREECEM": "Shree Cement", "LODHA": "Lodha Developers",
}

# ------------------------------------------------------------------------------
# Mutual-fund universe (original 7 groups kept + new groups). Names are *search
# phrases*; the app resolves each to the Direct-Growth scheme through mfapi.in.
# ------------------------------------------------------------------------------
MFU = {
    "Large Cap": ["Nippon India Large Cap", "Mirae Asset Large Cap", "HDFC Large Cap", "ICICI Prudential Large Cap",
                  "SBI Large Cap", "Kotak Large Cap", "Axis Large Cap", "Canara Robeco Large Cap", "Bandhan Large Cap", "Franklin India Large Cap"],
    "Mid Cap": ["HDFC Mid Cap", "Motilal Oswal Midcap", "Nippon India Growth Mid Cap", "Axis Midcap", "Kotak Midcap",
                "DSP Midcap", "Edelweiss Mid Cap", "Mahindra Manulife Mid Cap", "Invesco India Mid Cap", "Sundaram Mid Cap"],
    "Small Cap": ["Nippon India Small Cap", "SBI Small Cap", "Quant Small Cap", "Axis Small Cap", "HDFC Small Cap",
                  "Kotak Small Cap", "Bandhan Small Cap", "Tata Small Cap", "Franklin India Smaller Companies", "Canara Robeco Small Cap"],
    "Flexi Cap": ["Parag Parikh Flexi Cap", "HDFC Flexi Cap", "Kotak Flexicap", "UTI Flexi Cap", "Quant Flexi Cap",
                  "JM Flexicap", "Motilal Oswal Flexi Cap", "Franklin India Flexi Cap", "Axis Flexi Cap", "Mirae Asset Flexi Cap"],
    "ELSS": ["Quant ELSS Tax Saver", "Mirae Asset ELSS Tax Saver", "SBI Long Term Equity", "Bandhan ELSS Tax Saver",
             "DSP ELSS Tax Saver", "Canara Robeco ELSS Tax Saver"],
    "Index (Nifty 50)": ["UTI Nifty 50 Index", "ICICI Prudential Nifty 50 Index", "SBI Nifty Index",
                         "HDFC Index Fund NIFTY 50", "Motilal Oswal Nifty Midcap 150 Index", "UTI Nifty Next 50 Index"],
    "Sectoral / Thematic": ["ICICI Prudential Technology", "Nippon India Pharma", "SBI Healthcare Opportunities",
                            "Nippon India Banking", "Tata Digital India", "ICICI Prudential Infrastructure",
                            "Nippon India Power & Infra"],
    "Balanced Advantage": ["HDFC Balanced Advantage", "ICICI Prudential Balanced Advantage",
                           "Kotak Balanced Advantage", "Nippon India Balanced Advantage", "Edelweiss Balanced Advantage"],
    "Contra / Value": ["SBI Contra", "Invesco India Contra", "Kotak Contra", "ICICI Prudential Value Discovery",
                       "Nippon India Value"],
}
HOLD = {
    "Large Cap": "3-5 saal", "Mid Cap": "5+ saal", "Small Cap": "7+ saal",
    "Flexi Cap": "5+ saal", "ELSS": "3 saal lock-in, 5+ saal ideal",
    "Index (Nifty 50)": "5+ saal", "Sectoral / Thematic": "1-3 saal tactical",
    "Balanced Advantage": "3+ saal", "Contra / Value": "5+ saal",
}

POS = ("surge gain rally profit beat record order win upgrade buy growth jump rise strong dividend bonus approval "
       "boost inflow outperformance soar climbs rebound expansion").split()
NEG = ("fall drop loss miss downgrade sell fraud probe penalty ban cut weak plunge crash default warning decline "
       "slump outflow underperformance tumble slides raid lawsuit shutdown").split()
SHORT = "result q1 q2 q3 q4 earnings rbi policy fii dii fed inflation cpi nfp rate".split()
MID = "order merger acquisition approval launch capex deal stake expansion patent budget".split()

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def master_symbols():
    """Union of every stock the app may need (without the .NS suffix)."""
    seen, out = set(), []
    for lst in list(UNI.values()) + [" ".join(v) for v in SECTOR_STOCKS.values()]:
        for s in lst.split():
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def sector_of(symbol):
    for sec, lst in SECTOR_STOCKS.items():
        if symbol in lst:
            return sec
    return None
