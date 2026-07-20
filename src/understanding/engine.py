from __future__ import annotations

import logging
import re

from src.conversation.state import ConversationState
from src.engines.interfaces import UnderstandingInput
from src.understanding.interpreter import DomainInterpreter
from src.understanding.models import (
    ConversationSignals,
    IntentDiagnostics,
    MissingInformation,
    StageDetail,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.understanding.profile import (
    PATHWAY_REQUIRED_FIELDS,
    StudentProfile,
    compute_missing,
    is_field_set,
)
from src.understanding.vocabulary import INTENT_CONCEPTS, match_concept

logger = logging.getLogger(__name__)


def _detect_conflicts(pre: dict[str, float], post: dict[str, float]) -> list[str]:
    """Compare pre/post conflict scores to describe what conflicts fired."""
    conflicts: list[str] = []
    for intent in set(list(pre.keys()) + list(post.keys())):
        pre_val = pre.get(intent, 0)
        post_val = post.get(intent, 0)
        if post_val < pre_val:
            conflicts.append(f"'{intent}' reduced by {pre_val - post_val:.3f}")
        elif post_val > pre_val:
            conflicts.append(f"'{intent}' boosted by {post_val - pre_val:.3f}")
    return conflicts


RE_RANK = re.compile(
    r"(?:rank|air|ran)\s*(?:is|:)?\s*(\d{1,6})"
    r"|(\d{1,6})\s*(?:rank|air|ran)",
    re.IGNORECASE,
)
RE_PCM = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%?\s*(?:pcm|percentage|marks|aggregate|percent)"
    r"|(?:pcm|percentage|marks|aggregate)\s*(?:is|:)?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
    re.IGNORECASE,
)
RE_BOARD = re.compile(
    r"\b(wbchse|cbse|icse|west\s*bengal|bengal\s*board|state\s*board|central\s*board)\b",
    re.IGNORECASE,
)
RE_INTEREST = re.compile(
    r"(?:interested\s*in|want\s*(?:to\s*do|to\s*study|to\s*take|to\s*get|to\s*pursue)|"
    r"prefer|like|choose|aim\s*for|target|opt\s*for|looking\s*for|dream\s*of)\s+(\w+(?:\s+\w+){0,2})",
    re.IGNORECASE,
)
RE_BUDGET = re.compile(
    r"(?:budget|afford|fee|financial|cost|spend|pay)\s*(?:is|of|:)?\s*"
    r"(?:around\s+|about\s+|nearly\s+|~)?\s*"
    r"(?:rs\.?\s*|₹\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:lakh|lac|l|k|thousand|per\s*year)?"
    r"|(?:rs\.?\s*|₹\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:lakh|lac|l|k|thousand)\s*(?:budget|afford|fee)",
    re.IGNORECASE,
)
RE_CATEGORY = re.compile(
    r"\b(general|obc|sc|st|ews|gen|ur|unreserved)\b",
    re.IGNORECASE,
)
RE_LOCATION = re.compile(
    r"\b(bengal\s*|west\s*bengal|kolkata|howrah|hooghly|nadia|north\s*24|south\s*24|"
    r"state|outside\s*bengal|other\s*state)\b",
    re.IGNORECASE,
)
RE_NAME = re.compile(
    r"(?:my\s*name\s*is|i['']?m|called|myself)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
)

_INTENT_PATTERNS: list[tuple[str, str, float]] = [
    ("fee", (
        r"(?:\bfee\b|\bfees\b|\btuition\b|शुल्क|फीस|ফীस|কোর্স ফি|\bcourse\s+fee\b|কত টাকা|"
        r"kitna\s+fee\b|fee\s+kitna|how\s+much|koto\s+taka|koto\s+fee|多少钱|"
        r"fee\s+structure|fee\s+details|installment|payment|"
        r"fee\s+waiver|concession|discount|"
        r"ফি(?:স)?(?:\s+কি(?:তনি|তা))?|"
        r"फीस(?:\s+कितन)?)"
    ), 0.8),
    ("admission", (
        r"(?:admission|apply.*college|form.*fill|admit|प्रवेश|ভর্তি|"
        r"যোগ্যতা|eligibility|पात्रतা|কবে|kab se|kab hogi|"
        r"can I get|admission process|প্রক্রিয়া|পদ্ধতি|"
        r"college.*(choose|select|pick|which)|choose.*college|"
        r"which.*college|college.*for.*engineering)"
    ), 0.7),
    ("placement", (
        r"(?:placement|job|package|salary|recruit|hire|"
        r"placement\s*record|highest\s*package|CTC|lpa|"
        r"placements|প্লেসমেন্ট|recruiter|company.*visit)"
    ), 0.8),
    ("hostel", (
        r"(?:hostel|dorm|accommodation|room|हॉस्टल|আবাসন|"
        r"mess|boarding|hostel fee|hostel facility|আবাসন)"
    ), 0.8),
    ("scholarship", (
        r"(?:scholarship|financial\s*aid|stipend|"
        r"छात्रवृत्ति|স্কলারশিপ|free\s*ship|ছাত্রবৃত্তি|"
        r"post.matric|merit|based scholarship)"
    ), 0.8),
    ("department", (
        r"(?:"
        r"(?:department|branch|stream|course).*?(?:offer|avail|provid|have|there|kya|hai|क्या|কি|কৌন|kon|kaun)|"
        r"(?:which|what|kaun|kon|কোন)\s+(?:department|branch|stream|course)|"
        r"department\s+info|branch\s+info|stream\s+info|"
        r"which\s+department|which\s+branch|"
        r"कौन\s+स[ेा]\s+विभाग|"
        r"विभाग\s+है|বিভাগ\s+আছে|"
        r"branch(es)?\s+do\s+you|"
        r"departments?\s+are|branch\s+available|"
        r"kaun.*branch|kon.*branch|কন.*branch"
        r")"
    ), 0.7),
    ("contact", (
        r"(?:contact|phone|email|address|reach|संपर्क|"
        r"যোগাযোগ|call|whatsapp|telephone|mobile|office|location)"
    ), 0.7),
    ("cutoff", (
        r"(?:cutoff|cut\s*off|previous\s*year|last\s*year\s*rank|"
        r"closing\s*rank|कटऑफ|কাটঅফ|rank.*cutoff|eligibility\s*rank)"
    ), 0.8),
    ("seats", r"(?:seat|intake|capacity|strength|सीट|সিট|how\s*many\s*students|available.*seat)", 0.7),
    ("faculty", r"(?:faculty|teacher|professor|शिक्षक|অধ্যাপক|staff|qualification|PhD|experienced)", 0.7),
    ("hod", r"(?:principal|hod|head|director|dean|निदेशक|অধ্যক্ষ|incharge)", 0.7),
    ("safety", (
        r"(?:safe|safety|security|campus|girl|women|hostel\s*safety|"
        r"सुरक्षा|सुरक्षित|সুরক্ষা|নিরাপত্তা|সুরক্ষিত|"
        r"girls.*safe|secure\s*campus|worried\s*safety|कैंपस|ক্যাম্পাস)"
    ), 0.6),
    ("timings", r"(?:timing|time|hour|schedule|college\s*timing|office\s*hour|कब|কখন)", 0.7),
    ("repeat", r"(?:repeat|again|say\s*again|दोबारा|what\s*said|sorry|fir\s*se|dubara)", 0.6),
    ("greeting", (
        r"^(?:hello|hi|hey|good\s*(?:morning|afternoon|evening)|"
        r"namaste|namaskar|vanakkam)\b"
        r"|^(?:नमस्ते|হ্যালো|ওঁ নমঃ|namaskar|vanakkam)"
    ), 0.9),
    ("sports_quota", (
        r"(?:sports\s*quota|sports\s*admission|athlete|"
        r"sports.*seat|state.level|national.*level|cricket|"
        r"football|player|খেলাধুলা|खेल|sports.*certificate|trial)"
    ), 0.7),
    ("transfer", (
        r"(?:transfer|migration|change\s+college|shift\s+to|"
        r"switch\s+college|स्थानांतरण|স্থানান্তর|"
        r"current.*college|lateral|inter.college)"
    ), 0.7),
    ("distance_education", (
        r"(?:distance|online.*(?:course|degree|program|btech|study)|"
        r"correspondence|blended|distance learning|दूरस्थ|দূরশিক্ষণ)"
    ), 0.7),
    ("grievance", (
        r"(?:grievance|complaint|re.evaluat|rechecking|"
        r"marks.*lower|lower.*expect|issue.*exam|problem.*college|"
        r"शिकायत|অভিযোগ|not.*renewed|hasn.*t.*been)"
    ), 0.7),
    ("counseling_info", (
        r"(?:counseling|counselling|"
        r"when.*counseling|counseling.*date|কাউন্সেলিং|काउंसलिंग|"
        r"allotment|choice.*filling|mock.*round|"
        r"counseling.*document|document.*counseling)"
    ), 0.7),
    ("document", (
        r"(?:document|marksheet|certificate|10th.*mark|12th.*mark|"
        r"provisional|transfer.*certificate|migration.*certificate|"
        r"document.*need|need.*document|what.*document|"
        r"ডকুমেন্ট|प्रमाणपत्र|দস্তাবেজ)"
    ), 0.7),
    ("career_confusion", (
        r"(?:confus(?:ed|ion|ing|e).*?(?:about|which|what|career|hai|mein)|"
        r"not\s+sure.*?(?:about|which|what|hai)|"
        r"what\s+should\s+(?:i|she|he)\s+(?:do|study|choose|pick)|"
        r"dilemma|career.*?option|what\s+to\s+(?:do|choose|take)|"
        r"parent.*?want.*?engineering|don.*?t\s+know\s+what|"
        r"decide\s+(?:nahi|nhi|ni)\s+(?:kar|pa|sak)|"
        r"kaun\s+sa\s+(?:branch|stream|subject|career)|"
        r"kya\s+(?:kare|choose\s+kare|lena\s+chahiye)|"
        r"confusion\s+(?:hai|mein|ho|raha)|"
        r"pareshan.*?(?:hai|mein|choice|career|branch)|"
        r"samajh\s+(?:nahi|nhi|ni)\s+(?:aa|raha)|"
        r"কনফিউশন|দ্বিধা|কী\s+করব)"
    ), 0.7),
    ("lateral_entry", (
        r"(?:lateral|direct.*second.*year|diploma.*btech|polytechnic.*admission|"
        r"diploma.*(admission|engineering|btech|second)|jexpo|"
        r"after\s+diploma|from\s+diploma)"
    ), 0.7),
    ("management_quota", (
        r"(?:management\s*quota|donation|paid\s*seat|"
        r"management\s*seat|payment\s*seat|direct.*admission.*management)"
    ), 0.7),
    ("nri_admission", (
        r"(?:nri|foreign|international.*student|"
        r"abroad|nri\s*quota|nri\s*seat|outside.*india)"
    ), 0.7),
    ("loan", (
        r"(?:education\s*loan|student\s*loan|loan|शिक्षा\s*ऋण|"
        r"bank.*loan|loan.*amount|loan.*interest|loan.*apply|"
        r"কতটাকা\s*ঋণ|how\s*much\s*loan|loan\s*available)"
    ), 0.8),
    ("institution", (
        r"(?:affiliat|accredit|naac|college.*affil|"
        r"college.*name|institution.*name|"
        r"principal|hod|head\s+of\s+department|director|dean|"
        r"কলেজের\s+নাম)"
    ), 0.7),
]

