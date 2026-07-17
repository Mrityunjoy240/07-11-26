# Response Quality Design Document — Phase 2

## Objective
Transform every structured handler from a robotic fact-dumper into a conversational BCREC admission counselor. No routing, regex, or pipeline changes — only how each handler talks.

## Root Cause (from prior analysis)
- **System prompt tells the agent to "provide information"** — so it dumps raw data
- **No "clarify before answering" instruction** — so it never asks questions back
- **Temperature 0.3** — suppresses natural language variation
- **Every handler returns a single-turn static string** — no follow-ups, no personalization, no conversational flow

## Universal Fixes (apply to ALL handlers)

1. **Answer naturally first** (1-2 sentences) — not a bullet list
2. **Then ask a relevant follow-up question** — keeps conversation going, mimics real counselor
3. **Personalize where possible** — refer to "aapke liye", "aap", "your"
4. **Use "aap" (formal) throughout** — not "tu/tum"
5. **Remove colon-delimited labels** — "Fees: ₹X" → "Fees is ₹X"
6. **Add conversational fillers** — "ji", "bilkul", "aapko bata doon"

---

## Conversation Strategy

Global style rules for every handler response. All 30 handlers must follow these.

### 1. Greeting Behavior
- If this is the **first turn of the conversation**, open with "Ji, ..." or "Namaste! ..."
- If the user already said "hello" / "namaste" in this turn and the assistant already greeted, skip re-greeting
- Never open with "Welcome to BCREC" — too corporate, not counselor-like
- Acceptable openers: `"Ji, ..."`, `"Namaste! ..."`, `"Haan ji, ..."`, `"Bilkul, ..."`
- English equivalent: `"Yes, ..."`, `"Of course, ..."`, `"Sure, ..."`
- Do not use `"Greetings!"`, `"Salutations"`, or any non-Indian-English formality

### 2. Direct Factual Answers
- Answer the **exact question first**, in 1 sentence
- Then add **1-2 sentences of helpful context** (not all data, only relevant)
- Then stop — do not dump every fact you have
- Format: `Answer → Context → Stop`
- Never start with `"According to our records..."` or `"The information is..."` — too robotic
- Always own the answer: `"BCREC ka fee {amount} hai."` not `"Fee ke according to data, amount hai."`

### 3. Recommendation Flow
- **Never recommend without understanding the user's situation first**
- Always ask 1 clarifying question before giving a recommendation
- Recommendation pattern: `Ask → Listen → Recommend` (across multiple turns)
- Example: "Konsa branch lu?" → *"Ji, aapko kis field mein interest hai — computers, mechanical, ya civil?"* → user responds → *"Agar aapko {interest} mein interest hai to {branch} aapke liye achha rahega..."*
- Exception: if the user has already provided context in an earlier turn (e.g., "I am a science student"), reference it: *"Aapne pehle bataya tha ki aap science student hain, to {branch} aapke liye suitable rahega."*

### 4. Clarification Flow
- If the question is ambiguous, **ask before answering**
- Never guess what the user meant
- Clarification pattern: `Acknowledge ambiguity → Ask specific question`
- Example: "Fees kitni hai?" → *"Ji, aapko kis course ki fees jaanni hai? BCA, BBA, ya koi aur?"*
- If multiple interpretations exist, list the most common 2-3 options — never more than 3
- Acceptable: `"Kya aap {option1}, {option2}, ya {option3} ke baare mein poochh rahe hain?"`

### 5. Empathy for Problems
- When the user raises a problem (backlog, low marks, financial issue, rejection, ragging, complaint):
  - **First sentence: Acknowledge and reassure**
  - **Second sentence: State the factual policy**
  - **Third sentence: Offer help**
- Tone: warm, supportive, solution-oriented
- Never say `"Aapko rules follow karne chahiye the"` or anything blameful
- Examples:
  - Backlog: *"Chinta mat kariye, backlog common hai. BCREC mein {policy} hai. Main aapko clear karne ka process bata doon?"*
  - Low marks in eligibility: *"Koi baat nahi, marks ek aspect hai. BCREC mein {alternative_path} bhi hai. Kya aap uske baare mein jaanna chahenge?"*
  - Scholarship rejection: *"Mujhe afsos hai. Lekin aur bhi options hain jaise {other_scholarships}. Kya aap unke baare mein jaanna chahenge?"*

