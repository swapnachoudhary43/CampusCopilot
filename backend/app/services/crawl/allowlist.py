"""Official hosts the crawler is allowed to fetch.

A link is accepted only when its host is the university or one of the
department sites already identified from those sites. Other domains are
recorded as skipped and are not downloaded.
"""

from urllib.parse import urlparse

ALLOWED_HOST_SUFFIXES = ("dauniv.ac.in", "ietdavv.edu.in", "cdoedavv.ac.in", "iips.edu.in")

# Homepages linked from www.dauniv.ac.in on 13 Nov 2026, plus pages supplied as official.
SEED_URLS = (
    "https://www.dauniv.ac.in/",
    "https://www.dauniv.ac.in/admission",
    "https://www.dauniv.ac.in/exam-notice",
    "https://www.dauniv.ac.in/web2027",
    "https://www.dauniv.ac.in/syllabus",
    "https://www.dauniv.ac.in/pg-time-table",
    "https://www.dauniv.ac.in/ug-time-table",
    "https://www.dauniv.ac.in/iips",
    "https://www.dauniv.ac.in/dsf",
    "https://www.dauniv.ac.in/dsf-faculty-info",
    "https://edu.dauniv.ac.in/",
    "https://edu.dauniv.ac.in/academics.php",
    "https://edu.dauniv.ac.in/Library.php",
    "https://www.cdoedavv.ac.in/",
    "https://www.cdoedavv.ac.in/notices",
    "https://iconnect.ietdavv.edu.in/",
    "https://dsf.dauniv.ac.in/",
    "https://dsf.dauniv.ac.in/about.php",
    "https://dsf.dauniv.ac.in/academics.php",
    "https://dsf.dauniv.ac.in/ds.php",
    "https://dsf.dauniv.ac.in/SDSF_News/news.php",
    "https://iips.edu.in/",
    "https://iips.edu.in/about.php",
    "https://iips.edu.in/about_university.php",
    "https://iips.edu.in/academics.php",
    "https://iips.edu.in/courses.php",
    "https://iips.edu.in/how_to_apply.php",
    "https://iips.edu.in/fee_structure.php",
    "https://iips.edu.in/syllabus.php",
    "https://iips.edu.in/faculty_profile.php",
    "https://iips.edu.in/placement.php",
    "https://iips.edu.in/scholarship.php",
    "https://iips.edu.in/event.php",
    "https://iips.edu.in/grievance.php",
    "https://iips.edu.in/p_mtech-cs.php",
    "https://iips.edu.in/p_mca.php",
    "https://iips.edu.in/p_mtech.php",
    "https://iips.edu.in/p_mbams5.php",
    "https://iips.edu.in/p_mbat5.php",
    "https://iips.edu.in/p_bcom.php",
    "https://iips.edu.in/p_mbams2.php",
    "https://iips.edu.in/p_mbata2.php",
    "https://iips.edu.in/p_mbaapr2.php",
    "https://iips.edu.in/p_mbaent2.php",
    "https://lib.dauniv.ac.in/",
    "https://dsw.dauniv.ac.in/",
    "https://research.dauniv.ac.in/",
    "https://iqac.dauniv.ac.in/",
    "https://itc.dauniv.ac.in/",
    "https://nss.dauniv.ac.in/",
    "https://duaa.dauniv.ac.in/",
    "https://sindhupeeth.dauniv.ac.in/",
    "https://umc.dauniv.ac.in/",
    "https://naac.dauniv.ac.in/",
    "https://ost.dauniv.ac.in/",
    "https://vcdavv.dauniv.ac.in/",
    "https://cpc.dauniv.ac.in/",
    "https://www.ietdavv.edu.in/",
    "https://notices.ietdavv.edu.in/",
    "https://www.sports.dauniv.ac.in/",
)

OFFICIAL_SITES = (
    {"name": "Devi Ahilya Vishwavidyalaya", "url": "https://www.dauniv.ac.in/", "category": "university", "parent": "DAVV"},
    {"name": "University academic portal", "url": "https://edu.dauniv.ac.in/", "category": "portal", "parent": "DAVV"},
    {"name": "Central Library", "url": "https://lib.dauniv.ac.in/", "category": "library", "parent": "DAVV"},
    {"name": "School of Data Science and Forecasting", "url": "https://dsf.dauniv.ac.in/", "category": "school", "parent": "DAVV"},
    {"name": "International Institute of Professional Studies", "url": "https://iips.edu.in/", "category": "institute", "parent": "DAVV"},
    {"name": "Institute of Engineering and Technology", "url": "https://www.ietdavv.edu.in/", "category": "institute", "parent": "DAVV"},
    {"name": "IET notices", "url": "https://notices.ietdavv.edu.in/", "category": "notices", "parent": "IET"},
    {"name": "iConnect IET", "url": "https://iconnect.ietdavv.edu.in/", "category": "portal", "parent": "IET"},
    {"name": "Centre for Distance and Online Education", "url": "https://www.cdoedavv.ac.in/", "category": "centre", "parent": "DAVV"},
    {"name": "Centralised Placement Cell", "url": "https://cpc.dauniv.ac.in/", "category": "placement", "parent": "DAVV"},
    {"name": "Dean of Student Welfare", "url": "https://dsw.dauniv.ac.in/", "category": "student_welfare", "parent": "DAVV"},
    {"name": "Research compendium", "url": "https://research.dauniv.ac.in/", "category": "research", "parent": "DAVV"},
    {"name": "IQAC", "url": "https://iqac.dauniv.ac.in/", "category": "quality", "parent": "DAVV"},
    {"name": "Information Technology Centre", "url": "https://itc.dauniv.ac.in/", "category": "centre", "parent": "DAVV"},
    {"name": "NSS", "url": "https://nss.dauniv.ac.in/", "category": "student_welfare", "parent": "DAVV"},
    {"name": "Sindhu Peeth", "url": "https://sindhupeeth.dauniv.ac.in/", "category": "centre", "parent": "DAVV"},
    {"name": "University Minority Cell", "url": "https://umc.dauniv.ac.in/", "category": "centre", "parent": "DAVV"},
    {"name": "Sports", "url": "https://www.sports.dauniv.ac.in/", "category": "facility", "parent": "DAVV"},
    {"name": "DAVV Alumni Association", "url": "https://duaa.dauniv.ac.in/", "category": "association", "parent": "DAVV"},
    {"name": "Office of the Vice Chancellor", "url": "https://vcdavv.dauniv.ac.in/", "category": "administration", "parent": "DAVV"},
    {"name": "Online services", "url": "https://ost.dauniv.ac.in/", "category": "portal", "parent": "DAVV"},
    {"name": "NAAC", "url": "https://naac.dauniv.ac.in/", "category": "quality", "parent": "DAVV"},
)


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def department_for(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "").lower()
    if host.startswith("dsf.") or path.startswith("/dsf"):
        return "School of Data Science and Forecasting"
    if "iips.edu.in" in host or path.startswith("/iips"):
        return "International Institute of Professional Studies"
    if "cdoedavv.ac.in" in host:
        return "Centre for Distance and Online Education"
    if host.startswith("lib."):
        return "Central Library"
    if host.startswith("dsw."):
        return "Dean of Student Welfare"
    if host.startswith("research."):
        return "Research"
    if "ietdavv.edu.in" in host:
        return "Institute of Engineering and Technology"
    if host.startswith("cpc."):
        return "Centralised Placement Cell"
    if host.startswith("edu."):
        return "University academic portal"
    return "Devi Ahilya Vishwavidyalaya"
