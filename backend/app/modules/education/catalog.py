"""Original bilingual teaching notes with primary reading references.

The short notes are a learning aid, not accredited training or a substitute for
field-specific methods advice. All content is local; serving a guide does not
contact any source site. Reference pages were checked on 2026-11-20.
"""

import unicodedata
from copy import deepcopy


def bi(en, bn):
    return {"en": en, "bn": bn}


SOURCES = {
    "reading": {
        "title": "S. Keshav — How to Read a Paper (2007)",
        "url": (
            "https://cs.uwaterloo.ca/~brecht/courses/854-http-video-2012/readings/keshav-paper-reading.pdf"
        ),
    },
    "prisma": {
        "title": "PRISMA 2020 reporting checklist",
        "url": "https://www.prisma-statement.org/prisma-2020-checklist",
    },
    "statistics": {
        "title": "American Statistical Association — Statement on p-values",
        "url": "https://www.amstat.org/asa/files/pdfs/P-ValueStatement.pdf",
    },
    "intervals": {
        "title": "NIST/SEMATECH — What are confidence intervals?",
        "url": "https://www.itl.nist.gov/div898/handbook/prc/section1/prc14.htm",
    },
    "doi": {
        "title": "DOI Foundation — DOI Handbook",
        "url": "https://www.doi.org/doi-handbook/html/",
    },
    "integrity": {
        "title": (
            "U.S. Office of Research Integrity — Definition of " "research misconduct"
        ),
        "url": "https://ori.hhs.gov/definition-research-misconduct",
    },
}


def step(id, title, description, checklist, module_path):
    return {
        "id": id,
        "title": bi(*title),
        "description": bi(*description),
        "checklist": [bi(*item) for item in checklist],
        "module_path": module_path,
    }