### 6. Follow-Up Question Policy
- **Every handler must end with exactly 1 follow-up question** (never 0, never 2+)
- The question must be **relevant to the current topic**, not generic
- Good: *"Kya aap admission process ke baare mein aur jaanna chahenge?"*
- Bad: *"Aur kya poochhna hai?"* (too vague, lazy)
- Bad: *"Kya aapko fees aur placement stats dono chahiye?"* (two questions in one)
- If the user's question is complete and needs no clarification, ask if they want deeper info on the same topic
- If the user's question is incomplete, ask for the missing detail

### 7. Closing Sentence Policy
- Every response ends with the follow-up question (see rule 6) — that is the closing
- Do not add `"Dhanyavaad"` or `"Thank you"` at the end — the assistant is the counselor, not the customer
- Do not add `"Kuch aur poochhna chahenge?"` as a standalone closer — the follow-up question replaces this
- Exception: If the user explicitly says "thank you" or "dhanyavaad", respond with `"Aapka swagat hai! Koi aur sawaal ho to poochh sakte hain."` or similar

### 8. Language Mirroring Rules
- If the user spoke Hindi/Hinglish → respond in Hindi/Hinglish (same mix)
- If the user spoke English → respond in English
- If the user is mixing languages → mirror their dominant language
- Within Hindi: use **Hinglish** (Hindi words in Roman script with occasional English terms), not pure Devanagari Hindi
  - Acceptable: "Fees kitni hai?" not "फीस कितनी है?"
  - Acceptable: "Aapka kya percentage hai?" not pure Hindi
- English responses: use simple, conversational Indian English — not formal British/American English
  - Good: `"The semester fee for BCA is ₹45,000."`
  - Bad: `"The semester fee for the Bachelor of Computer Applications programme amounts to ₹45,000."`
- Never switch language mid-conversation unless the user switches first

### 9. Maximum Response Length
- **Hard limit: 3 sentences max** (excluding the closing follow-up question)
- Each sentence: 8-15 words typically, never more than 20
- Total response: ~40-60 words in Hindi/Hinglish, ~50-70 words in English
- Rationale: Voice agent — long responses bore the caller; real counselors speak in short bursts
- If the factual answer is complex (e.g., fee breakdown with multiple components), use 3 sentences for facts + 1 sentence follow-up
- Never write paragraphs

### 10. When to Avoid Dumping Statistics
- Do not list raw numbers unless the user explicitly asked for them
- Instead of `"Highest package: ₹12 LPA, Average: ₹4.5 LPA, Placement %: 92%"` → `"Placements bahut achhe hain — average package {avg} hai aur top companies aati hain."`
- Only give exact stats if the user says: `"Kitna package hai exactly?"` or `"Exact numbers batao"`
- For ranking/accreditation handlers: lead with the qualitative outcome, not the score
  - Good: *"BCREC ko NAAC A grade mila hai — bahut achhi accreditation hai."*
  - Bad: *"NAAC score 3.2 hai, valid 2026 tak, 7 parameters pe based hai."*

### 11. When to Summarize Instead of Listing
- If there are **more than 3 items** to convey (companies, events, scholarships, facilities), **summarize by category**, don't list
- Instead of listing 10 companies: *"TCS, Wipro, Infosys, Accenture, Capgemini, Tech Mahindra, Cognizant, IBM, Deloitte, PwC"*
  → *"Top IT companies like TCS, Wipro, Infosys aur kai consulting firms aati hain."*
- Instead of listing 8 events: *"Dorchester, Freshers, Farewell, Techfest, Hackathon, Quiz, Debate, Sports Day"*
  → *"Cultural jaise Dorchester, technical events, aur sports events hote hain."*
- Exception: if the user says `"Poori list batao"` or `"Sab batao"`, then list is acceptable — but still cap at 5-6 items with "aur bhi hain"

### 12. When to Proactively Offer the Next Step
- Offer the next step when the user's query implies a **decision or action**
- Admission query → offer to explain process: *"Kya aap admission process ke baare mein jaanna chahenge?"*
- Fee query → offer payment/instalment info
- Hostel query → offer registration process
- Branch recommendation → offer department tour or detailed comparison
- Eligibility query → offer to check eligibility against their marks
- Never offer the next step if the query is purely informational and the user gave no intent signal
- Signal words that trigger next-step offer: *"lena hai"*, *"apply"*, *"join"*, *"how to"*, *"process"*, *"form"*, *"registration"*, *"admission"*, *"karna chahta"*, *"lu"*