_NEGATION_PREFIX_RE = re.compile(
    r'(?:^|\s)(?:not|no|n\'?t|never|don\'?t|doesn\'?t|isn\'?t|aren\'?t|wasn\'?t|weren\'?t|won\'?t|can\'?t|haven\'?t|hasn\'?t)\s+'
    r'(?:\w+\s+){0,2}$',
    re.IGNORECASE,
)

_INTENT_SIGNAL_BOOSTS: dict[str, dict[str, float]] = {
    "fee": {"financial_concern": 0.15},
    "scholarship": {"financial_concern": 0.2},
    "admission": {"urgency": 0.1},
    "cutoff": {"urgency": 0.15},
    "department": {"confusion": 0.1},
    "safety": {"anxiety": 0.15},
    "hostel": {"anxiety": 0.1, "urgency": 0.05},
    "placement": {"anxiety": 0.1},
}

_SIGNAL_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "anxiety": [
        (r'\bworried\b', 0.35),
        (r'\bnervous\b', 0.35),
        (r'\btension\b', 0.35),
        (r'\banxious\b', 0.4),
        (r'\bscared\b', 0.4),
        (r'\btense\b', 0.35),
        (r'\bstressed\b', 0.35),
        (r'\bafraid\b', 0.4),
        (r'\bpanic(?:k?ing|s|ked|ed)?\b', 0.45),
        (r'\bconcerned\b', 0.25),
        (r'\buneasy\b', 0.35),
        (r'\bstressed?\s+out\b', 0.4),
        (r'\bfreaking\s+out\b', 0.5),
        (r'\bfeeling\s+nervous\b', 0.4),
        (r"\bi'?m\s+worried\b", 0.45),
        (r"\bi\s+am\s+very\s+worried\b", 0.45),
        (r"\bi\s+am\s+scared\b", 0.45),
        (r'\bchinta\b', 0.35),
        (r'\bडर\b', 0.4),
        (r'\bपरेशान\b', 0.3),
        (r'\btension\s+hai\b', 0.4),
        (r'\bghabrahat\b', 0.4),
        (r'\bচিন্তা\b', 0.35),
        (r'\bভয়\b', 0.4),
        (r'\bটেনশন\b', 0.35),
        (r'\bউদ্বিগ্ন\b', 0.4),
        (r'\bbahut\s+tension\b', 0.45),
        (r'\bparents\s+pressure\b', 0.35),
        (r'\bpressure\s+hai\b', 0.3),
        (r'\bdarak\b', 0.3),
        (r'\bdar\s+lag', 0.35),
        (r'\bpare?shan\b', 0.3),
    ],
    "urgency": [
        (r'\burgent\b', 0.45),
        (r'\bquick\b', 0.25),
        (r'\bhurry\b', 0.35),
        (r'\blast\s*date\b', 0.45),
        (r'\bdeadline\b', 0.45),
        (r'\bimmediately\b', 0.4),
        (r'\basap\b', 0.45),
        (r'\bsoon\b', 0.2),
        (r'\bhurry\s+up\b', 0.4),
        (r'\brunning\s+out\s+of\s+time\b', 0.5),
        (r'\bcutoff\s*date\b', 0.35),
        (r'\blast\s+day\b', 0.4),
        (r'\btime\s+is\s+running\b', 0.45),
        (r'\bजल्दी\b', 0.35),
        (r'\bjaldi\b', 0.3),
        (r'\bjaldi\s+batao\b', 0.4),
        (r'\btime\s+kam\s+hai\b', 0.4),
        (r'\bder\s+ho\s+rahi\b', 0.35),
        (r'\bজলদি\b', 0.35),
        (r'\bতারাতারি\b', 0.35),
        (r'\bসময়\s*নেই\b', 0.4),
        (r'\bdeadline\s+close\b', 0.45),
        (r'\btime\s+nahi\s+hai\b', 0.4),
        (r'\bkab\s+tak\b', 0.2),
        (r'\bkitna\s+time\b', 0.2),
        (r'\btime\s+limit\b', 0.35),
        (r'\bexpire\b', 0.35),
    ],
    "confusion": [
        (r'\bconfused\b', 0.35),
        (r'\bnot\s+sure\b', 0.3),
        (r"\bdon'?t\s+know\b", 0.25),
        (r'\bno\s+idea\b', 0.25),
        (r'\bwhat\s+should\s+i\s+do\b', 0.35),
        (r"\bcan'?t\s+decide\b", 0.4),
        (r'\bconfused\s+about\b', 0.4),
        (r'\bunclear\b', 0.3),
        (r'\bnot\s+clear\b', 0.3),
        (r'\bwhat\s+to\s+choose\b', 0.35),
        (r'\bunsure\b', 0.3),
        (r'\bdilemma\b', 0.35),
        (r'\bwhich\s+one\b', 0.2),
        (r'\bhow\s+to\s+decide\b', 0.35),
        (r'\bसमझ\s*नहीं\b', 0.4),
        (r'\bkya\s+karein\b', 0.3),
        (r'\bpata\s+nahi\b', 0.2),
        (r'\bconfusion\s+hai\b', 0.35),
        (r'\bsamajh\s+nahi\b', 0.35),
        (r'\bবুঝতে\s*পারছি\s*না\b', 0.4),
        (r'\bকী\s*করব\b', 0.3),
        (r'\bconfusion\b', 0.25),
        (r'\bidea\s+nei\b', 0.25),
        (r'\bkuch\s+samajh\b', 0.3),
        (r'\bsamajh\s+mein\b', 0.25),
        (r'\bkya\s+karu\b', 0.25),
        (r'\bhow\s+to\s+choose\b', 0.35),
        (r"\bcan'?t\s+understand\b", 0.3),
    ],
    "hesitation": [
        (r'\bmaybe\b', 0.2),
        (r'\bperhaps\b', 0.2),
        (r'\bprobably\b', 0.2),
        (r'\bmight\b', 0.15),
        (r'\bpossibly\b', 0.2),
        (r'\bmay\s+be\b', 0.2),
        (r'\bi\s+think\b', 0.15),
        (r'\bi\s+guess\b', 0.2),
        (r'\bcould\s+be\b', 0.2),
        (r'\bnot\s+sure\s+if\b', 0.3),
        (r'\bwondering\s+if\b', 0.2),
        (r'\bशायद\b', 0.2),
        (r'\bहो\s*सकता\s*है\b', 0.2),
        (r'\blagta\s+hai\b', 0.15),
        (r'\bহয়তো\b', 0.2),
        (r'\bপারে\b', 0.15),
        (r'\bমনে\s*হয়\b', 0.15),
        (r'\bshayad\b', 0.2),
        (r'\bho\s+sakta\s+hai\b', 0.2),
        (r'\bnot\s+sure\b', 0.25),
        (r'\bkya\s+pata\b', 0.2),
        (r'\bshayed\b', 0.2),
    ],
    "frustration": [
        (r'\bfrustrated\b', 0.4),
        (r'\bfed\s+up\b', 0.4),
        (r'\btired\b', 0.25),
        (r'\bannoyed\b', 0.35),
        (r'\benough\b', 0.25),
        (r'\bsick\s+of\b', 0.4),
        (r'\bnot\s+working\b', 0.3),
        (r'\buseless\b', 0.35),
        (r'\bwaste\b', 0.25),
        (r'\btoo\s+complicated\b', 0.35),
        (r'\bdifficult\b', 0.2),
        (r'\bwhy\s+is\s+it\s+so\s+hard\b', 0.4),
        (r'\bबहुत\s*हो\s*गया\b', 0.4),
        (r'\bपरेशान\s*हो\s*गया\b', 0.35),
        (r'\bथक\s*गया\b', 0.3),
        (r'\bनिराश\b', 0.35),
        (r'\bবিরক্ত\b', 0.35),
        (r'\bক্লান্ত\b', 0.25),
        (r'\bসহ্য\s*হচ্ছে\s*না\b', 0.4),
        (r'\bbahut\s+ho\s+gaya\b', 0.4),
        (r'\bthak\s+gaya\b', 0.3),
        (r'\bnirash\b', 0.35),
        (r'\bwhy\s+is\s+it\s+so\b', 0.2),
    ],
    "financial_concern": [
        (r'\bexpensive\b', 0.3),
        (r'\bcostly\b', 0.3),
        (r'\bafford\b', 0.3),
        (r'\bbudget\b', 0.2),
        (r'\bmoney\b', 0.15),
        (r'\bfees?\b', 0.15),
        (r'\bfee\s+high\b', 0.35),
        (r'\bfees\s+high\b', 0.35),
        (r'\bfees?\s+too\s+high\b', 0.4),
        (r'\bcheap\b', 0.2),
        (r'\blow\s+fee\b', 0.25),
        (r"\bcan'?t\s+afford\b", 0.4),
        (r'\btoo\s+expensive\b', 0.4),
        (r'\bfinancial\s+issue\b', 0.4),
        (r'\bnot\s+enough\s+money\b', 0.4),
        (r'\bbroke\b', 0.35),
        (r'\btight\s+budget\b', 0.35),
        (r'\beducation\s+loan\b', 0.3),
        (r'\bscholarship\s+needed\b', 0.3),
        (r'\bमहंगा\b', 0.3),
        (r'\bकिफ़ायत\b', 0.2),
        (r'\bपैसे\s*की\s*समस्या\b', 0.4),
        (r'\bफीस\s*ज्यादा\b', 0.35),
        (r'\bbudget\s+kam\s+hai\b', 0.35),
        (r'\bবেশি\s*দাম\b', 0.3),
        (r'\bসস্তা\b', 0.2),
        (r'\bটাকার\s*সমস্যা\b', 0.4),
        (r'\bfees\s+high\b', 0.3),
        (r'\bআর্থিক\b', 0.25),
        (r'\bfees\s+bahut\b', 0.35),
        (r'\bpaise\s+nahi\b', 0.35),
        (r'\bbudget\s+nahi\b', 0.35),
        (r'\bloan\s+needed\b', 0.3),
        (r'\bscholarship\s+chai\b', 0.25),
        (r'\bafford\s+korte\s+parbe\s+na\b', 0.45),
        (r'\bbudget?\s*(?:kam|kum|kom)\b', 0.3),
        (r'\bpaise\s+ki\s+samasya\b', 0.4),
        (r'\bfees\s+bahut\s+hai\b', 0.35),
        (r'\bfinancial\s+problem\b', 0.4),
    ],
    "parent_influence": [
        (r'\bmy\s+father\b', 0.35),
        (r'\bmy\s+mother\b', 0.35),
        (r'\bmy\s+parents\b', 0.35),
        (r'\bmom\s+said\b', 0.35),
        (r'\bdad\s+wants\b', 0.35),
        (r'\bfather\s+wants\b', 0.35),
        (r'\bfamily\s+wants\b', 0.3),
        (r'\bparents\s+want\b', 0.35),
        (r'\baccording\s+to\s+my\s+father\b', 0.4),
        (r'\bmy\s+family\s+decided\b', 0.4),
        (r'\bपिता\s*जी\b', 0.35),
        (r'\bमाता\s*जी\b', 0.35),
        (r'\bmere\s+papa\b', 0.35),
        (r'\bmeri\s+maa\b', 0.35),
        (r'\bghar\s+wale\b', 0.3),
        (r'\bparents\s+ka\s+kehna\b', 0.35),
        (r'\bfather\s+ne\s+kaha\b', 0.35),
        (r'\bআমার\s*বাবা\b', 0.35),
        (r'\bআমার\s*মা\b', 0.35),
        (r'\bবাবা-মা\b', 0.35),
        (r'\bপরিবার\b', 0.2),
        (r'\bmere\s+papa\s+ne\s+kaha\b', 0.4),
        (r'\bghar\s+wale\s+chahte\b', 0.35),
        (r'\bparents\s+bol\b', 0.3),
        (r'\bmy\s+family\s+wants\b', 0.35),
        (r'\bfather\s+said\b', 0.35),
        (r'\bmother\s+said\b', 0.35),
        (r'\bparents\s+said\b', 0.35),
        (r'\bmom\s+wants\b', 0.35),
    ],
}


