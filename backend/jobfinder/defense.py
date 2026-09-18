from __future__ import annotations

# Curated, not fetched from anywhere -- same spirit and maintenance model as
# featured.py: companies whose primary or major identifiable business line
# is military/defense contracting, intelligence-community work, or
# surveillance technology (facial recognition, mass monitoring, spyware,
# policing tech). Lets the dashboard filter these out for a viewer who wants
# to exclude them from a job search, without deleting the postings
# themselves -- a real preference, not a judgment encoded into filtering.
DEFENSE_SURVEILLANCE_COMPANIES: frozenset[str] = frozenset(
    name.lower()
    for name in [
        # Prime defense contractors
        "Lockheed Martin", "RTX", "Raytheon", "Raytheon Technologies",
        "Northrop Grumman", "General Dynamics", "L3Harris Technologies",
        "L3Harris", "BAE Systems", "Textron", "Kratos Defense & Security Solutions",
        "Oshkosh Defense", "AeroVironment", "Cubic Corporation",
        # Government/defense/intelligence services and IT contractors
        "Leidos", "Booz Allen Hamilton", "SAIC",
        "Science Applications International Corporation", "CACI International",
        "CACI", "ManTech International", "ManTech", "Peraton", "Parsons Corporation",
        # Defense-tech / autonomy startups
        "Anduril", "Anduril Industries", "Shield AI", "Epirus", "Saildrone",
        # International defense
        "Elbit Systems", "Rheinmetall", "Thales Group", "Thales",
        # Surveillance / facial-recognition / policing tech
        "Palantir", "Palantir Technologies", "Clearview AI", "NSO Group",
        "Axon Enterprise", "Axon", "Flock Safety", "Verkada", "Cellebrite",
        "Corsight AI", "Voyager Labs", "ShotSpotter", "SoundThinking",
    ]
)


def is_defense_surveillance(company: str) -> bool:
    return (company or "").strip().lower() in DEFENSE_SURVEILLANCE_COMPANIES
