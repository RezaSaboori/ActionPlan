# Complete Translation Workflow with Assigning Translator

## Visual Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENGLISH ACTION PLAN                          │
│              (from Formatter Agent)                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  1. TRANSLATOR AGENT                             │
│  • Performs Persian translation                                  │
│  • Adds English terms in parentheses                             │
│  • Preserves markdown structure                                  │
│  Model: gemma3:27b                                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  2. SEGMENTATION AGENT                           │
│  • Segments text into ~500 char chunks                          │
│  • Preserves sentence boundaries                                 │
│  • Maintains section integrity                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  3. TERM IDENTIFIER AGENT                        │
│  • Identifies technical terminology                              │
│  • Extracts context windows                                      │
│  • Marks specialized terms                                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  4. DICTIONARY LOOKUP AGENT                      │
│  • Validates terms against Dictionary.md                         │
│  • Uses RAG for semantic matching                                │
│  • Suggests corrections (confidence > 0.7)                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│               5. TRANSLATION REFINEMENT AGENT                    │
│  • Applies dictionary corrections                                │
│  • Maintains formatting                                          │
│  • Preserves structure                                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│            6. ASSIGNING TRANSLATOR AGENT ⭐ NEW                  │
│  • Corrects organizational assignments                           │
│  • Uses Assigner refrence.md                                    │
│  • Matches Ministry of Health structure                          │
│  • Corrects job titles & departments                             │
│  Model: gemma3:27b                                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              FINAL CORRECTED PERSIAN PLAN                        │
│  ✓ Accurate technical terminology                                │
│  ✓ Correct organizational assignments                            │
│  ✓ Official job titles                                           │
│  ✓ Preserved formatting                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Details

### 1. Translator Agent
**Purpose**: Initial Persian translation  
**Input**: English action plan  
**Output**: Persian plan with technical terms in parentheses  
**Key Feature**: Verbatim, officially-certified-grade translation

### 2. Segmentation Agent
**Purpose**: Text chunking for analysis  
**Input**: Persian plan  
**Output**: Segmented chunks with metadata  
**Key Feature**: Preserves sentence and section boundaries

### 3. Term Identifier Agent
**Purpose**: Technical term extraction  
**Input**: Segmented text  
**Output**: Identified terms with context  
**Key Feature**: Extracts context windows for semantic analysis

### 4. Dictionary Lookup Agent
**Purpose**: Term validation  
**Input**: Identified terms  
**Output**: Corrections and suggestions  
**Key Feature**: RAG-based semantic matching against Dictionary.md

### 5. Translation Refinement Agent
**Purpose**: Apply dictionary corrections  
**Input**: Persian plan + corrections  
**Output**: Terminology-corrected plan  
**Key Feature**: High-confidence corrections (>0.7)

### 6. Assigning Translator Agent ⭐ **NEW**
**Purpose**: Organizational terminology correction  
**Input**: Refined Persian plan  
**Output**: Final corrected plan  
**Key Features**:
- Uses `Assigner refrence.md` (68KB)
- Corrects job titles, departments, units
- Maintains organizational hierarchy
- Preserves all formatting

## Reference Documents

### Dictionary.md
- **Location**: `translator_tools/Dictionary.md`
- **Purpose**: Technical terminology validation
- **Used by**: Dictionary Lookup Agent

### Assigner refrence.md ⭐ **NEW**
- **Location**: `assigner_tools/Fa/Assigner refrence.md`
- **Size**: 68KB
- **Purpose**: Organizational structure reference
- **Used by**: Assigning Translator Agent
- **Content**:
  - Ministry of Health structure
  - University structure
  - Hospital/Center structure
  - Official job titles
  - Department names
  - Organizational hierarchy

## Organizational Levels Covered

### Ministry Level
```
معاونت‌ها (Deputy Ministries)
├── معاونت بهداشت
├── معاونت درمان
├── معاونت آموزشی
├── معاونت پژوهش و فناوری
└── ...

اداره‌های کل (General Directorates)
├── اداره کل امور مجلس
├── اداره کل مدیریت منابع انسانی
└── ...

مراکز (Centers)
├── مرکز مدیریت شبکه
├── مرکز روابط عمومی و اطلاع‌رسانی
└── ...

دفاتر (Offices)
├── دفتر فناوری اطلاعات و ارتباطات
├── دفتر مدیریت عملکرد
└── ...
```

### University Level
```
دانشگاه‌های علوم پزشکی
├── معاونت‌های دانشگاه
├── دانشکده‌ها
├── مراکز تحقیقات
└── شبکه‌های بهداشت و درمان
```

### Center/Hospital Level (5 Levels)
```
Level 1: رئیس بیمارستان، مدیر بیمارستان
Level 2: مترون/مدیر خدمات پرستاری، مدیر مالی
Level 3: سوپروایزر بالینی، سوپروایزر آموزشی
Level 4: سرپرستار بخش، مسئول شیفت
Level 5: پرستاران، پزشکان
```

## Error Handling

Each agent in the workflow includes robust error handling:

1. **Translator**: Falls back to original text
2. **Segmentation**: Preserves original structure
3. **Term Identifier**: Continues with found terms
4. **Dictionary Lookup**: Keeps original if no match
5. **Refinement**: Applies only high-confidence corrections
6. **Assigning Translator**: Returns original if correction fails

All errors are logged but don't break the pipeline.

## Performance

- **Translator**: ~2-5 seconds for typical plan
- **Segmentation**: <1 second
- **Term Identifier**: 1-2 seconds
- **Dictionary Lookup**: 2-4 seconds (RAG query)
- **Refinement**: 1-2 seconds
- **Assigning Translator**: 3-5 seconds (large reference doc)

**Total Translation Time**: ~10-20 seconds for typical action plan

## Configuration

All agents share similar configuration structure:

```bash
# Environment Variables
ASSIGNING_TRANSLATOR_PROVIDER=ollama
ASSIGNING_TRANSLATOR_MODEL=gemma3:27b
ASSIGNING_TRANSLATOR_TEMPERATURE=0.1
ASSIGNING_TRANSLATOR_API_KEY=
ASSIGNING_TRANSLATOR_API_BASE=
```

## Monitoring & Logging

Each agent logs:
- Agent start
- Input data summary
- Processing status
- Output summary
- Any errors

Example log for Assigning Translator:
```
INFO: Executing Assigning Translator
INFO: Input: 15,234 characters
INFO: Reference document loaded: 68,000 characters
INFO: Assignment correction completed: 15,412 characters
INFO: Corrected 8 organizational terms
```

