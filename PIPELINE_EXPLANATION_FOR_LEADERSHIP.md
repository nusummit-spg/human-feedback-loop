# Human Feedback Loop Pipeline - Leadership Overview

## Executive Summary

When users provide feedback about our AI responses, we process it through a 4-step pipeline that automatically:
1. **Understands** what the user is saying
2. **Gathers context** about the original response
3. **Prioritizes** the issue by importance
4. **Diagnoses** why the problem occurred

This automation allows us to process feedback at scale and identify systemic issues in our AI system.

---

## The 4 Steps Explained

### Step 1: Classification (Understanding the Feedback)

**What it does:**
- Reads the user's feedback text
- Extracts key information (what entity they're talking about, what product/fund/topic)
- Analyzes the emotional tone (is the user satisfied or frustrated?)
- Determines the intent (are they pointing out an error, complaining about quality, or asking a clarification question?)

**Business value:**
- Converts unstructured user feedback into structured data we can act on
- Identifies angry or frustrated users who need priority attention
- Categorizes feedback automatically (corrections vs. complaints vs. questions)

**Example:**
```
User feedback: "That NAV is outdated. Current NAV is ₹152.50"

Step 1 extracts:
✓ Entity: "NAV" (Net Asset Value)
✓ Sentiment: Negative (they're frustrated)
✓ Intent: Correction (they're pointing out an error)
```

---

### Step 2: Enrichment (Gathering Context)

**What it does:**
- Retrieves the original response that the user is giving feedback about (frozen at the time it was given)
- Checks if we've already received feedback about this exact same issue (deduplication)
- Analyzes if the user has given us related feedback before (tracking patterns)
- Identifies if this is a one-off issue or a systematic problem affecting many users

**Business value:**
- Prevents us from "double-processing" the same issue multiple times
- Identifies trending problems (if 100 users report the same error, we flag it as HIGH priority)
- Captures the exact state of the response the user saw (important for debugging)

**Example:**
```
User feedback: "That NAV is outdated"

Step 2 retrieves:
✓ Original response: "NAV: ₹150.25"
✓ Is this a duplicate? No (first report of this issue)
✓ Related feedback? No previous complaints about this fund
✓ Status: New issue to investigate
```

---

### Step 3: Adaptive Router (Prioritization)

**What it does:**
- Applies 5 business rules to determine severity (CRITICAL / HIGH / MEDIUM / LOW)
- Routes the feedback to the right team or process
- Determines how urgently we need to act

**The 5 Rules (in plain English):**
1. **Referential Rule** - Does this feedback contradict our data? (If yes: HIGH priority)
2. **Temporal Rule** - Is the data stale/outdated? (If yes: MEDIUM priority)
3. **Numeric Rule** - Is there a math/calculation error? (If yes: HIGH priority)
4. **Structured Correction** - Did the user provide the correct answer? (If yes: HIGH priority)
5. **Compliance Rule** - Could this expose us to regulatory risk? (If yes: CRITICAL priority)

**Business value:**
- Automatically routes CRITICAL issues (compliance, safety) to urgent handling
- Prevents wasting time on LOW priority complaints
- Ensures we focus engineering effort where it matters most

**Example:**
```
User feedback: "NAV is outdated. Should be ₹152.50"

Step 3 evaluates:
✓ Rule 1: User contradicts our data = HIGH severity
✓ Rule 3: Numeric mismatch ₹150.25 vs ₹152.50 = HIGH severity
✓ Final severity: HIGH (needs quick fix)
```

---

### Step 4: Adjudication (Root Cause Diagnosis)

**What it does:**
- Analyzes why the problem occurred
- Assigns one of 8 root causes that explain the failure

**The 8 Root Causes:**
1. **KNOWLEDGE** - Our data/training is out of date
2. **RETRIEVAL** - We found right data but retrieved wrong version
3. **GRAPH** - Knowledge graph has incomplete connections
4. **CONTEXT_ENGINEERING** - Didn't give AI enough context
5. **MODEL** - AI hallucinated or made up information
6. **GUARDRAIL** - Safety checks failed
7. **COMPLIANCE** - Response violates regulations
8. **PRESENTATION** - Correct but poorly explained

**Business value:**
- Shows WHERE to fix problems in our system
- Helps prioritize engineering work
- Identifies patterns for systemic improvement

**Example:**
```
User feedback: "NAV is outdated. Should be ₹152.50"

Step 4 diagnoses:
✓ Root cause: KNOWLEDGE
  Reason: Our database has ₹150.25, but market has ₹152.50
  Action: Refresh fund NAV data
```

---

## The Complete Flow

```
User feedback arrives
        ↓
[Step 1] Understand: "User is frustrated, correcting a NAV value"
        ↓
[Step 2] Context: "First report, original response was ₹150.25"
        ↓
[Step 3] Prioritize: "HIGH severity - numeric mismatch"
        ↓
[Step 4] Diagnose: "ROOT CAUSE = KNOWLEDGE - database outdated"
        ↓
Action: Flag data team to refresh NAV
```

---

## Business Impact

### Scale & Efficiency
- **Manual**: 10-20 min per feedback item
- **Automated**: 100 items per minute

### Pattern Detection
- Spot systemic issues (47 complaints about same thing = known issue)
- vs. edge cases (1 complaint = investigate)

### Faster Iteration
- From weeks of manual review → instant diagnosis
- 10x faster shipping of fixes

### Quality Metrics
- Severity distribution (% CRITICAL vs HIGH)
- Root cause breakdown (what % issues are DATA vs MODEL)
- Trending issues (growing vs one-offs)
- Fix effectiveness (do fixes prevent recurrence?)

---

## Summary

The pipeline is your **automated quality control system**:
- ✅ Understands feedback (Step 1)
- ✅ Contextualizes issues (Step 2)
- ✅ Prioritizes by impact (Step 3)
- ✅ Diagnoses root causes (Step 4)

**Result:** Better product, faster iteration, happier users.