class UnderstandingEngine:
    VERSION = "v6"

    def __init__(self, interpreter: DomainInterpreter | None = None):
        self._interpreter = interpreter or DomainInterpreter()
        self._prev_signals: ConversationSignals | None = None

    def process(self, input: UnderstandingInput) -> UnderstandingResult:
        result = self.understand(input.text, input.state, debug=input.debug)
        if input.debug:
            diag: IntentDiagnostics | None = result.metadata.get("_diag_raw")
            if diag:
                result.metadata["intent_diagnostics"] = diag
                result.metadata["intent_diagnostics_str"] = self._format_diagnostics(diag)
        return result

    def understand(
        self, text: str, state: ConversationState | None = None,
        debug: bool = False,
    ) -> UnderstandingResult:
        # Stage 1: Language
        language = self._detect_language(text)

        # Stage 2: Build / update StudentProfile from text
        profile = self._restore_profile(state)
        profile = self._update_profile(text, profile)

        # Stage 3: Domain interpretation (concept layer)
        domain = self._interpreter.interpret(text)

        # Apply domain pathway to profile
        if domain.pathway != "regular":
            profile.admission_pathway = domain.pathway
        if domain.student_type != "prospective":
            profile.student_type = domain.student_type

        # Stage 4: Evidence-based intent classification (uses profile + domain + state)
        intent, diagnostics = self._classify_intent(text, profile, domain, state, debug=debug)

        # Override intent with domain-aware intent if still unknown
        if intent.primary == "unknown" and domain.primary_intent != "unknown":
            intent = UnderstandingIntent(
                primary=domain.primary_intent, confidence=0.6,
                all_scores={domain.primary_intent: 0.6}
            )

        # Stage 5: Signals
        signals = self._detect_signals(text, intent, profile)

        # Stage 6: Missing information — fully deterministic from profile
        missing = self._compute_missing_from_profile(profile)

        references = self._detect_references(text)
        confidence = self._score_confidence(text, profile, intent)

        result = UnderstandingResult(
            text=text,
            language=language,
            intent=intent,
            profile=profile,
            signals=signals,
            missing_info=missing,
            references_previous=references,
            confidence=confidence,
            domain=domain,
        )
        if debug and diagnostics:
            result.metadata["_diag_raw"] = diagnostics
        return result

    def _detect_language(self, text: str) -> str:
        if any("\u0980" <= c <= "\u09ff" for c in text):
            return "bn"
        if any("\u0900" <= c <= "\u097f" for c in text):
            return "hi"
        hi_bn_words = {
            "hi": {"hai", "hain", "kya", "kaise", "kitna", "kaun", "kab", "kyu", "mera", "tera"},
            "bn": {"ami", "amar", "koto", "ache", "hobe", "keno", "kivabe", "bhalo"},
        }
        tl = text.lower()
        hi_score = sum(1 for w in hi_bn_words["hi"] if w in tl)
        bn_score = sum(1 for w in hi_bn_words["bn"] if w in tl)
        if hi_score > bn_score and hi_score >= 2:
            return "hi"
        if bn_score > hi_score and bn_score >= 2:
            return "bn"
        return "en"

    def _classify_intent(
        self, text: str,
        profile: StudentProfile | None = None,
        domain: DomainInterpretation | None = None,
        state: ConversationState | None = None,
        debug: bool = False,
    ) -> tuple[UnderstandingIntent, IntentDiagnostics | None]:
        tl = text.lower().strip()
        diagnostics = IntentDiagnostics(input=text) if debug else None

        # Stage 1: Keyword evidence (existing _INTENT_PATTERNS)
        keyword_scores: dict[str, float] = {}
        for intent_name, pattern, weight in _INTENT_PATTERNS:
            if re.search(pattern, tl):
                keyword_scores[intent_name] = max(keyword_scores.get(intent_name, 0.0), weight)

        # Stage 2: Entity-based evidence (from extracted profile fields)
        entity_scores = self._entity_intent_evidence(tl, profile)

        # Stage 3: Domain/pathway evidence
        domain_scores = self._domain_intent_evidence(domain)

        # Stage 4: Conversation context evidence
        context_scores = self._context_intent_evidence(state, profile, tl)

        # Stage 5: Additional wording pattern evidence
        wording_scores = self._wording_intent_evidence(tl)

        # Stage 6: Profile completeness evidence
        completeness_scores = self._completeness_intent_evidence(profile)

        # Combine all evidence with weights
        all_intents: set[str] = set()
        for d in [keyword_scores, entity_scores, domain_scores,
                  context_scores, wording_scores, completeness_scores]:
            all_intents.update(d.keys())

        all_scores: dict[str, float] = {}
        weights = {
            "keyword": 0.35, "entity": 0.25, "domain": 0.15,
            "context": 0.15, "wording": 0.05, "completeness": 0.05,
        }

        stage_raw = {
            "keyword": keyword_scores,
            "entity": entity_scores,
            "domain": domain_scores,
            "context": context_scores,
            "wording": wording_scores,
            "completeness": completeness_scores,
        }

        per_intent_breakdown: dict[str, dict[str, float]] = {}
        for intent in all_intents:
            breakdown: dict[str, float] = {}
            for stage, raw in stage_raw.items():
                breakdown[stage] = round(raw.get(intent, 0.0) * weights[stage], 3)
            per_intent_breakdown[intent] = breakdown

        for intent in all_intents:
            score = (
                keyword_scores.get(intent, 0.0) * weights["keyword"]
                + entity_scores.get(intent, 0.0) * weights["entity"]
                + domain_scores.get(intent, 0.0) * weights["domain"]
                + context_scores.get(intent, 0.0) * weights["context"]
                + wording_scores.get(intent, 0.0) * weights["wording"]
                + completeness_scores.get(intent, 0.0) * weights["completeness"]
            )
            all_scores[intent] = round(score, 3)

        pre_conflict = dict(all_scores)

        # Apply conflict resolution
        all_scores = self._resolve_intent_conflicts(all_scores, tl, profile, domain)

        if all_scores:
            best = max(all_scores, key=all_scores.get)
            best_score = all_scores[best]
        else:
            best = "unknown"
            best_score = 0.0

        # Minimum threshold — below this, return unknown
        if best_score < 0.08:
            best = "unknown"
            best_score = 0.0

        intent = UnderstandingIntent(primary=best, confidence=best_score, all_scores=all_scores)

        if debug:
            _d = diagnostics
            _d.stage_weights = weights
            _d.stage_details = {
                name: StageDetail(
                    scores=scores,
                    evidence=self._collect_stage_evidence(name, tl, profile, state, domain),
                )
                for name, scores in stage_raw.items()
            }
            _d.per_intent_breakdown = per_intent_breakdown
            _d.pre_conflict = pre_conflict
            _d.post_conflict = all_scores
            _d.conflicts_applied = _detect_conflicts(pre_conflict, all_scores)
            _d.winner = best
            _d.confidence = best_score
            _d.winner_reason = self._build_winner_reason(
                best, all_scores, pre_conflict, per_intent_breakdown, _d.conflicts_applied,
            )
            # Ranked intents, margin, confidence class
            sorted_scores = sorted(all_scores.items(), key=lambda x: -x[1])
            _d.ranked_intents = sorted_scores
            _d.runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
            _d.margin = round(best_score - _d.runner_up_score, 3)
            if _d.margin > 0.30:
                _d.confidence_class = "HIGH"
            elif _d.margin >= 0.15:
                _d.confidence_class = "MEDIUM"
            elif _d.margin >= 0.05:
                _d.confidence_class = "LOW"
            else:
                _d.confidence_class = "AMBIGUOUS"

        return intent, diagnostics

    def _collect_stage_evidence(
        self, stage: str, tl: str, profile: StudentProfile | None,
        state: ConversationState | None, domain: DomainInterpretation | None,
    ) -> list[str]:
        evidence: list[str] = []
        if stage == "keyword":
            for intent_name, pattern, weight in _INTENT_PATTERNS:
                m = re.search(pattern, tl)
                if m:
                    evidence.append(f"{intent_name} +{weight} [{m.group(0)}]")
        elif stage == "entity" and profile:
            def _get_val(field: str):
                mapping = {
                    "rank": profile.academic.rank,
                    "pcm_percentage": profile.academic.pcm_percentage,
                    "exam": profile.academic.exam,
                    "board": profile.academic.board,
                    "budget": profile.personal.budget,
                    "category": profile.personal.category,
                    "interest": profile.career.interest,
                    "hostel_required": profile.personal.hostel_required,
                    "location": profile.personal.location,
                }
                return mapping.get(field)
            seen_intents: set[str] = set()
            for field, mappings in self._ENTITY_EVIDENCE.items():
                val = _get_val(field)
                if val is not None and val != "":
                    for intent_name, weight in mappings:
                        if intent_name not in seen_intents:
                            evidence.append(f"{intent_name} +{weight} ({field}={val})")
                            seen_intents.add(intent_name)
        elif stage == "domain" and domain:
            if domain.primary_intent != "unknown":
                evidence.append(f"{domain.primary_intent} (domain)")
            for inferred in domain.all_intents:
                if inferred != domain.primary_intent:
                    evidence.append(f"{inferred} (domain inference)")
        elif stage == "context" and state:
            prev_intent = (state.goals or {}).get("primary", "")
            if prev_intent and prev_intent not in ("unknown", "general", "greeting", "repeat"):
                evidence.append(f"prev_intent={prev_intent}")
            if state.stage:
                evidence.append(f"stage={state.stage.value if hasattr(state.stage, 'value') else state.stage}")
        elif stage == "wording":
            wording_scores = self._wording_intent_evidence(tl)
            for intent, sc in wording_scores.items():
                evidence.append(f"{intent} +{sc} (wording)")
        return evidence

    def _build_winner_reason(
        self, winner: str, post: dict[str, float], pre: dict[str, float],
        breakdown: dict[str, dict[str, float]], conflicts: list[str],
    ) -> str:
        if winner == "unknown":
            return "No intent scored above threshold (0.08)."
        parts: list[str] = []
        parts.append(f"'{winner}' won (score={post.get(winner, 0.0):.3f})")
        wb = breakdown.get(winner, {})
        contributing = [(s, sc) for s, sc in wb.items() if sc > 0]
        if contributing:
            contributing.sort(key=lambda x: -x[1])
            parts.append("contributing stages: " + ", ".join(f"{s}={sc:.3f}" for s, sc in contributing))
        loser_parts: list[str] = []
        for intent, pre_score in sorted(pre.items(), key=lambda x: -x[1]):
            if intent == winner:
                continue
            post_score = post.get(intent, 0.0)
            if post_score < pre_score:
                loser_parts.append(f"'{intent}' dropped {pre_score:.3f}->{post_score:.3f}")
            lb = breakdown.get(intent, {})
            lc = [(s, sc) for s, sc in lb.items() if sc > 0]
            if lc:
                lc_str = ", ".join(f"{s}={sc:.3f}" for s, sc in sorted(lc, key=lambda x: -x[1]))
                loser_parts.append(f"'{intent}' had {lc_str}")
        if loser_parts:
            parts.append("losers: " + "; ".join(loser_parts))
        if conflicts:
            parts.append("conflicts: " + ", ".join(conflicts))
        return ". ".join(parts)

    # ── Diagnostics formatting ────────────────────────────────────────────

    def _format_diagnostics(self, diag: IntentDiagnostics) -> str:
        lines: list[str] = [
            "=" * 60,
            f"Intent Diagnostics: {diag.winner} ({diag.confidence:.3f}) [{diag.confidence_class}]",
            "=" * 60,
        ]
        # Per-stage evidence
        for stage_name in ["keyword", "entity", "domain", "context", "wording", "completeness"]:
            sd = diag.stage_details.get(stage_name)
            if not sd:
                continue
            if not sd.scores and not sd.evidence:
                continue
            lines.append(f"\n  Stage: {stage_name} (weight={diag.stage_weights.get(stage_name, 0):.2f})")
            for intent, score in sorted(sd.scores.items(), key=lambda x: -x[1]):
                lines.append(f"    {intent:<20s} +{score:.2f}")
            for ev in sd.evidence:
                lines.append(f"      └ {ev}")
        # Per-intent breakdown
        lines.append("\n  Weighted Scores:")
        for intent, breakdown in sorted(diag.per_intent_breakdown.items(), key=lambda x: -sum(x[1].values())):
            total = sum(breakdown.values())
            lines.append(f"\n    {intent}")
            for stage, sc in sorted(breakdown.items(), key=lambda x: -x[1]):
                if sc > 0:
                    lines.append(f"      {stage:<15s} {sc:.3f}")
            lines.append(f"      {'':15s} -----")
            lines.append(f"      {'TOTAL':15s} {total:.3f}")
        # Pre vs post conflict
        if diag.pre_conflict != diag.post_conflict:
            lines.append("\n  Conflict Resolution:")
            for intent in sorted(set(list(diag.pre_conflict.keys()) + list(diag.post_conflict.keys()))):
                pre = diag.pre_conflict.get(intent, 0)
                post = diag.post_conflict.get(intent, 0)
                if pre != post:
                    lines.append(f"    {intent:<20s} {pre:.3f} → {post:.3f}")
        # Rankings
        if diag.ranked_intents:
            lines.append(f"\n  Rankings (margin={diag.margin:.3f}, class={diag.confidence_class}):")
            for i, (intent, score) in enumerate(diag.ranked_intents, 1):
                marker = " ← winner" if i == 1 else ""
                lines.append(f"    {i}. {intent:<20s} {score:.3f}{marker}")
        # Winner reason
        lines.append(f"\n  Winner Reason:\n    {diag.winner_reason}")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ── Evidence scoring helpers ─────────────────────────────────────────

    _ENTITY_EVIDENCE: dict[str, list[tuple[str, float]]] = {
        "rank": [("admission", 0.6), ("cutoff", 0.4)],
        "pcm_percentage": [("admission", 0.4)],
        "exam": [("admission", 0.4)],
        "board": [("admission", 0.3)],
        "budget": [("fee", 0.5), ("scholarship", 0.2), ("loan", 0.3)],
        "category": [("admission", 0.3)],
        "interest": [("admission", 0.4)],
        "hostel_required": [("hostel", 0.7)],
        "location": [("distance_education", 0.2), ("contact", 0.1)],
    }

    def _entity_intent_evidence(
        self, text: str, profile: StudentProfile | None,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        if profile is None:
            return scores

        if profile.academic.rank is not None:
            for intent, val in self._ENTITY_EVIDENCE["rank"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.academic.pcm_percentage is not None:
            for intent, val in self._ENTITY_EVIDENCE["pcm_percentage"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.academic.exam:
            for intent, val in self._ENTITY_EVIDENCE["exam"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.academic.board:
            for intent, val in self._ENTITY_EVIDENCE["board"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.personal.budget is not None:
            for intent, val in self._ENTITY_EVIDENCE["budget"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
            if profile.personal.budget <= 200000:
                scores["scholarship"] = max(scores.get("scholarship", 0.0), 0.4)
        if profile.personal.category:
            for intent, val in self._ENTITY_EVIDENCE["category"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
            if profile.personal.category in ("sc", "st", "obc", "ews"):
                scores["scholarship"] = max(scores.get("scholarship", 0.0), 0.4)
        if profile.career.interest:
            for intent, val in self._ENTITY_EVIDENCE["interest"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.personal.hostel_required is True:
            for intent, val in self._ENTITY_EVIDENCE["hostel_required"]:
                scores[intent] = max(scores.get(intent, 0.0), val)
        if profile.personal.location:
            for intent, val in self._ENTITY_EVIDENCE["location"]:
                scores[intent] = max(scores.get(intent, 0.0), val)

        return scores

    _DOMAIN_EVIDENCE: dict[str, dict[str, float]] = {
        "lateral_entry": {"lateral_entry": 0.6, "admission": 0.3},
        "management_quota": {"management_quota": 0.6, "admission": 0.2, "fee": 0.2},
        "sports_quota": {"sports_quota": 0.6, "admission": 0.3},
        "nri": {"nri_admission": 0.6, "admission": 0.2, "fee": 0.2},
        "transfer": {"transfer": 0.6, "admission": 0.2},
        "scholarship": {"scholarship": 0.5, "fee": 0.2},
    }

    def _domain_intent_evidence(
        self, domain: DomainInterpretation | None,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        if domain is None:
            return scores

        for pw, boosts in self._DOMAIN_EVIDENCE.get(domain.pathway, {}).items():
            scores[pw] = max(scores.get(pw, 0.0), boosts)

        for intent in domain.all_intents:
            scores[intent] = max(scores.get(intent, 0.0), 0.5)

        if domain.student_type == "parent":
            scores["contact"] = max(scores.get("contact", 0.0), 0.2)
            scores["safety"] = max(scores.get("safety", 0.0), 0.3)
        elif domain.student_type == "existing":
            scores["grievance"] = max(scores.get("grievance", 0.0), 0.3)

        return scores

    def _context_intent_evidence(
        self, state: ConversationState | None, profile: StudentProfile | None = None,
        tl: str = "",
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        if state is None:
            return scores

        # Boost NRI intent if profile has NRI category (multi-turn context)
        if profile is not None and profile.personal.category.lower() in ("nri", "foreign"):
            scores["nri_admission"] = max(scores.get("nri_admission", 0.0), 0.9)

        # Boost management intent if profile has management category
        if profile is not None and profile.personal.category.lower() == "management":
            scores["management_quota"] = max(scores.get("management_quota", 0.0), 0.9)

        # Multi-turn intent context: boost same intent from previous turn
        prev_intent = (state.goals or {}).get("primary", "")
        if prev_intent and prev_intent not in ("unknown", "general", "greeting", "repeat"):
            scores[prev_intent] = max(scores.get(prev_intent, 0.0), 0.7)

        # Topic continuity: if previous intent was a persistent topic and
        # current text contains keywords for that topic, boost it strongly
        _TOPIC_KEYWORDS = {
            "hostel": r'\b(hostel|room|mess|boarding|dorm|warden|accommodation|security|girl)',
            "fee": r'\b(fee|fees|cost|pay|budget|lakh|tuition|installment|payment)',
            "placement": r'\b(placement|job|package|salary|recruit|company|lpa|ctc|career.*after)',
            "scholarship": r'\b(scholarship|stipend|financial.*aid|merit.*aid)',
            "safety": r'\b(safe|safety|security|ragging|anti.ragg|girl|women|daughter|warden)',
            "career_confusion": r'\b(confused|not\s+sure|dilemma|what.*choose|which.*branch|career.*option|decide)',
            "grievance": r'\b(complaint|grievance|unacceptable|re.?evaluat|issue|problem|mess)',
            "distance_education": r'\b(distance|online.*course|correspondence|blended)',
            "sports_quota": r'\b(sports|athlete|player|cricket|football|state.level|national.*level)',
            "transfer": r'\b(transfer|migration|change.*college|switch.*college|lateral)',
            "loan": r'\b(loan|education.*loan|bank.*loan)',
            "counseling_info": r'\b(counsel|counselling|allotment|choice.*fill|mock.*round)',
        }
        if prev_intent in _TOPIC_KEYWORDS:
            if re.search(_TOPIC_KEYWORDS[prev_intent], tl):
                scores[prev_intent] = max(scores.get(prev_intent, 0.0), 0.85)

        stage = getattr(state, "stage", None)
        if stage is None:
            return scores
        stage_value = stage.value if hasattr(stage, "value") else str(stage)

        stage_scores = {
            "discovery": {"admission": 0.5, "general": 0.2},
            "evaluation": {"department": 0.5, "cutoff": 0.4, "admission": 0.3},
            "decision": {"fee": 0.5, "hostel": 0.6, "placement": 0.5, "scholarship": 0.4},
            "application": {"contact": 0.5, "fee": 0.4},
        }
        for name, boost in stage_scores.get(stage_value, {}).items():
            scores[name] = max(scores.get(name, 0.0), boost)

        return scores

    def _wording_intent_evidence(self, tl: str) -> dict[str, float]:
        scores: dict[str, float] = {}

        if re.search(r'\b(get|got|have|secured|scored)\s+\d+', tl):
            scores['admission'] = max(scores.get('admission', 0.0), 0.3)
        if re.search(r'\b(how much|kitna|koto|cost|spend|pay|kitne|多少钱|concession|kam\s+fees?)', tl):
            scores['fee'] = max(scores.get('fee', 0.0), 0.4)
        if re.search(r'\b(scholarship|stipend|free.?ship|post.?matric|merit.*scholarship)', tl):
            scores['scholarship'] = max(scores.get('scholarship', 0.0), 0.5)
        if re.search(r'\b(room|mess|boarding|dorm|accommodation|abas)', tl):
            scores['hostel'] = max(scores.get('hostel', 0.0), 0.5)
        if re.search(r'\b(recruit|hire|company|ctc|lpa|salary|package)', tl):
            scores['placement'] = max(scores.get('placement', 0.0), 0.5)
        if re.search(r'\b(call|reach|whatsapp|phone|mobile|telephone)', tl):
            scores['contact'] = max(scores.get('contact', 0.0), 0.5)
        if re.search(r'\b(safe|secure|campus|girls?\s*safe|सुरक्षित|সুরক্ষিত|कैंपस)', tl):
            scores['safety'] = max(scores.get('safety', 0.0), 0.6)
        if re.search(r'\b(sports?\s*quota|athlete|player|cricket|football|state.level)', tl):
            scores['sports_quota'] = max(scores.get('sports_quota', 0.0), 0.6)
        if re.search(r'\b(transfer|migration|change\s+college|shift\s+to|switch|easier\s+to\s+get)', tl):
            scores['transfer'] = max(scores.get('transfer', 0.0), 0.6)
        if re.search(r'\b(distance|online.*(?:course|degree|program)|correspondence|university.*best|best.*university)', tl):
            scores['distance_education'] = max(scores.get('distance_education', 0.0), 0.6)
        if re.search(r'\b(re.?evaluat|complaint|grievance|marks.*low|lower.*expect)', tl):
            scores['grievance'] = max(scores.get('grievance', 0.0), 0.5)
        if re.search(r'\b(unacceptable|furious|angry|nobody.*responded|want.*speak.*charge|complete.*mess|terrible)', tl):
            scores['grievance'] = max(scores.get('grievance', 0.0), 0.6)
        if re.search(r'\b(counseling|counselling|document.*need|when.*counsel)', tl):
            scores['counseling_info'] = max(scores.get('counseling_info', 0.0), 0.5)
        if re.search(r'\b(document|marksheet|certificate|10th|12th|provisional|transfer.*certificate|migration.*certificate)', tl):
            scores['document'] = max(scores.get('document', 0.0), 0.4)
        if re.search(r'\b(affiliat|accredit|naac|university|principal|hod|director|dean)', tl):
            scores['institution'] = max(scores.get('institution', 0.0), 0.5)
        if re.search(r'\b(confused|not\s+sure|dilemma|what\s+to\s+(?:choose|do|take)|career|confusion)', tl):
            scores['career_confusion'] = max(scores.get('career_confusion', 0.0), 0.45)
        if re.search(r'(?:decide\s+(?:nahi|nhi|ni)|samajh\s+(?:nahi|nhi|ni)|kaun\s+sa|kya\s+kare|pareshan)', tl):
            scores['career_confusion'] = max(scores.get('career_confusion', 0.0), 0.5)
        if re.search(r'\b(loan|education.*loan|bank.*loan|loan.*amount)', tl):
            scores['loan'] = max(scores.get('loan', 0.0), 0.5)
        if re.search(r'\b(girl|women|girls.*hostel|daughter|beti)', tl):
            scores['safety'] = max(scores.get('safety', 0.0), 0.3)

        return scores

    def _completeness_intent_evidence(
        self, profile: StudentProfile | None,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        if profile is None:
            return scores

        filled = sum([
            1 if profile.academic.rank is not None else 0,
            1 if profile.academic.pcm_percentage is not None else 0,
            1 if profile.career.interest else 0,
            1 if profile.personal.category else 0,
            1 if profile.personal.budget is not None else 0,
            1 if profile.academic.exam else 0,
        ])
        if filled <= 1:
            scores["admission"] = 0.2
        elif filled >= 4:
            scores["fee"] = 0.15
            scores["hostel"] = 0.15
            scores["placement"] = 0.15

        return scores

    def _resolve_intent_conflicts(
        self, scores: dict[str, float], tl: str,
        profile: StudentProfile | None,
        domain: DomainInterpretation | None,
    ) -> dict[str, float]:
        result = dict(scores)

        # "admission" keywords + domain-specific intent → domain wins
        domain_specific = {"lateral_entry", "management_quota", "sports_quota",
                           "nri_admission", "transfer", "scholarship",
                           "distance_education", "counseling_info", "grievance",
                           "career_confusion", "loan", "institution",
                           "hostel", "fee", "placement", "safety"}
        if result.get("admission", 0) > 0:
            for ds in domain_specific:
                if ds in result and result[ds] >= result["admission"] * 0.3:
                    result["admission"] *= 0.4

        # Merge lateral_entry into transfer (granularity fix)
        if "transfer" in result and "lateral_entry" in result:
            result["transfer"] = max(result["transfer"], result["lateral_entry"])
            del result["lateral_entry"]
        elif "lateral_entry" in result and "transfer" not in result:
            result["transfer"] = result.pop("lateral_entry")

        # "hostel" + "fee" → if hostel entity, hostel wins
        if "hostel" in result and "fee" in result:
            if profile and profile.personal.hostel_required is True:
                result["fee"] *= 0.3
            elif re.search(r'\b(accommodation|room\b|mess\b|dorm\b|boarding)', tl):
                result["fee"] *= 0.3

        # "scholarship" + "fee" → if scholarship is much stronger, fee suppressed
        if "scholarship" in result and "fee" in result:
            if result["scholarship"] >= result["fee"] * 0.9:
                result["fee"] *= 0.5

        # "greeting" + meaningful content → remove greeting
        if result.get("greeting", 0) > 0:
            has_meaningful = any(
                result[k] > 0.25 for k in result
                if k not in ("greeting", "unknown", "general")
            )
            if has_meaningful:
                result.pop("greeting", None)

        # "repeat" + other intents → remove repeat
        if result.get("repeat", 0) > 0:
            has_other = any(
                result[k] > 0.2 for k in result
                if k not in ("repeat", "unknown", "general", "greeting")
            )
            if has_other:
                result.pop("repeat", None)

        return result

    def _restore_profile(self, state: ConversationState | None) -> StudentProfile:
        """Restore StudentProfile from conversation state, or start fresh."""
        if state is None:
            return StudentProfile()
        stored = getattr(state, "profile", None) or {}
        if "academic" in stored:
            return StudentProfile.from_dict(stored)
        # Legacy flat profile format — migrate to StudentProfile
        legacy_fields = {"rank", "pcm_percentage", "board", "interest", "category", "budget", "location"}
        if legacy_fields & set(stored.keys()):
            p = StudentProfile()
            if "rank" in stored:
                p.academic.rank = stored["rank"]
            if "pcm_percentage" in stored:
                p.academic.pcm_percentage = stored["pcm_percentage"]
            if "board" in stored:
                p.academic.board = stored["board"]
            if "interest" in stored:
                p.career.interest = stored["interest"]
            if "category" in stored:
                p.personal.category = stored["category"]
            if "budget" in stored:
                p.personal.budget = stored["budget"]
            if "location" in stored:
                p.personal.location = stored["location"]
            return p
        return StudentProfile()

    def _update_profile(self, text: str, profile: StudentProfile) -> StudentProfile:
        """Extract entities from text and fill them into StudentProfile."""

        tl = text.lower().strip()
        if not tl:
            return profile

        # ── Rank extraction ─────────────────────────────────────────────
        rank = self._extract_rank(tl)
        if rank is not None:
            profile.academic.rank = rank

        # ── PCM score extraction ────────────────────────────────────────
        pcm = self._extract_pcm(tl)
        if pcm is not None:
            profile.academic.pcm_percentage = pcm

        # ── Exam / Board extraction ─────────────────────────────────────
        exam = self._extract_exam(tl)
        if exam:
            profile.academic.exam = exam

        board = self._extract_board(tl)
        if board:
            profile.academic.board = board

        # ── Category extraction ─────────────────────────────────────────
        cat = self._extract_category(tl)
        if cat:
            profile.personal.category = cat

        # ── Interest extraction ─────────────────────────────────────────
        interest = self._extract_interest(tl)
        if interest is not None:
            profile.career.interest = interest

        # ── Budget extraction ───────────────────────────────────────────
        budget = self._extract_budget(tl)
        if budget is not None:
            profile.personal.budget = budget

        # ── Hostel extraction ───────────────────────────────────────────
        hostel = self._extract_hostel(tl)
        if hostel is not None:
            profile.personal.hostel_required = hostel

        # ── Current education extraction ────────────────────────────────
        self._extract_current_education(tl, profile)

        # ── Qualification extraction ────────────────────────────────────
        qual = self._extract_qualification(tl)
        if qual:
            profile.academic.qualification = qual

        # ── Location extraction ─────────────────────────────────────────
        loc = self._extract_location(tl)
        if loc:
            profile.personal.location = loc

        # ── Diploma extraction ──────────────────────────────────────────
        dip_pct = self._extract_diploma_pct(tl)
        if dip_pct is not None:
            profile.academic.diploma_percentage = dip_pct
        dip_br = self._extract_diploma_branch(tl)
        if dip_br:
            profile.academic.diploma_branch = dip_br

        return profile

    _RANK_PATTERNS = [
        (r"(?:air|rank|ran|general\s*rank)\s*(?::|is|=)?\s*(\d{1,2}\.\d)\s*lakh", 100000),
        (r"(?:air|rank|ran|general\s*rank)\s*(?::|is|=)?\s*(\d{1,2})\s*lakh", 100000),
        (r"(?:air|rank|ran|general\s*rank)\s*(?::|is|=)?\s*(\d{1,6})\s*k\b", 1000),
        (r"(?:air|rank|ran|general\s*rank)\s*(?::|is|=)?\s*(\d{1,2}(?:,\d{3})+)\b", 1),
        (r"(?:air|rank|ran|general\s*rank)\s*(?::|is|=)?\s*(\d{1,6})", 1),
        (r"(?:around|about|approximately|approx)\s+(\d{1,2}\.\d)\s+lakh", 100000),
        (r"(?:around|about|approximately|approx)\s+(\d{1,2})\s+lakh", 100000),
        (r"(?:around|about|approximately|approx)\s+(\d{1,6})\s*(?:k|thousand)\b", 1000),
        (r"(\d{1,6})\s*(?:k|thousand)\s*(?:rank|air|ran)", 1000),
        (r"(\d{1,6})\s*k\s+\w+\s+rank", 1000),
        (r"(\d{1,2}(?:\.\d)?)\s*lakh\s*(?:rank|air|ran)", 100000),
        (r"rank\s+(?:around|about|approximately|approx|hai|ache|hobe)\s+(\d{1,6})", 1),
        (r"rank\s+(?:around|about|approximately|approx|hai|ache|hobe)\s+(\d{1,2}\.\d)\s*lakh", 100000),
        (r"(\d{1,6})\s*rank\b", 1),
    ]
    _RANK_EXCLUDE_BUDGET = re.compile(r'\b(?:budget|afford|fee|fees|cost|spend)\s', re.IGNORECASE)

    def _extract_rank(self, tl: str) -> int | None:
        # Skip rank extraction in budget/fee contexts
        is_budget_context = bool(self._RANK_EXCLUDE_BUDGET.search(tl))
        for pat, mul in self._RANK_PATTERNS:
            m = re.search(pat, tl)
            if m:
                try:
                    # Skip if this is a budget context (e.g., "around 2 lakh" in "budget is around 2 lakh")
                    if is_budget_context and mul == 100000:
                        val_str = m.group(1).replace(",", "").strip()
                        if all(c.isdigit() or c == '.' for c in val_str):
                            val = float(val_str)
                            if val <= 50:  # Budget amounts like 2, 5, 10 lakh
                                continue
                    val = m.group(1).replace(",", "").strip()
                    if "." in val:
                        return int(float(val) * mul)
                    return int(val) * mul
                except (ValueError, IndexError):
                    pass
        return None

    _PCM_PATTERNS = [
        r"(?:pcm|physics\s*(?:and|&)?\s*chemistry|aggregate)\s*(?::|is|=)?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:pcm|marks|aggregate|percent)",
        r"(?:scored|got|secured|have|obtained)\s+(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|marks)?\s*(?:in\s*)?(?:pcm|science|physics\s*(?:and|&)?\s*chemistry)",
        r"(?:pcm|physics chemistry maths|physics chemistry)\s*(?:marks|score|aggregate)?\s*(?::|is|=)?\s*(\d{1,3}(?:\.\d+)?)",
        r"(\d{1,3}(?:\.\d+)?)\s*(?:pcm|percent|percentage)\b",
    ]

    def _extract_pcm(self, tl: str) -> float | None:
        for pat in self._PCM_PATTERNS:
            m = re.search(pat, tl)
            if m:
                try:
                    val = float(m.group(1))
                    if 0 <= val <= 100:
                        return val
                except ValueError:
                    pass
        # word numbers
        word_map = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
            "twenty one": 21, "twenty two": 22, "twenty three": 23, "twenty four": 24,
            "twenty five": 25, "twenty six": 26, "twenty seven": 27, "twenty eight": 28,
            "twenty nine": 29, "thirty": 30, "thirty one": 31, "thirty two": 32,
            "thirty three": 33, "thirty four": 34, "thirty five": 35, "thirty six": 36,
            "thirty seven": 37, "thirty eight": 38, "thirty nine": 39, "forty": 40,
            "forty one": 41, "forty two": 42, "forty three": 43, "forty four": 44,
            "forty five": 45, "forty six": 46, "forty seven": 47, "forty eight": 48,
            "forty nine": 49, "fifty": 50, "fifty one": 51, "fifty two": 52,
            "fifty three": 53, "fifty four": 54, "fifty five": 55, "fifty six": 56,
            "fifty seven": 57, "fifty eight": 58, "fifty nine": 59, "sixty": 60,
            "sixty one": 61, "sixty two": 62, "sixty three": 63, "sixty four": 64,
            "sixty five": 65, "sixty six": 66, "sixty seven": 67, "sixty eight": 68,
            "sixty nine": 69, "seventy": 70, "seventy one": 71, "seventy two": 72,
            "seventy three": 73, "seventy four": 74, "seventy five": 75, "seventy six": 76,
            "seventy seven": 77, "seventy eight": 78, "seventy nine": 79, "eighty": 80,
            "eighty one": 81, "eighty two": 82, "eighty three": 83, "eighty four": 84,
            "eighty five": 85, "eighty six": 86, "eighty seven": 87, "eighty eight": 88,
            "eighty nine": 89, "ninety": 90, "ninety one": 91, "ninety two": 92,
            "ninety three": 93, "ninety four": 94, "ninety five": 95, "ninety six": 96,
            "ninety seven": 97, "ninety eight": 98, "ninety nine": 99, "hundred": 100,
        }
        m = re.search(r"(?:pcm|physics\s*(?:and|&)?\s*chemistry|aggregate)\s+(?:is|=|:)?\s*(?:eighty two|eighty|seventy|ninety|fifty|\w+(?:\s+\w+)?)", tl)
        if not m:
            m = re.search(r"(?:my\s+)?pcm\s+(?:is|=|:)?\s*(\w+(?:\s+\w+)?)", tl)
        if m:
            phrase = m.group(0)
            for w, n in sorted(word_map.items(), key=lambda x: -len(x[0])):
                if w in phrase:
                    return float(n)
        return None

    _EXAM_PATTERNS = {
        "wbjee": [r"\bwb\s*jee\b", r"\bwbjee\b", r"west\s*bengal\s*jee\b"],
        "jee_main": [r"\bjee\s*(?:main|mains)\b", r"\bjee\b(?!\s*(?:advanced|advance))"],
        "jee_advanced": [r"\bjee\s*(?:advanced|advance)\b", r"\bjee\s*adv\b"],
        "jelet": [r"\bjelet\b"],
        "jexpo": [r"\bjexpo\b"],
        "nata": [r"\bnata\b"],
        "cuet": [r"\bcuet\b"],
        "diploma": [r"\bdiploma\b(?!.*(?:engineering|b\.?\s*tech|bachelor))"],
    }

    def _extract_exam(self, tl: str) -> str:
        for exam, patterns in self._EXAM_PATTERNS.items():
            for p in patterns:
                if re.search(p, tl):
                    return exam
        return ""

    _BOARD_PATTERNS = [
        (r"\bwbchse\b", "WBCHSE"),
        (r"\bwest\s*bengal\s*board\b", "WBCHSE"),
        (r"\bbengal\s*board\b", "WBCHSE"),
        (r"\bcbse\b", "CBSE"),
        (r"\bcentral\s*board\b", "CBSE"),
        (r"\bicse\b", "ICSE"),
        (r"\bisc\b", "ISC"),
        (r"\bstate\s*board\b", "State Board"),
    ]

    def _extract_board(self, tl: str) -> str:
        for pat, name in self._BOARD_PATTERNS:
            if re.search(pat, tl):
                return name
        return ""

    _CATEGORY_PATTERNS = [
        (r"\b(general|gen(?!u|e|d))\b", "general"),
        (r"\bur\b", "general"),
        (r"\bunreserved\b", "general"),
        (r"\bobc[-\s]?[ab]\b", "obc"),
        (r"\bobc\b", "obc"),
        (r"\bsc\b", "sc"),
        (r"\bst\b", "st"),
        (r"\bews\b", "ews"),
        (r"\bpwd\b", "pwd"),
        (r"\bnri\b", "nri"),
        (r"\btfw\b", "tfw"),
    ]

    def _extract_category(self, tl: str) -> str:
        for pat, norm in self._CATEGORY_PATTERNS:
            m = re.search(pat, tl)
            if m:
                raw = m.group(1) if m.lastgroup else m.group(0)
                raw = raw.lower().strip().replace(" ", "").replace("-", "")
                # normalize OBC variants
                if raw.startswith("obc"):
                    return "obc"
                return norm
        return ""

    _INTEREST_MAP: list[tuple[list[str], str]] = [
        (["ai", "artificial intelligence", "ai ml", "a i", "ai and ml", "aiml"], "AI"),
        (["cse", "computer science", "computer", "computer since", "cs"], "CSE"),
        (["ece", "electronics", "electronics and communication", "electronics & communication", "e and c", "ec"], "ECE"),
        (["ee", "electrical", "electrical engineering", "electrical engg"], "EE"),
        (["me", "mechanical", "mechanical engineering", "machanical", "mechanical engg"], "ME"),
        (["ce", "civil", "civil engineering", "civil engg"], "CE"),
        (["biotechnology", "bio tech", "biotech", "bio technology"], "Biotechnology"),
        (["data science", "data science", "data analytics"], "Data Science"),
        (["cyber security", "cybersecurity", "cyber"], "Cyber Security"),
        (["iot", "internet of things"], "IoT"),
        (["robotics", "robot"], "Robotics"),
        (["anthropology"], "Anthropology"),
        (["it", "information technology"], "IT"),
        (["ai ml", "machine learning"], "AI"),
    ]

    def _extract_interest(self, tl: str) -> str | None:
        unsure = r"(?:don'?t\s*know|not\s*sure|confused|open\s*to\s*anything|no\s*idea|kuch\s*samajh|kuch\s*pata|ki\s*korbo|ki\s*pora|jana\s*na)"
        if re.search(unsure, tl):
            return None

        # Map each canonical interest to a compiled regex
        interest_regexes: list[tuple[re.Pattern, str]] = []
        for keywords, canonical in self._INTEREST_MAP:
            pattern = "|".join(
                rf"\b{re.escape(kw)}\b" if len(kw) <= 4 else re.escape(kw)
                for kw in keywords
            )
            interest_regexes.append((re.compile(pattern, re.IGNORECASE), canonical))

        for pat, canonical in interest_regexes:
            if pat.search(tl):
                return canonical

        return None

    _BUDGET_PATTERNS = [
        (r"(?:budget|afford|fee|fees|financial|cost)\s*(?::|is|=)?\s*(?:around|about|below|under|nearly|~)?\s*(?:rs\.?\s*|₹\s*)?(\d+(?:\.\d+)?)\s*(lakh|lac|l)", "lakh"),
        (r"(?:budget|afford|fee|fees)\s*(?::|is|=)?\s*(?:around|about|below|under|nearly|~)?\s*(?:rs\.?\s*|₹\s*)?(\d+(?:\.\d+)?)\s*(k|thousand)", "thousand"),
        (r"(?:rs\.?\s*|₹\s*)?(\d+(?:\.\d+)?)\s*(lakh|lac|l)\s*(?:budget|afford|fee|fees)", "lakh"),
        (r"under\s+(\d+)\s*(lakh|lac|l)", "lakh"),
        (r"below\s+(\d+)\s*(lakh|lac|l)", "lakh"),
        (r"(?:budget|afford|fee|fees)\s*(?::|is|=)?\s*(?:rs\.?\s*|₹\s*)?(\d+(?:,\d{3})*)", "raw"),
    ]

    def _extract_budget(self, tl: str) -> float | None:
        for pat, unit in self._BUDGET_PATTERNS:
            m = re.search(pat, tl)
            if m:
                try:
                    val_str = m.group(1).replace(",", "")
                    val = float(val_str)
                    if unit == "lakh":
                        return val * 100000
                    elif unit == "thousand":
                        return val * 1000
                    else:
                        return val
                except (ValueError, IndexError):
                    pass
        # Check for budget keywords without explicit numbers
        budget_keywords = [
            r"\blow\s*budget\b",
            r"\bmiddle\s*class\b",
            r"\bcannot\s*afford\b",
            r"\bexpensive\b",
            r"\bbudget\s*(?:is\s*)?tight\b",
            r"\blimited\s*budget\b",
            r"\bloan\s*needed\b",
            r"\beducation\s*loan\b",
            r"\bscholarship\s*needed\b",
            r"\bscholarship\s*chai\b",
            r"\bafford\s*korte\s*parbe\s*na\b",
            r"\bbudget\s*(?:kom|kum|kam)\b",
        ]
        for pat in budget_keywords:
            if re.search(pat, tl):
                return 0.0  # signal low budget
        return None

    _HOSTEL_PATTERNS_TRUE = [
        r"\bhostel\s*(?:need|required|chai|lagbe|dorkar|required|chaie|chahiye)\b",
        r"\bneed\s*hostel\b",
        r"\bgirls?\s*hostel\b",
        r"\bboys?\s*hostel\b",
        r"\bhostel\s*(?:accommodation|facility|facilities)\b",
        r"\b(?:coming|come|from|arriving)\s+(?:from\s+)?(?:bihar|assam|up|delhi|rajasthan|mp|jharkhand|odisha|outside|distant|far)\b",
        r"\bfar\s*(?:away|from)\b",
        r"\b(?:live|lives|stay|staying|living)\s+(?:far|distant|away)\b",
        r"\b(?:accommodation|boarding|mess)\s+(?:need|required|chai)\b",
        r"\bneed\s+(?:accommodation|boarding|mess)\b",
        r"\bhostel\s+lagbe\b",
        r"\babas\w*\s+lag\w*\b",
    ]

    _HOSTEL_PATTERNS_FALSE = [
        r"\bday\s*scholar\b",
        r"\bhostel\s*(?:nhi|nahi|na)\b",
        r"\b(?:no|don'?t\s*need|not\s*need)\s*hostel\b",
    ]

    def _extract_hostel(self, tl: str) -> bool | None:
        for pat in self._HOSTEL_PATTERNS_FALSE:
            if re.search(pat, tl):
                return False
        for pat in self._HOSTEL_PATTERNS_TRUE:
            if re.search(pat, tl):
                return True
        return None

    def _extract_current_education(self, tl: str, profile: StudentProfile) -> None:
        # Current year
        year_map = {
            "1st": 1, "first": 1, "2nd": 2, "second": 2,
            "3rd": 3, "third": 3, "4th": 4, "fourth": 4,
        }
        for word, num in year_map.items():
            if re.search(rf"\b{word}\s*(?:year|semester|sem|saal|yearly|yr)\b", tl):
                profile.academic.current_year = num
                break

        # Current branch
        for keywords, canonical in self._INTEREST_MAP:
            for kw in keywords:
                m = re.search(rf"(?:studying|pursuing|doing|currently|reading|por\w*)\s+(?:in|at|of)?\s*{re.escape(kw)}", tl)
                if m:
                    profile.academic.current_branch = canonical
                    break
            if profile.academic.current_branch:
                break

        # Current college type
        if re.search(r"\bprivate\s*college\b", tl):
            profile.academic.current_college = "private"
        elif re.search(r"\bgovernment\s*college\b", tl):
            profile.academic.current_college = "government"

    _QUALIFICATION_PATTERNS = [
        (r"\bdiploma\b(?!\s*(?:holder|exam|percentage))", "diploma"),
        (r"\bb\.?\s*tech\b", "bachelor"),
        (r"\bbe\b", "bachelor"),
        (r"\bbachelor\b", "bachelor"),
        (r"\bgraduation\b", "bachelor"),
        (r"\b12th\b", "12th"),
        (r"\b12\s*(?:th|th\s*std|th\s*class|th\s*grade|standard)\b", "12th"),
        (r"\bhsc\b", "12th"),
        (r"\bhigher\s*secondary\b", "12th"),
        (r"\bintermediate\b", "12th"),
        (r"\b10th\b", "10th"),
        (r"\b10\s*(?:th|th\s*std|th\s*class)\b", "10th"),
        (r"\bssc\b", "10th"),
        (r"\bmatric\b", "10th"),
        (r"\bpost\s*graduate\b", "postgraduate"),
        (r"\bpg\b", "postgraduate"),
        (r"\bmaster\b", "postgraduate"),
        (r"\bm\.?\s*tech\b", "postgraduate"),
        (r"\bph\.?\s*d\b", "doctorate"),
    ]

    def _extract_qualification(self, tl: str) -> str:
        for pat, qual in self._QUALIFICATION_PATTERNS:
            if re.search(pat, tl):
                return qual
        return ""

    _LOCATION_PATTERNS = [
        (r"\bwest\s*bengal\b", "west bengal"),
        (r"\bbengal\b", "west bengal"),
        (r"\bkolkata\b", "kolkata"),
        (r"\bhowrah\b", "howrah"),
        (r"\bhooghly\b", "hooghly"),
        (r"\bnadia\b", "nadia"),
        (r"\bnorth\s*24\b", "north 24 parganas"),
        (r"\bsouth\s*24\b", "south 24 parganas"),
        (r"\boutside\s*bengal\b", "outside west bengal"),
        (r"\bother\s*state\b", "outside west bengal"),
        (r"\bbihar\b", "bihar"),
        (r"\bassam\b", "assam"),
        (r"\bdelhi\b", "delhi"),
        (r"\bup\b", "uttar pradesh"),
        (r"\b(?:rajasthan|rajasthan)\b", "rajasthan"),
    ]

    def _extract_location(self, tl: str) -> str:
        for pat, loc in self._LOCATION_PATTERNS:
            if re.search(pat, tl):
                return loc
        return ""

    _DIPLOMA_PCT_PATTERNS = [
        r"(?:diploma|polytechnic)\s*(?:marks|percentage|percent|score|pct|with|of)\s*(?::|is|=)?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:marks|score)?\s*(?:in\s*)?(?:diploma|polytechnic)",
    ]

    def _extract_diploma_pct(self, tl: str) -> float | None:
        for pat in self._DIPLOMA_PCT_PATTERNS:
            m = re.search(pat, tl)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    _DIPLOMA_BRANCH_PATTERNS = [
        (r"\bdiploma\s*(?:in|of)\s+(\w+)", True),
        (r"\bdiploma\s+(\w+)\s*(?:branch|engineering|engg)", True),
    ]

    def _extract_diploma_branch(self, tl: str) -> str:
        for pat, _ in self._DIPLOMA_BRANCH_PATTERNS:
            m = re.search(pat, tl)
            if m:
                raw = m.group(1).lower()
                for keywords, canonical in self._INTEREST_MAP:
                    for kw in keywords:
                        if raw == kw or raw.startswith(kw):
                            return canonical
        return ""

    def _detect_signals(
        self,
        text: str,
        intent: UnderstandingIntent | None = None,
        profile: StudentProfile | None = None,
    ) -> ConversationSignals:
        tl = text.lower()
        signals = ConversationSignals()

        for signal_name, patterns in _SIGNAL_PATTERNS.items():
            score = self._score_signal(tl, signal_name, patterns)
            setattr(signals, signal_name, score)

        signals = self._apply_intent_boost(signals, intent)
        signals = self._apply_profile_boost(signals, profile, tl)

        if self._prev_signals is not None:
            signals = self._apply_cross_turn_persistence(signals, self._prev_signals)

        self._prev_signals = signals
        return signals

    def _is_negated(self, tl: str, match_start: int, window: int = 40) -> bool:
        start = max(0, match_start - window)
        before = tl[start:match_start]
        if not before.strip():
            return False
        return bool(_NEGATION_PREFIX_RE.search(before))

    def _ensure_ascii_boundary(self, pattern: str) -> str:
        if all(ord(c) < 128 for c in pattern):
            return pattern
        return pattern.replace(r'\b', '')

    def _score_signal(
        self, tl: str, signal_name: str, patterns: list[tuple[str, float]]
    ) -> float:
        score = 0.0
        for pattern, weight in patterns:
            pat = self._ensure_ascii_boundary(pattern)
            for m in re.finditer(pat, tl):
                if not self._is_negated(tl, m.start()):
                    score += weight
        return min(1.0, score)

    def _apply_intent_boost(
        self, signals: ConversationSignals, intent: UnderstandingIntent | None
    ) -> ConversationSignals:
        if intent is None or intent.primary == "unknown":
            return signals
        boosts = _INTENT_SIGNAL_BOOSTS.get(intent.primary, {})
        for sig_name, boost in boosts.items():
            current = getattr(signals, sig_name, 0.0)
            if current > 0.0:
                setattr(signals, sig_name, min(1.0, current + boost))
        return signals

    def _apply_profile_boost(
        self,
        signals: ConversationSignals,
        profile: StudentProfile | None,
        tl: str,
    ) -> ConversationSignals:
        if profile is None:
            return signals

        has_uncertainty = bool(re.search(r'(?:confused|not\s+sure|don\'?t\s*know|pata\s+nahi|samajh\s+nahi|kya\s+kar)', tl))

        if profile.academic.rank is None and has_uncertainty:
            signals.confusion = min(1.0, signals.confusion + 0.15)

        if profile.academic.pcm_percentage is None and has_uncertainty:
            signals.confusion = min(1.0, signals.confusion + 0.1)

        if profile.career.interest == "" and has_uncertainty:
            signals.confusion = min(1.0, signals.confusion + 0.1)

        budget = profile.personal.budget
        if budget is not None and budget <= 50000:
            signals.financial_concern = min(1.0, signals.financial_concern + 0.2)
        elif budget is not None and budget <= 200000:
            signals.financial_concern = min(1.0, signals.financial_concern + 0.1)

        if re.search(r'\blow\s+budget\b|\btight\s+budget\b|\bcannot\s+afford\b|\bloan\s+needed\b|\beducation\s+loan\b|\bscholarship\s+needed\b', tl):
            signals.financial_concern = max(signals.financial_concern, 0.35)

        if profile.personal.hostel_required is True:
            signals.anxiety = min(1.0, signals.anxiety + 0.1)

        return signals

    def _apply_cross_turn_persistence(
        self,
        signals: ConversationSignals,
        prev: ConversationSignals,
    ) -> ConversationSignals:
        decay = 0.5
        for sig_name in ("anxiety", "confusion", "urgency", "frustration", "financial_concern"):
            prev_val = getattr(prev, sig_name, 0.0)
            curr_val = getattr(signals, sig_name, 0.0)
            if prev_val >= 0.6:
                carry = prev_val * decay
            elif prev_val >= 0.4:
                carry = prev_val * 0.35
            else:
                carry = prev_val * 0.15
            setattr(signals, sig_name, min(1.0, curr_val + carry))
        return signals

    def _compute_missing_from_profile(
        self, profile: StudentProfile,
    ) -> MissingInformation:
        """Fully deterministic — missing info = pathway required fields not yet set."""
        items = compute_missing(profile)
        return MissingInformation(items=items)

    def _detect_references(self, text: str) -> bool:
        return bool(re.search(
            r"\b(it|that|this|they|there|those|such|them|its|their|"
            r"yeah|okay|ok|hmm|um|uh|acha|accha|thik|theek)\b",
            text.lower(),
        ))

    def _score_confidence(
        self,
        text: str,
        profile: StudentProfile,
        intent: UnderstandingIntent,
    ) -> float:
        score = 0.3
        if len(text) > 5:
            score += 0.1
        if intent.confidence > 0:
            score += 0.2

        # Count how many profile sections have at least one field set
        filled = 0
        if not profile.academic.is_empty:
            filled += 1
        if not profile.personal.is_empty:
            filled += 1
        if not profile.career.is_empty:
            filled += 1
        score += min(0.4, filled * 0.15)
        return min(1.0, score)