GUIDES = [
    {
        "slug": "three-pass-reading",
        "title": bi(
            "Read a Scientific Paper: the Three-Pass Method",
            "তিন ধাপে বৈজ্ঞানিক গবেষণাপত্র পড়া",
        ),
        "summary": bi(
            (
                "Build an overview, inspect evidence, then reconstruct the "
                "reasoning. Choose the depth your question needs."
            ),
            (
                "আগে ধারণা নিন, পরে প্রমাণ দেখুন, শেষে যুক্তি পুনর্গঠন করুন। "
                "নিজের প্রশ্ন অনুযায়ী পড়ার গভীরতা ঠিক করুন।"
            ),
        ),
        "category": "reading",
        "estimated_minutes": 25,
        "sources": [SOURCES["reading"]],
        "steps": [
            step(
                "orient",
                ("Pass 1: orient yourself", "প্রথম ধাপ: সামগ্রিক ধারণা"),
                (
                    (
                        "Scan the title, abstract, headings and conclusion before "
                        "reading details."
                    ),
                    (
                        "বিস্তারিত পড়ার আগে শিরোনাম, সারসংক্ষেপ, উপশিরোনাম ও উপসংহার"
                        " দেখুন।"
                    ),
                ),
                [
                    (
                        "Write the question in your own words.",
                        "প্রশ্নটি নিজের ভাষায় লিখুন।",
                    ),
                    (
                        "Save the paper and decide why it matters to your project.",
                        "গবেষণাপত্রটি সংরক্ষণ করে প্রকল্পে এর প্রয়োজন লিখুন।",
                    ),
                ],
                "/library",
            ),
            step(
                "evidence",
                ("Pass 2: follow the evidence", "দ্বিতীয় ধাপ: প্রমাণ অনুসরণ"),
                (
                    (
                        "Read the main argument, figures and methods; list unfamiliar"
                        " terms and unresolved questions."
                    ),
                    (
                        "মূল যুক্তি, চিত্র ও পদ্ধতি পড়ুন; অজানা পরিভাষা ও অমীমাংসিত "
                        "প্রশ্ন লিখুন।"
                    ),
                ),
                [
                    (
                        "Check figure axes, units and comparison groups.",
                        "চিত্রের অক্ষ, একক ও তুলনার দল দেখুন।",
                    ),
                    (
                        (
                            "Record a page-linked note, separating observation "
                            "from your interpretation."
                        ),
                        "পর্যবেক্ষণ ও নিজের ব্যাখ্যা আলাদা করে পৃষ্ঠাসহ নোট রাখুন।",
                    ),
                ],
                "/analysis",
            ),
            step(
                "reconstruct",
                ("Pass 3: reconstruct and question", "তৃতীয় ধাপ: পুনর্গঠন ও প্রশ্ন"),
                (
                    (
                        "For a central paper, reconstruct the method and ask which "
                        "assumptions support each conclusion."
                    ),
                    (
                        "গুরুত্বপূর্ণ গবেষণাপত্রের পদ্ধতি পুনর্গঠন করে প্রতিটি "
                        "সিদ্ধান্তের অনুমান পরীক্ষা করুন।"
                    ),
                ),
                [
                    (
                        "Sketch the workflow without looking at the paper.",
                        "গবেষণাপত্র না দেখে কাজের ধাপ আঁকুন।",
                    ),
                    (
                        (
                            "List what you could reproduce and what information is "
                            "missing."
                        ),
                        "কী পুনরুৎপাদন করতে পারবেন এবং কোন তথ্য নেই তা লিখুন।",
                    ),
                ],
                "/writing",
            ),
        ],
    },
    {
        "slug": "research-questions-and-gaps",
        "title": bi(
            "Formulate Research Questions and Identify Gaps",
            "গবেষণা প্রশ্ন তৈরি ও ঘাটতি চিহ্নিত করা",
        ),
        "summary": bi(
            (
                "Turn a broad interest into a scoped, answerable question. A "
                "gap in your reading is not proof that no research exists."
            ),
            (
                "বিস্তৃত আগ্রহ থেকে নির্দিষ্ট ও উত্তরযোগ্য প্রশ্ন তৈরি করুন। "
                "নিজের পড়ায় ঘাটতি মানেই আগে কোনো গবেষণা নেই—এমন নয়।"
            ),
        ),
        "category": "planning",
        "estimated_minutes": 30,
        "sources": [SOURCES["prisma"], SOURCES["reading"]],
        "steps": [
            step(
                "scope",
                ("Bound the question", "প্রশ্নের পরিধি নির্ধারণ"),
                (
                    (
                        "Name the population or system, the setting, and the outcome "
                        "you want to understand."
                    ),
                    "কোন জনগোষ্ঠী বা ব্যবস্থা, কোন পরিবেশ ও কোন ফল বুঝতে চান তা বলুন।",
                ),
                [
                    (
                        "Write one question and define its key terms.",
                        "একটি প্রশ্ন লিখে মূল পরিভাষার অর্থ নির্ধারণ করুন।",
                    ),
                    (
                        "State what is outside the scope.",
                        "কোন বিষয় পরিধির বাইরে তা লিখুন।",
                    ),
                ],
                "/writing",
            ),
            step(
                "map",
                ("Map existing approaches", "আগের পদ্ধতিগুলো সাজান"),
                (
                    (
                        "Search synonyms and related methods; include work that "
                        "challenges your expectation."
                    ),
                    (
                        "সমার্থক শব্দ ও সম্পর্কিত পদ্ধতি খুঁজুন; নিজের ধারণার বিপরীত "
                        "গবেষণাও রাখুন।"
                    ),
                ),
                [
                    (
                        "Record search terms and sources.",
                        "অনুসন্ধানের শব্দ ও উৎস লিখুন।",
                    ),
                    (
                        (
                            "Compare assumptions, datasets and limitations "
                            "across saved papers."
                        ),
                        (
                            "সংরক্ষিত গবেষণাপত্রের অনুমান, ডেটাসেট ও সীমাবদ্ধতা তুলনা "
                            "করুন।"
                        ),
                    ),
                ],
                "/discover",
            ),
            step(
                "qualify",
                ("Write a cautious gap statement", "সতর্কভাবে গবেষণার ঘাটতি লিখুন"),
                (
                    (
                        "Connect the proposed gap to cited limitations and explain "
                        "how a feasible study could address it."
                    ),
                    (
                        "উদ্ধৃত সীমাবদ্ধতার সঙ্গে প্রস্তাবিত ঘাটতি যুক্ত করে "
                        "বাস্তবসম্মত গবেষণা কীভাবে তা যাচাই করবে বলুন।"
                    ),
                ),
                [
                    (
                        "Say 'in the papers reviewed' when your coverage is limited.",
                        "পরিধি সীমিত হলে 'পর্যালোচিত গবেষণাপত্রগুলোতে' বলুন।",
                    ),
                    (
                        "Specify evidence that would change your claim.",
                        "কোন প্রমাণ পেলে দাবি বদলাবেন তা নির্ধারণ করুন।",
                    ),
                ],
                "/analysis",
            ),
        ],
    },
    {
        "slug": "systematic-literature-review",
        "title": bi(
            "Plan and Write a Systematic Literature Review",
            "পদ্ধতিগত সাহিত্য পর্যালোচনা পরিকল্পনা ও লেখা",
        ),
        "summary": bi(
            (
                "Make searching, screening and synthesis traceable. PRISMA "
                "supports transparent reporting; it is not a guarantee of "
                "study quality."
            ),
            (
                "অনুসন্ধান, বাছাই ও সংশ্লেষণের ধাপ অনুসরণযোগ্য রাখুন। PRISMA "
                "স্বচ্ছ প্রতিবেদন দিতে সহায়তা করে; মানের নিশ্চয়তা দেয় না।"
            ),
        ),
        "category": "synthesis",
        "estimated_minutes": 40,
        "sources": [SOURCES["prisma"]],
        "steps": [
            step(
                "protocol",
                ("Plan before screening", "বাছাইয়ের আগে পরিকল্পনা"),
                (
                    (
                        "Record the review question, inclusion criteria and planned "
                        "synthesis before selecting results."
                    ),
                    (
                        "ফল বাছার আগে পর্যালোচনার প্রশ্ন, অন্তর্ভুক্তির নিয়ম ও "
                        "সংশ্লেষণ পরিকল্পনা লিখুন।"
                    ),
                ),
                [
                    (
                        "Define eligible study designs, dates and languages.",
                        "যোগ্য গবেষণার ধরন, সময় ও ভাষা নির্ধারণ করুন।",
                    ),
                    (
                        "Keep a dated protocol and explain later changes.",
                        "তারিখসহ পরিকল্পনা রাখুন এবং পরের পরিবর্তন ব্যাখ্যা করুন।",
                    ),
                ],
                "/writing",
            ),
            step(
                "search-screen",
                ("Search and document selection", "খোঁজা ও বাছাই নথিভুক্ত করা"),
                (
                    (
                        "Use reproducible search strings, deduplicate results, and "
                        "record reasons for exclusion."
                    ),
                    (
                        "পুনরায় ব্যবহারযোগ্য অনুসন্ধান লিখুন, সদৃশ ফল সরান ও বাদ "
                        "দেওয়ার কারণ রাখুন।"
                    ),
                ),
                [
                    (
                        "Save search dates, databases and queries.",
                        "অনুসন্ধানের তারিখ, ডেটাবেস ও প্রশ্ন সংরক্ষণ করুন।",
                    ),
                    (
                        "Keep included and excluded records distinguishable.",
                        "অন্তর্ভুক্ত ও বাদ দেওয়া নথি আলাদা রাখুন।",
                    ),
                ],
                "/discover",
            ),
            step(
                "extract",
                ("Extract comparable evidence", "তুলনাযোগ্য প্রমাণ সংগ্রহ"),
                (
                    (
                        "Use a consistent extraction form and appraise limitations "
                        "before pooling conclusions."
                    ),
                    (
                        "একই তথ্যসংগ্রহ কাঠামো ব্যবহার করুন এবং সিদ্ধান্ত মেলানোর আগে"
                        " সীমাবদ্ধতা বিচার করুন।"
                    ),
                ),
                [
                    (
                        "Record design, sample, methods, outcomes and source pages.",
                        "নকশা, নমুনা, পদ্ধতি, ফল ও উৎসের পৃষ্ঠা লিখুন।",
                    ),
                    (
                        "Distinguish missing information from a negative finding.",
                        "অনুপস্থিত তথ্যকে নেতিবাচক ফল থেকে আলাদা করুন।",
                    ),
                ],
                "/analysis",
            ),
            step(
                "report",
                (
                    "Synthesize and report transparently",
                    "স্বচ্ছভাবে সংশ্লেষণ ও প্রতিবেদন",
                ),
                (
                    (
                        "Explain similarities, differences and uncertainty; consult "
                        "the reporting checklist appropriate to your review."
                    ),
                    (
                        "মিল, অমিল ও অনিশ্চয়তা ব্যাখ্যা করুন; নিজের পর্যালোচনার "
                        "উপযুক্ত প্রতিবেদন নির্দেশিকা দেখুন।"
                    ),
                ),
                [
                    (
                        "Include a selection flow and cite every included study.",
                        (
                            "বাছাইয়ের প্রবাহ দেখান ও প্রতিটি অন্তর্ভুক্ত গবেষণা উদ্ধৃত "
                            "করুন।"
                        ),
                    ),
                    (
                        (
                            "Do not combine incompatible effect measures without a "
                            "justified method."
                        ),
                        (
                            "যুক্তিসংগত পদ্ধতি ছাড়া অসামঞ্জস্যপূর্ণ ফলের পরিমাপ একত্র "
                            "করবেন না।"
                        ),
                    ),
                ],
                "/writing",
            ),
        ],
    },
    {
        "slug": "methodology-and-experimental-design",
        "title": bi(
            "Understand Methodology and Experimental Design",
            "গবেষণা পদ্ধতি ও পরীক্ষণ নকশা বোঝা",
        ),
        "summary": bi(
            (
                "Match the question to a design, measurements and fair "
                "comparisons. Describe assumptions rather than treating one "
                "method as universally best."
            ),
            (
                "প্রশ্নের সঙ্গে নকশা, পরিমাপ ও ন্যায্য তুলনা মেলান। কোনো "
                "পদ্ধতিকে সবার জন্য শ্রেষ্ঠ না বলে অনুমানগুলো লিখুন।"
            ),
        ),
        "category": "methods",
        "estimated_minutes": 35,
        "sources": [SOURCES["statistics"], SOURCES["prisma"]],
        "steps": [
            step(
                "design",
                ("Choose the design", "নকশা নির্বাচন"),
                (
                    (
                        "Decide whether the goal is description, explanation, "
                        "prediction or causal estimation."
                    ),
                    (
                        "লক্ষ্য বর্ণনা, ব্যাখ্যা, পূর্বানুমান নাকি কার্যকারণ নির্ণয় "
                        "তা ঠিক করুন।"
                    ),
                ),
                [
                    (
                        "Explain why qualitative, quantitative or mixed methods fit.",
                        "গুণগত, পরিমাণগত বা মিশ্র পদ্ধতি কেন মানানসই তা বলুন।",
                    ),
                    (
                        "State ethical and data-access constraints.",
                        "নৈতিকতা ও তথ্যপ্রাপ্তির সীমা লিখুন।",
                    ),
                ],
                "/writing",
            ),
            step(
                "measure",
                ("Define measurements and comparisons", "পরিমাপ ও তুলনা নির্ধারণ"),
                (
                    (
                        "Specify variables, a baseline and an evaluation plan before "
                        "interpreting results."
                    ),
                    (
                        "ফল ব্যাখ্যার আগে চলক, ভিত্তিমূল তুলনা ও মূল্যায়ন পরিকল্পনা "
                        "নির্ধারণ করুন।"
                    ),
                ),
                [
                    (
                        "Check whether groups or datasets are comparable.",
                        "দল বা ডেটাসেট তুলনাযোগ্য কি না দেখুন।",
                    ),
                    (
                        "Identify confounding and data leakage risks.",
                        "বিভ্রান্তিকারী প্রভাব ও তথ্য ফাঁসের ঝুঁকি চিহ্নিত করুন।",
                    ),
                ],
                "/analysis",
            ),
            step(
                "validate",
                (
                    "Check robustness and reproducibility",
                    "দৃঢ়তা ও পুনরুৎপাদনযোগ্যতা পরীক্ষা",
                ),
                (
                    (
                        "Keep analysis decisions traceable and test reasonable "
                        "alternatives."
                    ),
                    (
                        "বিশ্লেষণের সিদ্ধান্ত অনুসরণযোগ্য রাখুন এবং যুক্তিসংগত বিকল্প"
                        " পরীক্ষা করুন।"
                    ),
                ),
                [
                    (
                        "Record versions, parameters and exclusions.",
                        "সংস্করণ, প্যারামিটার ও বাদ দেওয়ার নিয়ম লিখুন।",
                    ),
                    (
                        (
                            "Explain uncertainty and where the conclusions may not "
                            "generalize."
                        ),
                        (
                            "অনিশ্চয়তা ও কোন ক্ষেত্রে সিদ্ধান্ত প্রযোজ্য নাও হতে পারে তা"
                            " বলুন।"
                        ),
                    ),
                ],
                "/library",
            ),
        ],
    },
    {
        "slug": "statistics-and-evaluation-metrics",
        "title": bi(
            "Statistics and Evaluation Metrics: a Primer",
            "পরিসংখ্যান ও মূল্যায়ন সূচকের প্রাথমিক পাঠ",
        ),
        "summary": bi(
            (
                "Read effect sizes, uncertainty and metrics together. A "
                "threshold alone does not establish scientific importance."
            ),
            (
                "প্রভাবের মাত্রা, অনিশ্চয়তা ও সূচক একসঙ্গে পড়ুন। শুধু একটি "
                "সীমামান বৈজ্ঞানিক গুরুত্ব প্রমাণ করে না।"
            ),
        ),
        "category": "statistics",
        "estimated_minutes": 30,
        "sources": [SOURCES["statistics"], SOURCES["intervals"]],
        "steps": [
            step(
                "outcomes",
                ("Name the outcome and unit", "ফল ও একক চিহ্নিত করা"),
                (
                    (
                        "Determine what was measured, on whom, and with which units "
                        "and denominator."
                    ),
                    "কী মাপা হয়েছে, কার ওপর, কোন একক ও হর ব্যবহার করে তা দেখুন।",
                ),
                [
                    (
                        "Separate a count, proportion and rate.",
                        "সংখ্যা, অনুপাত ও হার আলাদা করুন।",
                    ),
                    (
                        "Check sample size and missing observations.",
                        "নমুনার আকার ও অনুপস্থিত পর্যবেক্ষণ দেখুন।",
                    ),
                ],
                "/analysis",
            ),
            step(
                "uncertainty",
                ("Interpret uncertainty carefully", "সতর্কভাবে অনিশ্চয়তা বোঝা"),
                (
                    (
                        "A p-value is conditional on a model, not the probability "
                        "that a hypothesis is true. Read effect sizes and interval "
                        "assumptions too."
                    ),
                    (
                        "p-value একটি মডেলের শর্তসাপেক্ষ পরিমাপ, কোনো অনুমান সত্য "
                        "হওয়ার সম্ভাবনা নয়। প্রভাবের মাত্রা ও ব্যবধানের শর্তও "
                        "পড়ুন।"
                    ),
                ),
                [
                    (
                        "Report the estimate, interval and model assumptions.",
                        "অনুমিত মান, ব্যবধান ও মডেলের শর্ত লিখুন।",
                    ),
                    (
                        "Distinguish statistical evidence from practical importance.",
                        "পরিসংখ্যানগত প্রমাণ ও বাস্তব গুরুত্ব আলাদা করুন।",
                    ),
                ],
                "/library",
            ),
            step(
                "metrics",
                ("Compare metrics fairly", "ন্যায্যভাবে সূচক তুলনা"),
                (
                    (
                        "Check metric definitions and evaluation data before ranking "
                        "methods."
                    ),
                    "পদ্ধতি সাজানোর আগে সূচকের সংজ্ঞা ও মূল্যায়নের তথ্য দেখুন।",
                ),
                [
                    (
                        "Use the same dataset split and comparable baselines.",
                        "একই তথ্যবিভাজন ও তুলনাযোগ্য ভিত্তিমূল পদ্ধতি ব্যবহার করুন।",
                    ),
                    (
                        "Ask whether an average hides subgroup errors.",
                        "গড় মান কোনো উপদলের ভুল আড়াল করে কি না দেখুন।",
                    ),
                ],
                "/writing",
            ),
        ],
    },
]