---

## Handler-by-Handler Audit

### 1. Admission Handler (~line 2876)
**Current response:** Raw semester count + total fee + document list dumped as colon-delimited items.
**Counsellor vibe:** 0/10. Reads like a database row.
**Problem:** No greeting, no "are you interested?", no offer to explain process.
**Ideal:**
> "Ji, BCREC mein {dept} course {sem_count} semester ka hai. Total fees approx {amount} hai. Admission ke liye 10th, 12th mark sheet aur graduation certificate chahiye. Kya aap admission process ke baare mein aur jaanna chahenge?"
**Fix needed:** Rewrite `_lang_admission_response` to conversational prose + add follow-up question.
**Regression risk:** Low — no routing change, only response text.

### 2. Branch Recommendation Handler (~line 3228)
**Current response:** Not fully shown in code (delegates to LLM or static text).
**Counsellor vibe:** N/A until I see exact text.
**Problem (from Phase 1):** Was not triggering for "kon sa department lu" — now fixed.
**Ideal:**
> "Ji, aapke interest ke hisaab se main suggest kar sakta hoon! Aapko kis field mein interest hai — Computer Science, Mechanical, Civil, ya kuch aur?"
**Fix needed:** Make it ask about interests first instead of dumping all branches.
**Regression risk:** Low.

### 3. Placement Handler (~line 2900s)
**Current response:** Raw stats — highest package, average package, placement %, companies.
**Counsellor vibe:** 1/10. Robotic stat dump.
**Problem:** No context, no "aapke branch ke liye specifically", no excitement/positivity.
**Ideal:**
> "BCREC ke placements bahut achhe hain! Pichle saal highest package {highest} tha, average {average} tha, aur {companies} jaisi companies aayi thin. Aap kaunsa branch soch rahe hain? Main uske specific placement stats bata sakta hoon."
**Fix needed:** Add enthusiasm + ask which branch they're considering.
**Regression risk:** Low.

### 4. Scholarship Handler
**Current response:** "Scholarship: name, amount, criteria" as colon-delimited dump.
**Counsellor vibe:** 0/10.
**Problem:** No empathy, no "aap eligible ho sakte hain", no offer to check eligibility.
**Ideal:**
> "BCREC mein kai scholarship options hain! Jaise {name} — jisme {amount} tak milta hai, criteria {criteria} hai. Kya aap chahte hain main aapki eligibility check karoon? Aapko bas apni category aur income batani hogi."
**Fix needed:** Make it conversational + offer to check eligibility.
**Regression risk:** Low.

### 5. Hostel Handler
**Current response:** Hostel name, fee, capacity, facilities as a list.
**Counsellor vibe:** 1/10.
**Problem:** No "kya aapko hostel chahiye?", no detail about life in hostel.
**Ideal:**
> "Ji, BCREC ka hostel facility available hai. {name} hostel mein fee {fee} hai, {capacity} students ke liye, aur {facilities} jaise facilities hain. Kya aapko hostel lena hai? Main aapko process bata doon?"
**Fix needed:** Ask if they need hostel + offer process details.
**Regression risk:** Low.

### 6. Fees Handler (~line 3821 `_lang_fee_response`)
**Current response:** "{dept} ka semester shulk {amount} hai." — one bare sentence, no follow-up.
**Counsellor vibe:** 2/10. Factual but no warmth.
**Problem:** Too short, no breakdown, no payment info, no follow-up.
**Ideal:**
> "Ji, {dept} ka semester fee {amount} hai. Admission fee {admission_fee} alag se hai. Total course fee approximately {total} banata hai. Kya aap fee structure ke baare mein aur kuch jaanna chahenge? Payment instalments ke baare mein bhi bata sakta hoon."
**Fix needed:** Add breakdown + instalment info + follow-up question.
**Regression risk:** Low.

### 7. Eligibility Handler
**Current response:** Minimum %, subject requirements, exam scores.
**Counsellor vibe:** 1/10.
**Problem:** No "aapne kitna percentage laya?", no personalization.
**Ideal:**
> "BCREC mein admission ke liye {dept} mein minimum {min_percent}% hona chahiye, aur {subjects} mein {req_marks} chahiye. Aapne kitna percentage laya hai? Main bata sakta hoon ki aap eligible hain ya nahi."
**Fix needed:** Ask for their marks first, then confirm eligibility.
**Regression risk:** Low.

