#!/usr/bin/env python3
"""
generate_kb.py — Generates combined_kb.json from knowledge_base.json

This script:
1. Reads knowledge_base.json (flat, clean single source of truth)
2. Generates voice_ready_answers (trilingual natural language answers)
3. Generates quick_answers (text summaries for common queries)
4. Writes combined_kb.json (runtime format used by the agent)

Usage:
    python scripts/generate_kb.py                  # Generate combined_kb.json
    python scripts/generate_kb.py --validate       # Validate without writing
"""

import json
import sys
from pathlib import Path
from datetime import datetime

INPUT_PATH = Path("backend/data/knowledge_base.json")
OUTPUT_PATH = Path("backend/data/knowledge_base/combined_kb.json")
ALL_DEPARTMENTS = ["CSE", "IT", "ECE", "EE", "ME", "CE", "CSD", "AIML", "DS", "CY", "MBA", "MCA"]


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Written: {path} ({len(json.dumps(data))} bytes)")


def number_to_en(num):
    """Convert a number to English words for TTS-friendly output."""
    if num is None:
        return ""
    try:
        n = int(float(num))
    except (ValueError, TypeError):
        return str(num)
    if n < 0:
        return f"minus {number_to_en(-n)}"

    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = [
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    if n < 10:
        return units[n]
    if n < 20:
        return teens[n - 10]
    if n < 100:
        return tens[n // 10] + (" " + units[n % 10] if n % 10 else "")
    if n < 1000:
        return units[n // 100] + " hundred" + (" " + number_to_en(n % 100) if n % 100 else "")

    # Indian numbering: lakh (100k), crore (10M)
    if n < 100000:
        return (
            number_to_en(n // 1000)
            + " thousand"
            + (" " + number_to_en(n % 1000) if n % 1000 else "")
        )
    if n < 10000000:
        return (
            number_to_en(n // 100000)
            + " lakh"
            + (" " + number_to_en(n % 100000) if n % 100000 else "")
        )
    return (
        number_to_en(n // 10000000)
        + " crore"
        + (" " + number_to_en(n % 10000000) if n % 10000000 else "")
    )


def format_fee_en(amount):
    """Format a fee amount as English words for TTS."""
    if isinstance(amount, str):
        return amount
    in_words = number_to_en(amount)
    return f"{in_words} rupees"


def generate_voice_answers(data):
    """Generate voice_ready_answers from KB data."""
    courses = data.get("courses", {})
    college = data.get("college", {})
    placements = data.get("placements", {})
    hostel = data.get("hostel", {})
    admission = data.get("admission", {})
    infrastructure = data.get("infrastructure", {})
    scholarships = data.get("scholarships", {})
    student_life = data.get("student_life", {})
    academics = data.get("academics", {})
    depts_raw = data.get("departments", {})
    anti_ragging = data.get("anti_ragging", {})
    principal_data = data.get("principal", {})
    vp_data = data.get("vice_principal", {})

    # Build HOD sub_answers
    hod_sub = {}
    depts = depts_raw
    for code in ALL_DEPARTMENTS:
        dept = depts.get(code, {})
        hod = dept.get("hod", {})
        name = hod.get("name", "")
        code_lower = code.lower()
        if name:
            hod_sub[code_lower] = {
                "semantic_anchor": f"department_head {code} faculty_leadership",
                "keywords": [code_lower],
                "answers": {
                    "en": f"The Head of the {code} department is {name}.",
                    "hi": f"{code} विभाग के अध्यक्ष {name} हैं।",
                    "bn": f"{code} বিভাগের প্রধান হলেন {name}।",
                },
            }

    hod_sub["default"] = {
        "answers": {
            "en": "Could you please specify which department's HOD you are looking for? We have CSE, IT, ECE, EE, MCA, MBA, and other departments.",
            "hi": "कृपया स्पष्ट करें कि आप किस विभाग के एचओडी की तलाश कर रहे हैं? हमारे पास सीएसई, आईटी, ईसीई, ईई, एमसीए, एमबीए और अन्य विभाग हैं।",
            "bn": "দয়া করে নির্দিষ্ট করুন আপনি কোন বিভাগের এইচওডির খোঁজ করছেন? আমাদের সিএসই, আইটি, ইসিই, ইই, এমসিএ, এমবিএ এবং অন্যান্য বিভাগ রয়েছে।",
        }
    }

    # Fee data
    btech = courses.get("btech", {})
    cse_fee_total = btech.get("CSE", {}).get("fees", {}).get("total", "6,04,700")
    cse_fee_adm = btech.get("CSE", {}).get("fees", {}).get("admission", "98,225")
    mba_fee = courses.get("mba", {}).get("fees", {})
    mca_fee = courses.get("mca", {}).get("fees", {})

    answers = {
        "fees": {
            "semantic_anchor": "fee_structure tuition_cost admission_fees",
            "keywords": ["fee", "fees", "फीस", "ফি", "शुल्क", "শুল্ক", "cost", "price", "खर्च", "খরচ"],
            "cse_it_ece": {
                "semantic_anchor": "fee_structure CSE_IT_ECE tuition admission_cost",
                "en": f"B.Tech CSE, IT, and ECE total fee is {format_fee_en(cse_fee_total)}. Admission fee is {format_fee_en(cse_fee_adm)}.",
                "hi": f"बी.टेक सीएसई, आईटी, और ईसीई की कुल फीस {number_to_en(cse_fee_total)} रुपये है। एडमिशन फीस {number_to_en(cse_fee_adm)} रुपये है।",
                "bn": f"বি.টেক সিএসই, আইটি, এবং ইসিই এর মোট ফি {number_to_en(cse_fee_total)} টাকা। ভর্তি ফি {number_to_en(cse_fee_adm)} টাকা।",
            },
            "ee_aiml_ds_cy_csd": {
                "semantic_anchor": "fee_structure EE_AIML_DS_Cyber_CSD tuition admission_cost",
                "en": f"B.Tech EE, AI-ML, Data Science, Cyber Security, and CS Design total fee is {format_fee_en(554100)}. Admission fee is {format_fee_en(91900)}.",
                "hi": f"बी.टेक ईई, एआई-एमएल, डाटा साइंस, साइबर सिक्योरिटी, और सीएस डिज़ाइन की कुल फीस {number_to_en(554100)} रुपये है। एडमिशन फीस {number_to_en(91900)} रुपये है।",
                "bn": f"বি.টেক ইই, এআই-এমএল, ডাটা সায়েন্স, সাইবার সিকিউরিটি, এবং সিএস ডিজাইন এর মোট ফি {number_to_en(554100)} টাকা। ভর্তি ফি {number_to_en(91900)} টাকা।",
            },
            "me_ce": {
                "semantic_anchor": "fee_structure ME_CE tuition admission_cost",
                "en": f"B.Tech Mechanical and Civil total fee is {format_fee_en(444100)}. Admission fee is {format_fee_en(78150)}.",
                "hi": f"बी.टेक मैकेनिकल और सिविल की कुल फीस {number_to_en(444100)} रुपये है। एडमिशन फीस {number_to_en(78150)} रुपये है।",
                "bn": f"বি.টেক মেকানিক্যাল এবং সিভিল এর মোট ফি {number_to_en(444100)} টাকা। ভর্তি ফি {number_to_en(78150)} টাকা।",
            },
            "mba": {
                "semantic_anchor": "fee_structure MBA tuition admission_cost",
                "en": f"MBA total fee is {format_fee_en(mba_fee.get('total', 419200))}. Admission fee is {format_fee_en(mba_fee.get('admission', 121400))}.",
                "hi": f"एमबीए की कुल फीस {number_to_en(mba_fee.get('total', 419200))} रुपये है। एडमिशन फीस {number_to_en(mba_fee.get('admission', 121400))} रुपये है।",
                "bn": f"এমবিএ এর মোট ফি {number_to_en(mba_fee.get('total', 419200))} টাকা। ভর্তি ফি {number_to_en(mba_fee.get('admission', 121400))} টাকা।",
            },
            "mca": {
                "semantic_anchor": "fee_structure MCA tuition admission_cost",
                "en": f"MCA total fee is {format_fee_en(mca_fee.get('total', 208800))}. Admission fee is {format_fee_en(mca_fee.get('admission', 67200))}.",
                "hi": f"एमसीए की कुल फीस {number_to_en(mca_fee.get('total', 208800))} रुपये है। एडमिशन फीस {number_to_en(mca_fee.get('admission', 67200))} रुपये है।",
                "bn": f"এমসিএ এর মোট ফি {number_to_en(mca_fee.get('total', 208800))} টাকা। ভর্তি ফি {number_to_en(mca_fee.get('admission', 67200))} টাকা।",
            },
        },
        "principal": {
            "semantic_anchor": "principal_office chief_executive top_management",
            "keywords": ["principal", "प्रिंसिपल", "প্রিন্সিপাল", "প্রধান", "head of college", "অধ্যক্ষ"],
            "answers": {
                "en": f"The principal of BCREC is {principal_data.get('name', 'Dr. Sanjay S. Pawar')}.",
                "hi": f"बीसीआरईसी के प्रिंसिपल {principal_data.get('name_hi', principal_data.get('name', 'डॉ. संजय एस. पवार'))} हैं।",
                "bn": f"বিসিআরইসি এর প্রিন্সিপাল হলেন {principal_data.get('name_bn', principal_data.get('name', 'ড. সঞ্জয় এস পাওয়ার'))}।",
            },
        },
        "vice_principal": {
            "semantic_anchor": "administrative_head college_vice_principal deputy_leadership",
            "keywords": [
                "vice principal",
                "vice-principal",
                "up-principal",
                "deputy principal",
                "উপ-প্রিন্সিপাল",
                "उप-प्रिंसिपल",
            ],
            "answers": {
                "en": f"The Vice Principal of BCREC is {vp_data.get('name', 'Prof. (Dr.) K. M. Hossain')}.",
                "hi": f"बीसीआरईसी के उप-प्रिंसिपल {vp_data.get('name_hi', vp_data.get('name', 'प्रो. (डॉ.) के. एम. होसैन'))} हैं।",
                "bn": f"বিসিআরইসি এর উপ-প্রিন্সিপাল হলেন {vp_data.get('name_bn', vp_data.get('name', 'প্রো. (ড.) কে. এম. হোসেন'))}।",
            },
        },
        "hod": {
            "semantic_anchor": "department_head faculty_leadership HoD",
            "keywords": ["hod", "head of department", "विभाग अध्यक्ष", "বিভাগীয় প্রধান", "হোড"],
            "sub_answers": hod_sub,
        },
        "hostel": {
            "semantic_anchor": "accommodation hostel_mess student_housing facilities",
            "keywords": ["hostel", "हॉस्टल", "হস্টেল", "mess", "food", "खाना", "খাবার"],
            "answers": {
                "en": f"Hostel is optional, not compulsory. Single bed room costs thirty thousand rupees per semester. Double or triple bed room costs ten thousand rupees per semester. Mess food charges are five thousand rupees per month. Four meals are served daily including non-veg three to four days a week.",
                "hi": "हॉस्टल वैकल्पिक है, अनिवार्य नहीं। सिंगल बेड रूम की फीस तीस हज़ार रुपये प्रति सेमेस्टर है। डबल या ट्रिपल बेड रूम दस हज़ार रुपये प्रति सेमेस्टर है। मेस का खाना पाँच हज़ार रुपये प्रति महीना है। रोज़ चार बार खाना मिलता है, हफ्ते में तीन-चार दिन नॉन-वेज मिलता है।",
                "bn": "হোস্টেল ঐচ্ছিক, বাধ্যতামূলক নয়। সিঙ্গেল বেড রুমের ভাড়া ত্রিশ হাজার টাকা প্রতি সেমিস্টার। ডাবল বা ট্রিপল বেড রুম দশ হাজার টাকা প্রতি সেমিস্টার। মেসের খাবার পাঁচ হাজার টাকা প্রতি মাস। প্রতিদিন চারবেলা খাবার দেওয়া হয়, সপ্তাহে তিন-চারদিন মাংস বা মাছ থাকে।",
            },
        },
        "placement": {
            "semantic_anchor": "career placement_job recruitment company package",
            "keywords": [
                "placement",
                "प्लेसमेंट",
                "প্লেসমেন্ট",
                "company",
                "recruit",
                "package",
                "salary",
            ],
            "answers": {
                "en": f"BCREC has {placements.get('overall_rate_2025', '91')} percent overall placement rate. CSE placement rate is {placements.get('cse_rate_2025', '93.6')} percent. Highest package is {format_fee_en(placements.get('highest_package', {}).get('amount', 7.0))} per annum. Median package is {placements.get('median_package', 'Rs. 4.25 LPA')}. Top recruiters include TCS, Infosys, Wipro, Capgemini, and HCL.",
                "hi": f"बीसीआरईसी की समग्र प्लेसमेंट दर {placements.get('overall_rate_2025', '91')} प्रतिशत है। सीएसई प्लेसमेंट दर {placements.get('cse_rate_2025', '93.6')} प्रतिशत है। सबसे अधिक पैकेज {number_to_en(placements.get('highest_package', {}).get('amount', 7) * 100000)} रुपये प्रति वर्ष है। प्रमुख भर्तीकर्ताओं में टीसीएस, इंफोसिस, विप्रो, कैपजेमिनी और एचसीएल शामिल हैं।",
                "bn": f"বিসিআরইসি এর সামগ্রিক প্লেসমেন্ট রেট {placements.get('overall_rate_2025', '91')} শতাংশ। সিএসই প্লেসমেন্ট রেট {placements.get('cse_rate_2025', '93.6')} শতাংশ। প্রধান নিয়োগকারীদের মধ্যে রয়েছে টিসিএস, ইনফোসিস, উইপ্রো, ক্যাপজেমিনি এবং এইচসিএল।",
            },
        },
        "courses": {
            "semantic_anchor": "academic_programs branches degrees majors specializations",
            "keywords": [
                "course",
                "branch",
                "btech",
                "program",
                "कोर्स",
                "শাখা",
                "internship",
                "branch change",
            ],
            "answers": {
                "en": "BCREC offers B.Tech in CSE, CSE with AI ML, CSE with Data Science, CS and Design, IT, ECE, EE, ME, CE, and Cyber Security. Also offers MCA, MBA, and M.Tech programs. Branch change is allowed after the first year subject to academic criteria and availability.",
                "hi": "बीसीआरईसी बी.टेक सीएसई, सीएसई एआई एमएल, सीएसई डेटा साइंस, सीएस डिजाइन, आईटी, ईसीई, ईई, एमई, सीई, और साइबर सिक्योरिटी में प्रदान करता है। एमसीए, एमबीए और एम.टेक प्रोग्राम भी हैं। पहले वर्ष के बाद शैक्षणिक मानदंडों और उपलब्धता के आधार पर शाखा परिवर्तन की अनुमति है।",
                "bn": "বিসিআরইসি বি.টেক সিএসই, সিএসই এআই এমএল, সিএসই ডাটা সায়েন্স, সিএস ডিজাইন, আইটি, ইসিই, ইই, এমই, সিই, এবং সাইবার সিকিউরিটি অফার করে। এমসিএ, এমবিএ এবং এম.টেক প্রোগ্রামও আছে। প্রথম বর্ষের পরে একাডেমিক মানদণ্ড এবং আসন প্রাপ্যতা সাপেক্ষে শাখা পরিবর্তনের অনুমতি দেওয়া হয়।",
            },
        },
        "admission": {
            "semantic_anchor": "admission_process eligibility application entrance_exam enrollment",
            "keywords": [
                "admission",
                "apply",
                "application",
                "भर्ती",
                "এডমিশন",
                "age limit",
                "eligibility",
            ],
            "answers": {
                "en": f"B.Tech admission is through WBJEE (80% seats), JEE Main (10%), or Management Quota (10%). Eligibility is 10+2 with PCM, minimum 50% marks for general category. There is no upper age limit. Apply online at the WBJEEB website or the college admission portal.",
                "hi": "बी.टेक में एडमिशन WBJEE (80% सीटें), JEE Main (10%), या मैनेजमेंट कोटा (10%) के माध्यम से होता है। पात्रता 10+2 PCM के साथ, सामान्य श्रेणी के लिए न्यूनतम 50% अंक है। कोई ऊपरी आयु सीमा नहीं है।",
                "bn": "বি.টেক এ ভর্তি WBJEE (80% আসন), JEE Main (10%), বা ম্যানেজমেন্ট কোটা (10%) এর মাধ্যমে হয়। যোগ্যতা 10+2 PCM সহ, সাধারণ বিভাগের জন্য ন্যূনতম 50% নম্বর। কোনো ঊর্ধ্ব বয়সসীমা নেই।",
            },
        },
        "campus": {
            "semantic_anchor": "campus facilities infrastructure laboratories size",
            "keywords": [
                "campus",
                "acre",
                "laboratory",
                "lab",
                "transportation",
                "medical",
                "club",
                "canteen",
            ],
            "answers": {
                "en": f"BCREC campus is approximately {college.get('campus_size_acres', '17')} acres, with multi-storied buildings for each department. It has state-of-the-art laboratories for all disciplines. On-site medical facilities are available.",
                "hi": f"बीसीआरईसी कैंपस लगभग {college.get('campus_size_acres', '17')} एकड़ में फैला है, जिसमें प्रत्येक विभाग के लिए बहुमंजिला भवन हैं। सभी विषयों के लिए अत्याधुनिक प्रयोगशालाएं हैं। परिसर में चिकित्सा सुविधाएं उपलब्ध हैं।",
                "bn": f"বিসিআরইসি ক্যাম্পাস প্রায় {college.get('campus_size_acres', '17')} একর জুড়ে বিস্তৃত, প্রতিটি বিভাগের জন্য বহুতল ভবন রয়েছে। সব বিষয়ের জন্য অত্যাধুনিক ল্যাবরেটরি রয়েছে। ক্যাম্পাসে চিকিৎসা সুবিধা উপলব্ধ।",
            },
        },
        "wifi": {
            "semantic_anchor": "campus_facility wifi_internet connectivity network",
            "keywords": ["wifi", "wi-fi", "internet", "network", "वाई-फाई", "ওয়াই-ফাই"],
            "answers": {
                "en": "Yes, 24-hour Wi-Fi is available across the entire campus including all academic blocks and hostels.",
                "hi": "हाँ, पूरे कैंपस में सभी शैक्षणिक भवनों और हॉस्टलों में 24 घंटे वाई-फाई उपलब्ध है।",
                "bn": "হ্যাঁ, পুরো ক্যাম্পাসে সমস্ত একাডেমিক ব্লক এবং হোস্টেলে 24 ঘন্টা ওয়াই-ফাই উপলব্ধ।",
            },
        },
        "faculty": {
            "semantic_anchor": "faculty_teachers professors academic_staff teaching",
            "keywords": ["faculty", "teacher", "professor", "शिक्षक", "প্রফেসর"],
            "answers": {
                "en": f"BCREC has {academics.get('faculty', {}).get('total', '150+')} experienced faculty members. Student-teacher ratio is {academics.get('student_teacher_ratio', '15:1 to 20:1')}.",
                "hi": f"बीसीआरईसी में {academics.get('faculty', {}).get('total', '150+')} अनुभवी शिक्षक हैं। छात्र-शिक्षक अनुपात {academics.get('student_teacher_ratio', '15:1 to 20:1')} है।",
                "bn": f"বিসিআরইসি তে {academics.get('faculty', {}).get('total', '150+')} অভিজ্ঞ শিক্ষক রয়েছেন। ছাত্র-শিক্ষক অনুপাত {academics.get('student_teacher_ratio', '15:1 to 20:1')}।",
            },
        },
        "scholarship": {
            "semantic_anchor": "financial_aid scholarship_tuition fee_waiver education_grant",
            "keywords": ["scholarship", "छात्रवृत्ति", "স্কলারশিপ", "tfw", "svmcm", "kanyashree"],
            "answers": {
                "en": "BCREC offers Tuition Fee Waiver, Swami Vivekananda Scholarship, Kanyashree for girls, and OASIS or Aikyashree scholarships for SC, ST, OBC, and minority students.",
                "hi": "बीसीआरईसी ट्यूशन फीस माफी, स्वामी विवेकानंद स्कॉलरशिप, लड़कियों के लिए कन्याश्री और एससी, एसटी, ओबीसी और अल्पसंख्यक छात्रों के लिए ओएसिस या ऐक्यश्री स्कॉलरशिप प्रदान करता है।",
                "bn": "বিসিআরইসি টিউশন ফি ওয়েভার, স্বামী বিবেকানন্দ স্কলারশিপ, মেয়েদের জন্য কন্যাশ্রী এবং এসসি, এসটি, ওবিসি ও সংখ্যালঘু শিক্ষার্থীদের জন্য ওয়েসিস বা ঐক্যশ্রী স্কলারশিপ প্রদান করে।",
            },
        },
        "documents": {
            "semantic_anchor": "admission_documents required_certificates verification paperwork",
            "keywords": ["document", "दस्तावेज", "ডকুমেন্ট", "certificate", "marksheet"],
            "answers": {
                "en": "For admission, you need class ten and twelve marksheets, admit cards, allotment letter, rank card, photographs, Aadhar card, and domicile or caste certificates if applicable.",
                "hi": "एडमिशन के लिए आपको दसवीं और बारहवीं की मार्कशीट, एडमिट कार्ड, अलॉटमेंट लेटर, रैंक कार्ड, फोटो, आधार कार्ड और डोमिसाइल या जाति प्रमाण पत्र की आवश्यकता होगी।",
                "bn": "ভর্তির জন্য আপনার দশম ও দ্বাদশ শ্রেণীর মার্কশিট, অ্যাডমিট কার্ড, অ্যালটমেন্ট লেটার, র‍্যাঙ্ক কার্ড, ফটো, আধার কার্ড এবং প্রযোজ্য ক্ষেত্রে ডোমিসাইল বা কাস্ট সার্টিফিকেট লাগবে।",
            },
        },
        "online_learning": {
            "semantic_anchor": "online_learning virtual_classes digital_education remote",
            "keywords": ["online", "virtual", "remote", "recorded lecture", "hybrid"],
            "answers": {
                "en": "BCREC conducts regular on-campus classes. Information about online classes is not available on the official site. Please contact the college at 0343-2501353 for details.",
                "hi": "बीसीआरईसी नियमित कैंपस कक्षाएं संचालित करता है। ऑनलाइन कक्षाओं के बारे में आधिकारिक साइट पर जानकारी उपलब्ध नहीं है। कृपया विवरण के लिए कॉलेज को 0343-2501353 पर कॉल करें।",
                "bn": "বিসিআরইসি নিয়মিত অন-ক্যাম্পাস ক্লাস পরিচালনা করে। অনলাইন ক্লাস সম্পর্কে অফিসিয়াল সাইটে তথ্য উপলব্ধ নেই। বিস্তারিত জানার জন্য কলেজে 0343-2501353 নম্বরে কল করুন।",
            },
        },
        "why_bcrec": {
            "semantic_anchor": "why_choose college_advantages highlights accreditation benefits",
            "keywords": [
                "why bcrec",
                "why choose",
                "NBA",
                "NAAC",
                "GATE",
                "alumni",
                "क्यों बीसीआरईसी",
            ],
            "answers": {
                "en": "BCREC, established in 2000, is NBA accredited (CSE, ECE, IT, EE, ME) and NAAC B+ graded. The college offers modern infrastructure, dedicated training cells, and a GATE Forum for career readiness.",
                "hi": "बीसीआरईसी, 2000 में स्थापित, NBA मान्यता प्राप्त (CSE, ECE, IT, EE, ME) और NAAC B+ ग्रेडेड है। कॉलेज आधुनिक बुनियादी ढांचा, समर्पित प्रशिक्षण प्रकोष्ठ और करियर तैयारी के लिए GATE फोरम प्रदान करता है।",
                "bn": "বিসিআরইসি, ২০০০ সালে প্রতিষ্ঠিত, NBA স্বীকৃত (CSE, ECE, IT, EE, ME) এবং NAAC B+ গ্রেড প্রাপ্ত। কলেজ আধুনিক infrastructure, dedicated training cell, এবং GATE ফোরাম প্রদান করে।",
            },
        },
        "international": {
            "semantic_anchor": "international_student foreign_admission visa overseas",
            "keywords": ["international", "foreign", "visa", "dasa", "DASA"],
            "answers": {
                "en": "All programs at BCREC are taught in English. International students may enroll through existing channels such as DASA. For inquiries, contact info@bcrec.ac.in.",
                "hi": "बीसीआरईसी में सभी प्रोग्राम अंग्रेजी में पढ़ाए जाते हैं। अंतर्राष्ट्रीय छात्र DASA जैसे मौजूदा चैनलों के माध्यम से नामांकन कर सकते हैं।",
                "bn": "বিসিআরইসি তে সব প্রোগ্রাম ইংরেজিতে পড়ানো হয়। আন্তর্জাতিক শিক্ষার্থীরা DASA এর মতো বিদ্যমান চ্যানেলের মাধ্যমে নথিভুক্ত করতে পারেন।",
            },
        },
        "policies": {
            "semantic_anchor": "college_policies rules regulations procedures guidelines",
            "keywords": ["fail", "backlog", "laptop", "dress code", "intake", "education loan"],
            "answers": {
                "en": "Failing a semester: Students may reappear in supplementary exams or repeat courses as per MAKAUT rules. Laptops: Not mandatory but recommended for labs and projects. Dress code: No formal dress code for daily classes.",
                "hi": "सेमेस्टर में असफल होना: छात्र MAKAUT नियमों के अनुसार पूरक परीक्षा में शामिल हो सकते हैं। लैपटॉप: अनिवार्य नहीं, लेकिन अनुशंसित। ड्रेस कोड: दैनिक कक्षाओं के लिए कोई औपचारिक ड्रेस कोड नहीं।",
                "bn": "সেমিস্টারে ফেল: শিক্ষার্থীরা MAKAUT নিয়ম অনুযায়ী সাপ্লিমেন্টারি পরীক্ষায় অংশ নিতে পারে। ল্যাপটপ: বাধ্যতামূলক নয়, তবে ল্যাব এবং প্রকল্পের জন্য সুপারিশ করা হয়। ড্রেস কোড: প্রতিদিনের ক্লাসের জন্য কোনো আনুষ্ঠানিক ড্রেস কোড নেই।",
            },
        },
        "hidden_charges": {
            "semantic_anchor": "fees_transparency hidden_costs no_hidden_fees disclosure",
            "keywords": ["hidden", "hidden charge", "transparent", "छिपा शुल्क", "লুকানো ফি"],
            "answers": {
                "en": "No hidden charges. All fees are transparently listed in the official B.Tech fee brochure published by the college. Every charge is itemized per semester.",
                "hi": "कोई छिपा शुल्क नहीं। सभी शुल्क कॉलेज द्वारा प्रकाशित आधिकारिक बी.टेक फी ब्रोशर में पारदर्शी रूप से सूचीबद्ध हैं।",
                "bn": "কোনো লুকানো ফি নেই। কলেজের প্রকাশিত অফিসিয়াল বি.টেক ফি ব্রোশারে সব ফি স্বচ্ছভাবে তালিকাভুক্ত।",
            },
        },
        "refund_policy": {
            "semantic_anchor": "refund cancellation withdrawal_fees money_back",
            "keywords": ["refund", "caution money", "security deposit", "रिफंड", "রিফান্ড"],
            "answers": {
                "en": "The fee structure lists Caution Money as a refundable security deposit, returned after course completion. Other refunds follow MAKAUT and AICTE norms.",
                "hi": "शुल्क संरचना में कॉशन मनी को वापसी योग्य सुरक्षा जमा के रूप में सूचीबद्ध किया गया है जो पाठ्यक्रम पूरा होने पर वापस कर दी जाती है।",
                "bn": "ফি কাঠামোতে কশন মানি ফেরতযোগ্য নিরাপত্তা জমা হিসেবে তালিকাভুক্ত যা কোর্স সম্পূর্ণ হলে ফেরত দেওয়া হয়।",
            },
        },
        "application_status": {
            "semantic_anchor": "application_tracking admission_status result counseling",
            "keywords": ["application status", "result", "seat allotment", "counseling result"],
            "answers": {
                "en": "You can track your application by logging into the college admission portal. Admission results follow the WBJEEB or JEE Main counseling schedule.",
                "hi": "आप कॉलेज एडमिशन पोर्टल में लॉग इन करके अपने आवेदन की स्थिति देख सकते हैं।",
                "bn": "আপনি কলেজ ভর্তি পোর্টালে লগইন করে আপনার আবেদনের অবস্থা দেখতে পারেন।",
            },
        },
        "eligibility_by_rank": {
            "semantic_anchor": "rank_based_eligibility cutoff admission_rank category_rank",
            "answers": {
                "en": "Rank 80,000 with 65 percent PCM marks typically qualifies for CSE, CSE-AIML, CE, and ME. Rank 1,00,000 plus typically qualifies for EE, ECE, and lower-preference branches. Cutoffs vary yearly.",
                "hi": "रैंक 80,000 और PCM में 65% अंक पर आमतौर पर CSE, CSE-AIML, CE, और ME के लिए पात्रता होती है। कटऑफ साल-दर-साल बदलती रहती है।",
                "bn": "র‍্যাঙ্ক ৮০,০০০ এবং PCM এ ৬৫% মার্কস সাধারণত CSE, CSE-AIML, CE, এবং ME এর জন্য যোগ্যতা দেয়। কাটঅফ প্রতি বছর পরিবর্তিত হয়।",
            },
        },
    }
    return answers


def generate_quick_answers(data):
    """Generate quick_answers text snippets from KB data."""
    courses = data.get("courses", {})
    placements = data.get("placements", {})
    hostel = data.get("hostel", {})
    college = data.get("college", {})
    admission = data.get("admission", {})

    btech = courses.get("btech", {})
    cse = btech.get("CSE", {}).get("fees", {})
    ee = btech.get("EE", {}).get("fees", {})
    me = btech.get("ME", {}).get("fees", {})

    return {
        "btech_fee": f"B.Tech total fees range from Rs. {me.get('total', '4,44,100')} to Rs. {cse.get('total', '6,04,700')} depending on branch. CSE/IT/ECE: Rs. {cse.get('total', '6,04,700')}. EE/AIML/DS/CS/CSD: Rs. {ee.get('total', '5,54,100')}. ME/CE: Rs. {me.get('total', '4,44,100')}.",
        "placement_rate": f"BCREC has {placements.get('overall_rate_2025', '91%')} overall placement rate. CSE placement rate is {placements.get('cse_rate_2025', '93.6%')}. Highest package: Rs. {placements.get('highest_package', {}).get('amount', 7)} LPA. Median package: {placements.get('median_package', 'Rs. 4.25 LPA')}.",
        "hostel_fee": f"Hostel is optional. Seat rent: Rs. 10,000 per semester. Mess charges: Rs. 5,500 per month. Caution deposit: Rs. 10,000 (without hostel) or Rs. 12,000 (with hostel), refundable.",
        "nba_accredited": "5 branches are NBA accredited: CSE, IT, ECE, EE, and ME.",
        "autonomous": "Yes, BCREC is an Autonomous Institute from 2024-25 batch onwards.",
        "admission_through": "B.Tech admission through WBJEE (80%), JEE Main (10%), or Management Quota (10%).",
    }


def build_output(data):
    """Build the complete combined_kb.json from KB data."""
    # Generate voice and quick answers
    voice = generate_voice_answers(data)
    quick = generate_quick_answers(data)

    # Preserve important_links
    important_links = data.get("important_links", {})

    output = {
        "meta": {
            "version": f"{data['meta']['version']}",
            "last_updated": datetime.now().strftime("%B %Y"),
            "completeness": "100%",
            "agent_instruction": "Answer questions directly using this knowledge base. If exact data is unavailable, say 'Please contact the college directly.' Phone: 0343-2501353 | Mobile: +91-6297128554 | Email: info@bcrec.ac.in",
        },
        "college": data.get("college", {}),
        "principal": data.get("principal", {}),
        "vice_principal": data.get("vice_principal", {}),
        "courses": data.get("courses", {}),
        "fees_summary": data.get("fees_summary", {}),
        "admission": data.get("admission", {}),
        "admission_documents": data.get("admission_documents", {}),
        "infrastructure": data.get("infrastructure", {}),
        "student_life": data.get("student_life", {}),
        "scholarships": data.get("scholarships", {}),
        "placements": data.get("placements", {}),
        "hostel": data.get("hostel", {}),
        "anti_ragging": data.get("anti_ragging", {}),
        "academics": data.get("academics", {}),
        "departments": data.get("departments", {}),
        "branch_change": data.get(
            "branch_change",
            {
                "allowed": True,
                "timing": "After 1st Year",
                "criteria": "Merit-based (GPA/CGPA) + Seat vacancy in target branch",
            },
        ),
        "quick_answers": quick,
        "important_links": important_links,
        "voice_ready_answers": voice,
    }
    return output


def main():
    validate_only = "--validate" in sys.argv

    print("=" * 60)
    print("BCREC KB Generator")
    print("=" * 60)

    print(f"\nReading KB: {INPUT_PATH}")
    data = load_json(INPUT_PATH)

    print("Building combined_kb.json...")
    output = build_output(data)

    # Verify output is valid JSON
    output_json = json.dumps(output, indent=2, ensure_ascii=False)
    json.loads(output_json)  # Will raise if invalid

    print(f"Output size: {len(output_json)} bytes")
    print(f"Voice ready answers: {len(output.get('voice_ready_answers', {}))} entries")
    print(f"Quick answers: {len(output.get('quick_answers', {}))} entries")

    if validate_only:
        print("\nValidation passed. Output NOT written (--validate mode).")
        return

    save_json(OUTPUT_PATH, output)
    print("\nDone.")


if __name__ == "__main__":
    main()
