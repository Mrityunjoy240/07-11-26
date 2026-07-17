# IMPROVEMENT_PLAN.md

**Failing**: 91/129

## Priority

**1. handler_selection** (54 fail, CRITICAL)
**2. content_accuracy** (53 fail, CRITICAL)
**3. latency** (47 fail, CRITICAL)
**4. completeness** (25 fail, MEDIUM)
**5. conciseness** (13 fail, MEDIUM)
**6. safety_guard** (9 fail, MEDIUM)

## Fix Plans

### Handler Selection

- `G-006`: "namaste" → src=transcript_clarification, ans="I didn't quite catch that. Could you please repeat your question?"  
- `G-007`: "नमस्ते" → src=transcript_clarification, ans="I didn't quite catch that. Could you please repeat your question?"  
- `FF-008`: "CSE er fees koto" → src=safe_point_bengali, ans="আমি পুরোটা বুঝতে পারিনি। আরেকবার একটু ধীরে বলবেন?"  
- `AD-005`: "admission last date" → src=llm_tools, ans="Aapko pata hai ki BCREC ka admission process WBJEE ke through hota hai. Last dat"  


### Content Accuracy

- `G-004`: "good morning" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  
- `G-005`: "good evening" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  
- `G-006`: "namaste" → src=transcript_clarification, ans="I didn't quite catch that. Could you please repeat your question?"  
- `G-007`: "नमस्ते" → src=transcript_clarification, ans="I didn't quite catch that. Could you please repeat your question?"  


### Latency

- `AD-005`: "admission last date" → src=llm_tools, ans="Aapko pata hai ki BCREC ka admission process WBJEE ke through hota hai. Last dat"  
- `AD-007`: "admission ke liye kya chahiye" → src=llm_tools, ans="Aapko WBJEE ya JEE Main mein pass hona hoga aur 10+2 ke PCM mein 50% marks hona "  
- `AD-009`: "CSE a koto seat ache" → src=llm_tools, ans="CSE branch mein 120 seat ache hain. Bilkul, yeh WBJEE rank ke according seat all"  
- `DP-001`: "how many departments in BCREC" → src=llm_tools, ans="Aapko pata hai ki BCREC mein 15 departments hain."  


### Completeness

- `OD-010`: "iit jee coaching" → src=timeout, ans=""  
- `OD-011`: "what is machine learning" → src=timeout, ans=""  
- `OD-012`: "who won the world cup" → src=timeout, ans=""  
- `OD-013`: "opencode ai" → src=timeout, ans=""  


### Conciseness

- `G-001`: "hello" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  
- `G-002`: "hi" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  
- `G-003`: "hey" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  
- `G-004`: "good morning" → src=greeting_deterministic, ans="Hello. How can I help you with admissions, fees, courses, or hostel details?"  


### Safety Guard

- `OD-005`: "how to make biryani" → src=llm_tools, ans="Biryani banane ki vidhi kya hai? Bilkul, main aapko batata hoon. Biryani banane "  
- `OD-006`: "play cricket with me" → src=llm_tools+safe_point_unknown, ans="I am not completely sure about that information, but I can connect you with the "  
- `OD-008`: "latest bollywood movie" → src=llm_tools+safe_point_unknown, ans="I am not completely sure about that information, but I can connect you with the "  
- `OD-009`: "how to build a website" → src=llm_tools, ans="Aap website banane ke liye kya karna hoga? Aapko coding knowledge ki zaroorat ho"  


## Sprints
| Sprint | Focus | Est Impact |
|---|---|---|
| 1 | Handler Selection + Content Accuracy | ~50% |
| 2 | Conciseness (follow-ups) | ~20% |
| 3 | Latency | ~15% |
| 4 | Safety + Language | ~10% |
| 5 | Edge Cases | ~5% |