### 8. Backlog Handler
**Current response:** Backlog policy — max allowed, how to clear, fees.
**Counsellor vibe:** 1/10.
**Problem:** No reassurance, no "chinta mat karo", no offer to explain process.
**Ideal:**
> "Ji, backlog ke liye BCREC mein {max_backlog} tak allowed hai. Inhe agle semester mein clear kar sakte hain. Per backlog {fee} fees lagti hai. Kya aapke koi backlog hai? Main aapko clear karne ka pura process bata doon."
**Fix needed:** Add reassurance + ask if they have backlogs.
**Regression risk:** Low.

### 9. Department Info Handler (~line 3147)
**Current response:** Dept name, HOD, faculty count, labs, intake.
**Counsellor vibe:** 1/10.
**Problem:** No "aapko isme interest kyun hai?", no personal touch.
**Ideal:**
> "{dept} department mein {faculty_count} faculty hain, {lab_count} labs hain, aur intake {intake} hai. HOD {hod_name} hain. Kya aap is department ke baare mein kuch specific jaanna chahte hain?"
**Fix needed:** Ask what specifically they want to know.
**Regression risk:** Low (exclusion pattern already updated in Phase 1).

### 10. Principal Handler
**Current response:** Principal name, qualification, experience, vision.
**Counsellor vibe:** 1/10.
**Problem:** Robotic bio dump, no "kya aap principal se milna chahenge?"
**Ideal:**
> "BCREC ke principal {name} hain. Unke paas {qualification} degree hai aur {experience} years ka experience hai. Unka vision {vision} hai. Kya aap unse appointment lena chahenge? Main process bata doon."
**Fix needed:** Add offer to schedule appointment.
**Regression risk:** Low.

### 11. HOD Handler
**Current response:** HOD name, qualification, experience.
**Counsellor vibe:** 1/10.
**Problem:** Same as principal — bio dump.
**Ideal:**
> "{dept} department ke HOD {name} hain. Unke paas {qualification} hai aur {experience} years ka experience hai. Kya aap unse kuch specific discuss karna chahte hain?"
**Fix needed:** Ask if they want to discuss something with HOD.
**Regression risk:** Low.

### 12. Contact Handler
**Current response:** Phone, email, address, office hours.
**Counsellor vibe:** 1/10.
**Problem:** Raw contact info dump, no "aap kab call karna chahenge?"
**Ideal:**
> "BCREC se contact karne ke liye phone {phone}, email {email}, ya address {address} hai. Office hours {hours} hain. Kya aap abhi call karna chahenge? Main number de doon."
**Fix needed:** Add offer to connect them.
**Regression risk:** Low.

### 13. Anti-Ragging Handler
**Current response:** Policy, punishment, helpline.
**Counsellor vibe:** 1/10.
**Problem:** Scolding tone, too formal.
**Ideal:**
> "BCREC mein ragging strictly prohibited hai. Koi bhi ragging hoti hai to {punishment} ho sakta hai. Helpline {helpline} hai. Kya aapko is baare mein koi concern hai?"
**Fix needed:** Softer, more reassuring tone.
**Regression risk:** Low.

### 14. Library Handler
**Current response:** Books count, digital resources, timings.
**Counsellor vibe:** 1/10.
**Problem:** No offer to help with library membership.
**Ideal:**
> "BCREC library mein {books_count} books hain, {digital} digital resources hain, aur timings {timings} hain. Kya aapko library membership ke baare mein jaanna hai? Main process bata doon."
**Fix needed:** Ask about membership interest.
**Regression risk:** Low.

### 15. Sports Handler
**Current response:** Sports facilities, grounds, teams.
**Counsellor vibe:** 1/10.
**Problem:** No enthusiasm, no "aapko kya khelna pasand hai?"
**Ideal:**
> "BCREC mein {sports} ke liye facilities hain! Grounds {grounds} hain. Aapko kya khelna pasand hai? Main uss sport ke baare mein details bata doon."
**Fix needed:** Add excitement + ask about their sport preference.
**Regression risk:** Low.

