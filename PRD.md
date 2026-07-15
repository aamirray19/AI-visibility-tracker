# AI Brand Monitoring Platform – Product Requirements Document (PRD)

## Overview

The platform monitors how AI models perceive and recommend a target company. A user submits a company and website, verifies the generated company profile, and launches a scan. The platform generates realistic user prompts, queries multiple LLMs, evaluates the responses, and presents brand visibility and competitor insights in a dashboard.

---

# Phase 1: Company Onboarding

## Goal
Collect and validate the target company.

### User Input
Required:
- Company name
- Company website

### Validation
- Validate website format.
- Normalize the company name.
- Resolve the company using the supplied website.
- Prevent duplicate scans for the same company.
- Reject invalid or mismatched website/company combinations.

---

# Phase 2: Company Intelligence Generation

## Goal
Generate a structured company profile using gemini 2.5 flash model.

### Generated Fields
- Company
- Website
- Industry
- Products
- Competitors
- Aliases
- Description
- Relevant keywords

### Persisted Scan Data
- Company
- Industry
- Website
- Products
- Competitors

### Edge Cases
- Unknown companies
- Missing competitors
- Incorrect products
- Low-confidence enrichment

---

# Phase 3: User Verification

## Goal
Allow the user to verify and edit generated information.

### Editable Sections
- Company
- Website
- Industry
- Products
- Competitors
- Aliases

### Actions
- Edit
- Add
- Remove
- Confirm

The confirmed profile becomes the source of truth for the scan after once again getting verified by gemini 2.5 flash model.

---

# Phase 4: Monitoring Scope

## Goal
Define what the scan should focus on.

### Monitoring Categories
- Brand mentions
- Product recommendations
- Competitor comparisons
- Purchase intent
- Feature comparisons
- Alternatives
- Reviews
- Pricing discussions
- Technical evaluations


---

# Phase 5: Prompt Generation

## Goal
Generate approximately 50 realistic prompts using gemini 2.5 flash.

### Prompt Categories
- Informational
- Commercial
- Competitor discovery
- Product-specific

Each prompt includes metadata:
- Category
- Intent
- Target
- Language

### Validation
- Remove duplicates
- Regenerate poor-quality prompts
- Limit final prompt set to 50

---

# Phase 6: AI Query Execution

## Goal
Execute every prompt against multiple AI providers.

### Providers
- Gemma 4 31B (Google AI Studio) 
- GPT-OSS 120B (Groq with web search) 

### Execution
- Run providers in parallel for each prompt.
- Capture:
  - Prompt
  - Provider
  - Timestamp
  - Latency
  - Raw response
  - Token usage (if available)

### Failure Handling
- Retry transient failures.
- Retry timeouts once.
- Mark provider unavailable if retries fail.

---

# Phase 7: Response Evaluation

## Goal
Convert raw AI responses into structured insights using lightweight evaluation models.

### Extracted Fields
- Sentiment (Positive, Neutral, Negative)
- Target company mentioned
- Competitors mentioned
- Mentioned companies
- Ranking position
- Recommendation status
- Confidence score
- Reasoning summary

---

# Phase 8: Aggregation

## Goal
Aggregate evaluated results into business metrics.

### Metrics
- AI Visibility
- Recommendation Rate
- Share of Voice
- Overall Sentiment
- Competitor Mention Frequency
- Rank Distribution
- Provider Comparison

---

# Phase 9: Dashboard

## Goal
Present scan results in an actionable interface.

### Executive Summary
- AI Visibility Score
- Overall Sentiment
- Recommendation Rate
- Share of Voice
- Scan Date

### Leaderboard
- Target company
- Competitors
- Mentions
- Positive
- Neutral
- Negative
- Average Rank

### Dashboard Sections
- Competitor Comparison
- Sentiment Breakdown
- Prompt Category Performance
- Model Comparison
- Prompt Explorer

### Prompt Explorer
For every prompt display:
- Prompt
- Gemma response
- GPT-OSS response
- Evaluation
- Mentioned companies
- Sentiment