def term(slug, en, bn, definition_en, definition_bn, example_en, example_bn, category):
    return {
        "slug": slug,
        "term": bi(en, bn),
        "definition": bi(definition_en, definition_bn),
        "example": bi(example_en, example_bn),
        "category": category,
    }


GLOSSARY = [
    term(
        "abstract",
        "Abstract",
        "সারসংক্ষেপ",
        "A compact account of a paper's question, approach and principal findings.",
        "গবেষণাপত্রের প্রশ্ন, পদ্ধতি ও প্রধান ফলের সংক্ষিপ্ত পরিচয়।",
        "Read the abstract to decide whether the paper addresses your question.",
        "গবেষণাপত্রটি আপনার প্রশ্নের সঙ্গে মেলে কি না বুঝতে সারসংক্ষেপ পড়ুন।",
        "reading",
    ),
    term(
        "literature-review",
        "Literature Review",
        "সাহিত্য পর্যালোচনা",
        "A critical synthesis of research relevant to a defined topic.",
        "নির্দিষ্ট বিষয়ের সম্পর্কিত গবেষণার সমালোচনামূলক সংশ্লেষণ।",
        "Our literature review compares the assumptions behind the methods.",
        "আমাদের সাহিত্য পর্যালোচনায় পদ্ধতিগুলোর অনুমান তুলনা করা হয়েছে।",
        "writing",
    ),
    term(
        "peer-review",
        "Peer Review",
        "সহকর্মী মূল্যায়ন",
        (
            "Assessment of scholarly work by other researchers; it does "
            "not guarantee correctness."
        ),
        "অন্য গবেষকদের দ্বারা গবেষণাকর্ম মূল্যায়ন; এতে নির্ভুলতার নিশ্চয়তা হয় না।",
        "The journal requested revisions after peer review.",
        "সহকর্মী মূল্যায়নের পরে সাময়িকী সংশোধন চেয়েছে।",
        "publishing",
    ),
    term(
        "hypothesis",
        "Hypothesis",
        "পরীক্ষাযোগ্য অনুমান",
        "A proposed explanation or relationship that can be examined using evidence.",
        "প্রমাণ দিয়ে পরীক্ষা করা যায় এমন প্রস্তাবিত ব্যাখ্যা বা সম্পর্ক।",
        "We specified the hypothesis before examining the outcomes.",
        "ফল দেখার আগে আমরা পরীক্ষাযোগ্য অনুমান নির্ধারণ করেছি।",
        "methods",
    ),
    term(
        "ablation-study",
        "Ablation Study",
        "উপাদান বাদ দিয়ে মূল্যায়ন",
        "A comparison that removes or changes a component to examine its contribution.",
        "কোনো উপাদান সরিয়ে বা বদলে তার অবদান পরীক্ষা করার তুলনা।",
        "The ablation study removed the attention component.",
        "উপাদানভিত্তিক পরীক্ষায় attention অংশটি বাদ দেওয়া হয়েছে।",
        "methods",
    ),
    term(
        "baseline",
        "Baseline",
        "ভিত্তিমূল তুলনা",
        "A reference method or condition used for comparison.",
        "তুলনার জন্য ব্যবহৃত প্রাথমিক পদ্ধতি বা অবস্থা।",
        "We evaluated both models against the same baseline.",
        "দুটি মডেলকে একই ভিত্তিমূল পদ্ধতির সঙ্গে মূল্যায়ন করেছি।",
        "methods",
    ),
    term(
        "p-value",
        "p-value",
        "পি-মান",
        (
            "Under a specified null model and assumptions, the "
            "probability of a test statistic at least as extreme as "
            "observed; not the probability the hypothesis is true."
        ),
        (
            "নির্দিষ্ট শূন্য মডেল ও শর্ত ধরে পর্যবেক্ষিত মানের সমান বা "
            "বেশি চরম পরীক্ষণ পরিসংখ্যান পাওয়ার সম্ভাবনা; অনুমানটি সত্য "
            "হওয়ার সম্ভাবনা নয়।"
        ),
        "Report the p-value alongside the effect estimate and assumptions.",
        "প্রভাবের অনুমিত মান ও শর্তের সঙ্গে p-value লিখুন।",
        "statistics",
    ),
    term(
        "confidence-interval",
        "Confidence Interval",
        "আস্থা ব্যবধান",
        (
            "An interval from a procedure with a stated long-run coverage"
            " rate under its assumptions; a particular interval does not "
            "assign a frequentist probability to a fixed parameter."
        ),
        (
            "শর্ত পূরণ হলে দীর্ঘমেয়াদে নির্দিষ্ট হারে প্রকৃত প্যারামিটার"
            " ধারণকারী পদ্ধতি দিয়ে পাওয়া ব্যবধান; একটি ব্যবধান স্থির "
            "প্যারামিটারের ওপর সম্ভাবনা বসায় না।"
        ),
        "Report the confidence interval, sample size and estimation method.",
        "আস্থা ব্যবধান, নমুনার আকার ও অনুমান পদ্ধতি লিখুন।",
        "statistics",
    ),
    term(
        "citation-index",
        "Citation Index",
        "উদ্ধৃতি সূচি",
        (
            "A database or index linking scholarly works to works that "
            "cite them; citation counts depend on coverage."
        ),
        (
            "গবেষণাকর্মের সঙ্গে সেগুলোকে উদ্ধৃত করা কাজের সংযোগ দেখানো "
            "সূচি; উদ্ধৃতি সংখ্যা অন্তর্ভুক্তির পরিধির ওপর নির্ভর করে।"
        ),
        "Different citation indexes may report different citation counts.",
        "ভিন্ন উদ্ধৃতি সূচিতে উদ্ধৃতির সংখ্যা ভিন্ন হতে পারে।",
        "publishing",
    ),
    term(
        "doi",
        "DOI",
        "স্থায়ী ডিজিটাল পরিচায়ক",
        (
            "A persistent identifier resolved through the DOI system; it "
            "identifies a registered object rather than guaranteeing its "
            "quality."
        ),
        (
            "DOI ব্যবস্থায় সমাধানযোগ্য স্থায়ী পরিচায়ক; নিবন্ধিত বস্তু "
            "শনাক্ত করে, মানের নিশ্চয়তা দেয় না।"
        ),
        "Include the DOI when importing a reference.",
        "তথ্যসূত্র আমদানির সময় DOI দিন।",
        "publishing",
    ),
    term(
        "preprint",
        "Preprint",
        "প্রাক্‌প্রকাশিত পাণ্ডুলিপি",
        (
            "A publicly shared research manuscript, commonly before "
            "journal peer review; check its version and review status."
        ),
        (
            "সাধারণত সাময়িকীর সহকর্মী মূল্যায়নের আগে প্রকাশ্যে রাখা "
            "গবেষণা পাণ্ডুলিপি; সংস্করণ ও মূল্যায়নের অবস্থা দেখুন।"
        ),
        "We checked whether the preprint had a later journal version.",
        "প্রাক্‌প্রকাশিত পাণ্ডুলিপির পরে সাময়িকীর সংস্করণ আছে কি না দেখেছি।",
        "publishing",
    ),
    term(
        "empirical",
        "Empirical",
        "পর্যবেক্ষণনির্ভর",
        (
            "Based on observations or measurements rather than "
            "theoretical reasoning alone."
        ),
        "শুধু তত্ত্বগত যুক্তি নয়, পর্যবেক্ষণ বা পরিমাপভিত্তিক।",
        "The empirical evaluation used a held-out dataset.",
        "পর্যবেক্ষণনির্ভর মূল্যায়নে আলাদা রাখা ডেটাসেট ব্যবহার করা হয়েছে।",
        "methods",
    ),
    term(
        "qualitative",
        "Qualitative",
        "গুণগত",
        (
            "Research focused on meanings, experiences or processes using"
            " contextual, interpretive evidence."
        ),
        (
            "প্রাসঙ্গিক ও ব্যাখ্যামূলক প্রমাণ দিয়ে অর্থ, অভিজ্ঞতা বা "
            "প্রক্রিয়া বোঝার গবেষণা।"
        ),
        "The qualitative study analyzed interview accounts.",
        "গুণগত গবেষণায় সাক্ষাৎকারের বিবরণ বিশ্লেষণ করা হয়েছে।",
        "methods",
    ),
    term(
        "quantitative",
        "Quantitative",
        "পরিমাণগত",
        (
            "Research using numerical measurements and explicit analytic "
            "models to examine a question."
        ),
        "সংখ্যাগত পরিমাপ ও স্পষ্ট বিশ্লেষণ মডেল দিয়ে প্রশ্ন পরীক্ষা করার গবেষণা।",
        "The quantitative analysis reported uncertainty around the estimate.",
        "পরিমাণগত বিশ্লেষণে অনুমিত মানের অনিশ্চয়তা দেখানো হয়েছে।",
        "methods",
    ),
    term(
        "plagiarism",
        "Plagiarism",
        "চৌর্যবৃত্তি",
        (
            "Presenting another person's words, ideas, processes or "
            "results without appropriate credit."
        ),
        (
            "উপযুক্ত স্বীকৃতি ছাড়া অন্যের শব্দ, ধারণা, প্রক্রিয়া বা ফল "
            "নিজের হিসেবে উপস্থাপন।"
        ),
        "Paraphrasing still requires credit to the original source.",
        "নিজের ভাষায় লিখলেও মূল উৎসকে স্বীকৃতি দিতে হয়।",
        "integrity",
    ),
    term(
        "open-access",
        "Open Access",
        "উন্মুক্ত প্রবেশাধিকার",
        (
            "Scholarly content available to read without a subscription "
            "barrier; reuse rights depend on its license."
        ),
        (
            "সাবস্ক্রিপশন বাধা ছাড়া পড়া যায় এমন গবেষণাসামগ্রী; "
            "পুনর্ব্যবহারের অধিকার লাইসেন্সের ওপর নির্ভর করে।"
        ),
        "Check the open-access license before reusing a figure.",
        "চিত্র পুনর্ব্যবহারের আগে উন্মুক্ত প্রকাশনার লাইসেন্স দেখুন।",
        "publishing",
    ),
    term(
        "effect-size",
        "Effect Size",
        "প্রভাবের মাত্রা",
        (
            "A numerical measure of the magnitude of a difference or "
            "association, interpreted in context."
        ),
        (
            "পার্থক্য বা সম্পর্কের মাত্রার সংখ্যাগত পরিমাপ, যা "
            "প্রেক্ষাপটে ব্যাখ্যা করতে হয়।"
        ),
        "A small p-value can accompany a small effect size.",
        "ছোট p-value-এর সঙ্গেও প্রভাবের মাত্রা ছোট হতে পারে।",
        "statistics",
    ),
    term(
        "reproducibility",
        "Reproducibility",
        "পুনরুৎপাদনযোগ্যতা",
        (
            "Obtaining consistent computational results using the "
            "original data and specified analysis; terminology varies by "
            "field."
        ),
        (
            "মূল তথ্য ও নির্দিষ্ট বিশ্লেষণ দিয়ে সামঞ্জস্যপূর্ণ গণনাগত ফল"
            " পাওয়া; ক্ষেত্রভেদে পরিভাষার ব্যবহার বদলায়।"
        ),
        "The authors shared code and versions to support reproducibility.",
        "পুনরুৎপাদন সহজ করতে লেখকেরা কোড ও সংস্করণ দিয়েছেন।",
        "integrity",
    ),
]


def guide(slug):
    return next((deepcopy(item) for item in GUIDES if item["slug"] == slug), None)


def normalize(value):
    return unicodedata.normalize("NFC", value).casefold().strip()


def glossary(q="", category=None):
    query = normalize(q)
    return {
        "items": [
            deepcopy(item)
            for item in GLOSSARY
            if (not category or category == item["category"])
            and (
                not query
                or query
                in normalize(
                    " ".join(
                        value
                        for field in ("term", "definition", "example")
                        for value in item[field].values()
                    )
                )
            )
        ],
        "categories": sorted({item["category"] for item in GLOSSARY}),
    }