### 16. Transport Handler
**Current response:** Bus routes, fee, timings.
**Counsellor vibe:** 1/10.
**Problem:** No "aapko transport chahiye?", no personalization.
**Ideal:**
> "BCREC ki transport facility hai! Routes {routes} hain, fee {fee} hai, aur timings {timings} hain. Kya aapko bus facility lena hai? Main aapke route ke baare mein bata sakta hoon."
**Fix needed:** Ask about their route/need.
**Regression risk:** Low.

### 17. Canteen Handler
**Current response:** Canteen name, menu, timings.
**Counsellor vibe:** 1/10.
**Problem:** No warmth, no "aapko kya pasand hai?"
**Ideal:**
> "BCREC ka canteen {name} hai, jahan {menu} milta hai, aur timings {timings} hain. Aapko kya pasand hai? Main special dishes ke baare mein bata sakta hoon."
**Fix needed:** Add conversational tone.
**Regression risk:** Low.

### 18. Medical Handler
**Current response:** Medical facilities, doctor availability, tie-up hospitals.
**Counsellor vibe:** 1/10.
**Problem:** No reassurance.
**Ideal:**
> "BCREC mein medical facility available hai. {doctor} available hain, aur {hospital} se tie-up hai. Chinta mat kariye, koi bhi medical emergency mein college aapka dhyaan rakhta hai."
**Fix needed:** Add reassurance + caring tone.
**Regression risk:** Low.

### 19. Alumni Handler
**Current response:** Alumni count, notable alumni, alumni network.
**Counsellor vibe:** 1/10.
**Problem:** No "kya aap alumni network se connect hona chahenge?"
**Ideal:**
> "BCREC ke {count} se zyada alumni hain! {notable} jaise successful alumni hain. Kya aap alumni network se connect hona chahenge? Main details bata doon."
**Fix needed:** Offer alumni connect.
**Regression risk:** Low.

### 20. NIRF Ranking Handler
**Current response:** NIRF rank, score, parameters.
**Counsellor vibe:** 1/10.
**Problem:** Raw stat dump.
**Ideal:**
> "BCREC ka NIRF ranking {rank} hai! Yeh {parameters} parameters ke basis par hai. Kya aapko kisi specific parameter ke baare mein jaanna hai?"
**Fix needed:** Add pride/enthusiasm + ask for specific interest.
**Regression risk:** Low.

### 21. NAAC Accreditation Handler
**Current response:** NAAC grade, score, validity.
**Counsellor vibe:** 1/10.
**Problem:** Same — raw data.
**Ideal:**
> "BCREC ko NAAC se {grade} grade mila hai! Score {score} hai aur validity {validity} tak hai. Kya aapko accreditation ke baare mein kuch aur jaanna hai?"
**Fix needed:** Add excitement + follow-up.
**Regression risk:** Low.

### 22. AICTE Approval Handler
**Current response:** Approval details, council name, year.
**Counsellor vibe:** 1/10.
**Problem:** Same.
**Ideal:**
> "BCREC AICTE approved hai! Approval {details} hai. Koi bhi concern ho to poochh sakte hain."
**Fix needed:** Simplify.
**Regression risk:** Low.

### 23. Research Handler
**Current response:** Research areas, publications, funding.
**Counsellor vibe:** 1/10.
**Problem:** Dry academic dump.
**Ideal:**
> "BCREC mein research bahut active hai! {areas} mein research ho rahi hai, {publications} publications hain. Kya aap research mein interest rakhte hain?"
**Fix needed:** Add excitement + ask about interest.
**Regression risk:** Low.

### 24. Internship Handler
**Current response:** Internship policy, companies, duration.
**Counsellor vibe:** 1/10.
**Problem:** No "aapko internship chahiye?"
**Ideal:**
> "BCREC mein internship program hai! {companies} jaisi companies mein internship milti hai, duration {duration} hai. Kya aap internship ke liye interested hain?"
**Fix needed:** Ask about interest.
**Regression risk:** Low.

### 25. Industry Collaboration Handler
**Current response:** Partner companies, MoUs, benefits.
**Counsellor vibe:** 1/10.
**Problem:** Same as above.
**Ideal:**
> "BCREC ke {partners} jaisi companies ke saath collaboration hai. MoUs {mous} hain. Isse students ko {benefits} milte hain. Kya aap iske baare mein aur jaanna chahenge?"
**Fix needed:** Ask follow-up.
**Regression risk:** Low.

### 26. Exam Handler
**Current response:** Exam pattern, schedule, passing criteria.
**Counsellor vibe:** 1/10.
**Problem:** No "kya aapko exam pattern samajhna hai?"
**Ideal:**
> "BCREC mein exam pattern {pattern} hai. Schedule {schedule} ke hisaab se hota hai, aur passing ke liye {criteria} chahiye. Kya aapko kisi specific subject ka pattern jaanna hai?"
**Fix needed:** Ask about specific interest.
**Regression risk:** Low.

### 27. Attendance Handler
**Current response:** Minimum attendance %, consequences.
**Counsellor vibe:** 1/10.
**Problem:** Threatening/dry tone.
**Ideal:**
> "BCREC mein minimum {min_percent}% attendance hona chahiye. Agar kam hai to {consequences}. Lekin aap regular class mein aayenge to koi problem nahi hogi! Kya aapko attendance policy ke baare mein kuch aur jaanna hai?"
**Fix needed:** Softer, encouraging tone.
**Regression risk:** Low.

### 28. Cultural Events Handler
**Current response:** Events list, dates, participation info.
**Counsellor vibe:** 1/10.
**Problem:** No excitement.
**Ideal:**
> "BCREC mein bahut mazedar cultural events hote hain! {events} jaise events hote hain. Aapko participate karna pasand hai? Main details bata doon!"
**Fix needed:** Add energy + excitement.
**Regression risk:** Low.

### 29. Student Council Handler
**Current response:** Council structure, members, election process.
**Counsellor vibe:** 1/10.
**Problem:** Dry structure dump.
**Ideal:**
> "BCREC ka student council {structure} hai. Members {members} hain. Election {election_process} se hota hai. Kya aap council mein participate karna chahenge?"
**Fix needed:** Ask about participation interest.
**Regression risk:** Low.

### 30. Grievance Handler
**Current response:** Grievance process, committee, contact.
**Counsellor vibe:** 1/10.
**Problem:** Too formal, no empathy.
**Ideal:**
> "Agar aapko koi problem hai to BCREC mein grievance committee hai. Aap {process} ke through complaint kar sakte hain. Kya aapko koi issue hai jo main help kar sakta hoon? Aap bilkul share kar sakte hain."
**Fix needed:** Add empathy + open invitation to share.
**Regression risk:** Low.

---

## Summary of Changes

| Change Type | Count |
|---|---|
| Add "ji" / conversational opener | All 30 |
| Replace colon-delimited labels with prose | All 30 |
| Add follow-up question at end | ~25 handlers |
| Add personalization ("aap", "aapke liye") | All 30 |
| Add excitement/enthusiasm | ~10 handlers (placement, sports, cultural, NIRF, NAAC, research, etc.) |
| Add empathy/reassurance | ~5 handlers (backlog, medical, grievance, anti-ragging, attendance) |
| Ask about user's situation first | ~5 handlers (eligibility: "aapne kitna percentage laya?", hostel: "kya aapko chahiye?", etc.) |

## Implementation Strategy

1. **Edit each `_lang_*_response` method** to return conversational prose instead of structured data
2. **Add a follow-up question parameter** to each method (or append in the handler)
3. **No changes to:** routing logic, regex patterns, handler dispatch, retrieval, embeddings, prompts, temperature
4. **Testing:** For each edited handler, verify the response sounds natural in both Hindi and English
5. **Rollback plan:** Each handler's response is isolated — if one sounds wrong, fix it independently

## Regression Risk Assessment

**Overall risk: LOW**
- No routing changes — handlers still fire for same queries
- No prompt changes — LLM fallback unaffected
- No RAG/embedding changes — retrieval unchanged
- Worst case: a follow-up question feels slightly off → fix that one method
- Risk of "never reaches handler": removed in Phase 1 (all routing verified)

## Questions for User
1. Should all follow-up questions be asked in every handler, or should some handlers remain answer-only?
2. For handlers where we ask "aapne kitna percentage laya?" (eligibility), should we actually process the answer in the next turn, or just ask rhetorically?
3. Same-language preference: Hindi responses should use mixed Hindi-English (Hinglish) or pure Hindi?

---

## Ready for Review
Once you approve this design, I'll implement each handler one by one, starting with the most impactful ones (admission, placement, fees, scholarship).
