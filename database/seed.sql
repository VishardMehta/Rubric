-- Rubric demo data
--
-- Run in the Supabase SQL editor after database/schema.sql.
-- Safe to re-run: every row has a fixed id and inserts with
-- `on conflict do nothing`, so a second run changes nothing.
--
-- Two jobs from the descriptions in Demofiles/, five applications from the
-- three resumes there, and one completed interview. Enough to open every
-- screen in docs/screens.md with something real on it.
--
-- What is genuine and what is not:
--
--   * The job descriptions, candidate names and resume text come from the
--     files in Demofiles/.
--   * The rubrics, transcripts, scores, assessments and interview answers
--     are written by hand to look like what the pipeline produces. No
--     Gemini or Groq call made any of this. If you want real model output,
--     create the job through the UI instead.
--   * audio_path and resume_path are null. Nothing was uploaded to
--     storage, and signed_url() returns null for a null path, so the
--     recording player and the resume link are simply absent on these
--     candidates rather than broken.
--
-- Sub-scores sum to the total on every row, because that is the invariant
-- the product is built on (CLAUDE.md, "Scoring discipline") and seed data
-- that violated it would make the Candidate Detail screen contradict
-- itself.

-- ---------------------------------------------------------------------
-- Reset (uncomment to remove just the seeded rows)
-- ---------------------------------------------------------------------
-- delete from jobs where id in (
--   '11111111-1111-4111-8111-111111111111',
--   '22222222-2222-4222-8222-222222222222'
-- );
-- Candidates, interviews, turns and results cascade from the job.

-- ---------------------------------------------------------------------
-- Jobs
-- ---------------------------------------------------------------------

insert into jobs (id, title, description, skills, experience, rubric, state, created_at)
values (
  '11111111-1111-4111-8111-111111111111',
  'Junior Business Analyst',
  $jd$About Us

Sigmoid empowers enterprises to make smarter, data-driven decisions through Data Engineering, AI, and Analytics. We partner with Fortune 500 companies across Retail, BFSI, Life Sciences, Manufacturing, and other industries to build cloud-native data platforms, AI solutions, and business analytics products that solve complex business problems at scale.

What You'll Do

As a Junior Business Analyst, you will work with experienced consultants, data engineers, and data scientists and your mentors to solve real-world business problems using data and analytics.

Key Responsibilities

- Analyze business and data problems to generate actionable insights.
- Quick and exploratory data analysis for generating rapid insights.
- Write SQL queries to extract, clean, and analyze data.
- Work with cross-functional teams to understand business requirements and translate them into analytical solutions.
- Support data validation, quality checks, and documentation activities.
- Present findings through clear visualizations and business storytelling.
- Learn and apply modern Analytics, AI, and Generative AI technologies as part of project delivery.

Who We're Looking For

- Final-year or recent graduate (B.E./B.Tech) from a recognized university.
- Strong analytical thinking and problem-solving aptitude.
- Good understanding of SQL, Excel, and basic programming concepts.
- Exposure to Python or R through coursework, projects, or internships.
- Familiarity with Power BI or Tableau is an added advantage.
- Strong communication, collaboration, and presentation skills.
- Curious, self-motivated, and eager to learn new technologies.

Preferred Qualifications

- Academic projects or internships in Data Analytics, Business Intelligence, Machine Learning, or Data Science.
- Basic understanding of databases, statistics, and data visualization.
- Participation in hackathons, coding competitions, analytics case studies, or open-source projects is a plus.$jd$,
  array['SQL', 'Excel', 'Python', 'Power BI', 'Data visualization', 'Business storytelling'],
  'Final year student or recent graduate, 0 to 1 years',
  $rubric${
    "criteria": [
      {
        "id": "sql_and_data_extraction",
        "name": "SQL and data extraction",
        "description": "Writes SQL to pull, join and clean data without waiting for a prepared table. Evidence looks like named constructs (group by, joins, window functions), work against real schemas, and handling of messy or incomplete source data.",
        "points": 25,
        "dimension": "technical"
      },
      {
        "id": "python_or_r_analysis",
        "name": "Python or R analysis",
        "description": "Uses Python or R for exploratory analysis rather than only for coursework. Evidence looks like Pandas, NumPy or equivalent applied to a dataset of real size, with a stated method and a stated result.",
        "points": 20,
        "dimension": "technical"
      },
      {
        "id": "business_intelligence_tooling",
        "name": "Dashboards and visualization",
        "description": "Builds dashboards or reports other people use. Evidence looks like Power BI, Tableau or Excel work with a named audience, chosen metrics, and a change in how a decision was made or how long reporting took.",
        "points": 15,
        "dimension": "technical"
      },
      {
        "id": "analytical_problem_solving",
        "name": "Structured problem solving",
        "description": "Breaks an open business question into parts before analysing it. Evidence looks like a hypothesis, a decomposition of a metric into drivers, or an explanation of why one explanation was ruled out in favour of another.",
        "points": 20,
        "dimension": "experience"
      },
      {
        "id": "communication_and_storytelling",
        "name": "Communication and storytelling",
        "description": "Explains an analysis to people who did not do it. Evidence looks like presenting to stakeholders, teaching or mentoring, or a clear account of what a finding means for a decision rather than what the model scored.",
        "points": 20,
        "dimension": "communication"
      }
    ],
    "interview_topics": [
      "SQL query construction and data cleaning",
      "Exploratory analysis and hypothesis framing",
      "Dashboard design and metric selection",
      "Presenting findings to non-technical stakeholders",
      "Data validation and quality checks"
    ]
  }$rubric$::jsonb,
  'active',
  now() - interval '6 days'
)
on conflict (id) do nothing;

insert into jobs (id, title, description, skills, experience, rubric, state, created_at)
values (
  '22222222-2222-4222-8222-222222222222',
  'Business Analytics & Insights Intern',
  $jd$Amgen harnesses the best of biology and technology to fight the world's toughest diseases, and make people's lives easier, fuller and longer. We discover, develop, manufacture and deliver innovative medicines to help millions of patients.

Role Description

The Business Analytics & Insights Intern will support the internal Amgen team in delivering data-driven insights that inform strategic and operational decision-making across commercial functions. This role partners with cross-functional stakeholders including Commercial, Value and Access, Finance, and Brand Strategy teams to analyze data, uncover trends, and translate findings into actionable insights. The role blends structured analytics, business problem-solving, and storytelling to help drive clarity on key business questions such as performance drivers, market dynamics, and growth opportunities.

Roles and Responsibility

- Apply structured problem-solving and analytical thinking to understand business questions, identify key drivers, and formulate data-driven hypotheses.
- Analyze large and complex datasets (sales data, market data, claims data, customer data) to identify trends, patterns, risks, and opportunities.
- Support development of dashboards, reports, and analytical models that enable tracking of commercial performance and key KPIs.
- Assist in synthesizing insights into clear, concise narratives and presentations for business stakeholders.
- Collaborate with cross-functional teams (Commercial, Finance, Market Access) to understand business needs and translate them into analytical solutions.
- Contribute to exploratory analyses, including segmentation, trend analysis, and scenario-based evaluations.
- Identify opportunities to improve data quality, reporting efficiency, and analytical frameworks.

Tools you may use: SQL, Python, Tableau, Excel, analytics and BI dashboards, data platforms (Snowflake, Databricks), enterprise data sources and selected AI tooling.

Qualifications

- Master's degree, or a bachelor's degree in a relevant field with 70% or 7.0 CGPA. Flexible for strong projects or internships.
- Passion for data analysis and hypothesis-driven thinking.
- Curious, self-driven learner who connects insights across functions.
- Clear written and verbal communication.
- Understanding of analytics concepts: segmentation, trends, forecasting, KPIs.
- Experience or willingness to work with large datasets.
- Exposure to biotech, pharma or healthcare data is a plus.

Location: Hyderabad$jd$,
  array['SQL', 'Python', 'Tableau', 'Excel', 'Dashboards and KPI tracking', 'Forecasting', 'Stakeholder communication'],
  'Internship. No prior full time experience required',
  $rubric${
    "criteria": [
      {
        "id": "sql_and_large_datasets",
        "name": "SQL on large datasets",
        "description": "Queries datasets large enough that structure matters. Evidence looks like joins and aggregation across multiple sources, work with sales, claims or transactional data, and an account of how data quality problems were found and handled.",
        "points": 25,
        "dimension": "technical"
      },
      {
        "id": "python_and_statistical_analysis",
        "name": "Python and statistical analysis",
        "description": "Applies Python and analytics concepts to a business question. Evidence looks like segmentation, trend analysis, forecasting or scenario modelling with a stated method, and a result that was checked rather than asserted.",
        "points": 20,
        "dimension": "technical"
      },
      {
        "id": "dashboarding_and_kpis",
        "name": "Dashboards and KPI tracking",
        "description": "Builds tracking that a business function relies on. Evidence looks like Tableau, Power BI or Excel dashboards with deliberately chosen KPIs and a reason those KPIs were the right ones for the question.",
        "points": 15,
        "dimension": "technical"
      },
      {
        "id": "structured_problem_solving",
        "name": "Hypothesis-driven problem solving",
        "description": "Starts from a business question and works to drivers. Evidence looks like decomposing a metric, forming and testing a hypothesis, or separating correlated explanations to identify what actually moved a number.",
        "points": 20,
        "dimension": "experience"
      },
      {
        "id": "insight_storytelling",
        "name": "Insight storytelling",
        "description": "Turns analysis into a narrative a stakeholder can act on. Evidence looks like presenting to a non-technical audience, writing up a recommendation, or stating the decision a finding should change.",
        "points": 20,
        "dimension": "communication"
      }
    ],
    "interview_topics": [
      "Working with large and messy commercial datasets",
      "Hypothesis-driven decomposition of a business metric",
      "Forecasting and scenario analysis",
      "KPI selection for a commercial dashboard",
      "Communicating findings to non-analysts"
    ]
  }$rubric$::jsonb,
  'active',
  now() - interval '4 days'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Candidates: Junior Business Analyst
-- ---------------------------------------------------------------------
--
-- Every quote in sub_scores.evidence appears word for word in the
-- transcript or resume_text on the same row. The real screener is
-- required to do that (backend.md 5.2) and it is checked, so seed data
-- that quoted something absent would misrepresent the feature.

insert into candidates (
  id, job_id, name, email, transcript, resume_text,
  screening_score, screening_band, sub_scores,
  matched_skills, unevidenced_skills, resume_intro_conflicts,
  assessment, recommendation, state, created_at
) values (
  'aaaaaaa1-0000-4000-8000-000000000001',
  '11111111-1111-4111-8111-111111111111',
  'Vishard Mehta',
  'vishard2005@gmail.com',
  $t$Hi, I am Vishard Mehta, a final year Computer Science student at Thapar Institute, and most of my work is in business and quantitative analysis. The piece I am proudest of is an analysis of two hundred and forty billion dollars of US Medicare Part D drug spending across three and a half thousand products. I built a reconciled bridge that split the growth into price, volume and mix effects, and found that price rather than patient volume drove fifty nine percent of a seventy seven billion dollar increase. I then built a three scenario forecast that back tested to a one point seven percent error, and a priority scoring model whose top ten output matched three of the ten drugs the government actually selected for price negotiation. I have also spent six months as a quantitative analyst on a live forecasting tournament with my own capital staked, finishing in the top twelve percent globally, and I did a profit diagnostic on a large manufacturer using SQL and Power BI. Day to day I work in SQL, Python with Pandas, Excel and Power BI, and what I care about is getting from a messy dataset to a decision somebody can act on.$t$,
  $r$Vishard Mehta. B.Tech Computer Science and Engineering, Thapar Institute of Engineering and Technology, 2023 to 2027, CGPA 8.78.

EXPERIENCE
Raio Quantum, Summer Intern, June to August 2026. Developed an enterprise-grade relational schema for a multi-entity transactional system, optimizing query read paths with partial indexes. Built a ranked search and record-matching system using BM25 scoring, synonym expansion and Levenshtein fuzzy matching to resolve inconsistent free-text queries, validated by 27 automated tests.

Numerai, Quantitative Analyst (independent), January to June 2026. Forecast obfuscated financial time series for a live hedge fund tournament with personal capital staked on model performance, reaching a top 12% global rank on 60-day risk-adjusted contribution. Designed a regime-gated ensemble of specialist models using cross-validation to eliminate temporal leakage.

PROJECTS
Bosch Profit Diagnostic. SQL, Excel, Power BI, Python (Pandas). Diagnosed a profit paradox by analyzing why revenue increased while operating profit declined, using hypothesis-driven business analysis and KPI decomposition. Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories, identifying raw-material inflation, logistics costs and discounting as the primary drivers of margin erosion.

Medicare Part D Spending Analysis. Python (Pandas), Matplotlib, CMS public data. Analyzed $240bn of US Medicare Part D drug spending across 3,575 products from 2018 to 2022, building a reconciled bridge splitting growth into price, volume and mix effects. Produced a three-scenario forecast back-tested to a 1.7% error. Developed a priority-scoring model ranking drugs on spend, price-led growth and lack of generic competition.

Querix. Python, React, TypeScript, DuckDB, FastAPI. Analytics tool letting non-technical users query structured data in plain English, generating visualizations and written insights from CSV and Parquet sources.

SKILLS
Analytics: MS Excel, SQL, Python (Pandas, NumPy, Scikit-learn), R, MATLAB.
Tools and reporting: PowerPoint, Power BI, Matplotlib, GitHub.
Methods: Forecasting, scenario and sensitivity analysis, hypothesis testing, root-cause analysis.

ACHIEVEMENTS
2x Kaggle Expert, 17 public datasets, 14 medals, peak global rank 87.
Microsoft Learn Student Chapter, led technical execution for flagship events with 2000+ participants.
Amazon Machine Learning Summer School 2026.$r$,
  84, 'strong',
  $s$[
    {
      "criterion_id": "sql_and_data_extraction",
      "evidence": [
        {"source": "resume", "quote": "Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories"},
        {"source": "resume", "quote": "Developed an enterprise-grade relational schema for a multi-entity transactional system, optimizing query read paths with partial indexes"}
      ],
      "points_awarded": 21,
      "points_possible": 25
    },
    {
      "criterion_id": "python_or_r_analysis",
      "evidence": [
        {"source": "resume", "quote": "Analyzed $240bn of US Medicare Part D drug spending across 3,575 products from 2018 to 2022"},
        {"source": "introduction", "quote": "I built a reconciled bridge that split the growth into price, volume and mix effects"}
      ],
      "points_awarded": 17,
      "points_possible": 20
    },
    {
      "criterion_id": "business_intelligence_tooling",
      "evidence": [
        {"source": "introduction", "quote": "I did a profit diagnostic on a large manufacturer using SQL and Power BI"}
      ],
      "points_awarded": 12,
      "points_possible": 15
    },
    {
      "criterion_id": "analytical_problem_solving",
      "evidence": [
        {"source": "introduction", "quote": "found that price rather than patient volume drove fifty nine percent of a seventy seven billion dollar increase"},
        {"source": "resume", "quote": "using hypothesis-driven business analysis and KPI decomposition"}
      ],
      "points_awarded": 18,
      "points_possible": 20
    },
    {
      "criterion_id": "communication_and_storytelling",
      "evidence": [
        {"source": "introduction", "quote": "what I care about is getting from a messy dataset to a decision somebody can act on"},
        {"source": "resume", "quote": "Analytics tool letting non-technical users query structured data in plain English"}
      ],
      "points_awarded": 16,
      "points_possible": 20
    }
  ]$s$::jsonb,
  array['SQL', 'Excel', 'Python', 'Power BI', 'Data visualization', 'Business storytelling'],
  array[]::text[],
  array[]::text[],
  $a$Strongest evidence on structured problem solving and Python analysis. The Medicare Part D work decomposes spending growth into price, volume and mix and states a checked result, which is what the structured problem solving criterion asks for, and the priority-scoring model was validated against an external outcome rather than asserted. SQL and data extraction is evidenced twice, once through GROUP BY and JOIN analysis on the profit diagnostic and once through schema design with partial indexes, though neither describes handling messy or incomplete source data directly. Dashboards and visualization is the thinnest area: Power BI appears in both sources but no audience, chosen metric or reporting outcome is named. Communication is evidenced through building a plain-English query tool for non-technical users rather than through presenting to stakeholders.$a$,
  'shortlist', 'interviewed',
  now() - interval '5 days'
)
on conflict (id) do nothing;

insert into candidates (
  id, job_id, name, email, transcript, resume_text,
  screening_score, screening_band, sub_scores,
  matched_skills, unevidenced_skills, resume_intro_conflicts,
  assessment, recommendation, state, created_at
) values (
  'aaaaaaa1-0000-4000-8000-000000000002',
  '11111111-1111-4111-8111-111111111111',
  'Hitesh Yadav',
  'yadavhitesh144@gmail.com',
  $t$Hi, my name is Hitesh Yadav and I am a final year Computer Science student at Thapar Institute, currently at a CGPA of 9.82. The most relevant thing I have done for this role is my data science internship at the Unessa Foundation. I analysed social program datasets of about a thousand records across three programs, and built Power BI dashboards and analytical reports that cut the team's manual analysis time by roughly forty percent and improved reporting accuracy by about thirty percent. Before that I did a tech internship on a distributed backend using Django, Redis and Celery, so I am comfortable going down to the data layer and writing my own SQL rather than waiting for someone to hand me a clean table. Day to day I work in Python with Pandas, NumPy and Matplotlib, and I also use R and SQL. Outside coursework I am a Kaggle datasets expert ranked in the top two percent globally, and I have solved over eight hundred problems on LeetCode and similar platforms.$t$,
  $r$Hitesh Yadav. B.Tech Computer Science and Engineering, Thapar Institute of Engineering and Technology, 2023 to 2027, CGPA 9.82.

EXPERIENCE
Algo University x Tensor School of CS and AI, Tech Intern, June 2026. Architected a 7-container distributed microservices backend using Django, Redis and Celery, implementing direct-to-S3 multipart uploads that processed 10GB+ video files and reduced server memory overhead by 85%. Engineered a high-concurrency write-behind caching system leveraging Redis Hashes to absorb 5,000+ continuous video progress heartbeats per minute, reducing PostgreSQL database write load by 95%.

Unessa Foundation, Data Science Intern, January 2026. Analyzed social datasets of 1k+ records, identifying trends that improved program insights by 20 to 25%. Built dashboards and analytical reports using Power BI, reducing manual data analysis time by 40% and improving reporting accuracy by 25%. Analyzed datasets across 3+ programs to enable evidence-based decision-making.

PROJECTS
Road Sign Detection. Python, YOLOv8, OpenCV, Ultralytics, Roboflow, PyTorch. Trained a custom YOLOv8 model on a traffic dataset of 3530 training, 801 validation and 641 test images. Achieved mAP@0.5 of 81%, recall 96% and precision 60%. Analyzed model performance using confusion matrices and precision-recall curves, identifying that 65 to 70% of false positives arose from visually similar road sign classes.

Pacman AI Game. Pygame, BFS, A*, hill-climbing. Built a 2D game with AI-controlled ghost navigation, achieving 35 to 45% faster path convergence compared to random movement.

StudyNotion EdTech Platform. MongoDB, Express, React, Node, Redux. Built a full-stack platform with JWT authentication and role-based authorization across 3 user roles, and 15+ RESTful APIs.

SKILLS
Languages: C, C++, Python, JavaScript, MATLAB, R, SQL, NoSQL.
Frameworks: React, Express, Pandas, NumPy, Matplotlib, PyTorch, TensorFlow, OpenCV.
Developer tools: Git, GitHub, Docker, Postman, Node.

ACHIEVEMENTS
Kaggle Datasets Expert, global rank 190 of 8,427 contributors, top 2.2%.
Kaggle Notebooks Expert, global rank 1,656 of 58,851 contributors, top 2.8%.
Solved 800+ problems on GeeksforGeeks, LeetCode and HackerRank.
Winner of Hacklipse 4.0, an intra-college hackathon.$r$,
  72, 'strong',
  $s$[
    {
      "criterion_id": "sql_and_data_extraction",
      "evidence": [
        {"source": "introduction", "quote": "I am comfortable going down to the data layer and writing my own SQL rather than waiting for someone to hand me a clean table"},
        {"source": "resume", "quote": "reducing PostgreSQL database write load by 95%"}
      ],
      "points_awarded": 18,
      "points_possible": 25
    },
    {
      "criterion_id": "python_or_r_analysis",
      "evidence": [
        {"source": "resume", "quote": "Analyzed social datasets of 1k+ records, identifying trends that improved program insights by 20 to 25%"},
        {"source": "resume", "quote": "Analyzed model performance using confusion matrices and precision-recall curves"}
      ],
      "points_awarded": 16,
      "points_possible": 20
    },
    {
      "criterion_id": "business_intelligence_tooling",
      "evidence": [
        {"source": "resume", "quote": "Built dashboards and analytical reports using Power BI, reducing manual data analysis time by 40%"}
      ],
      "points_awarded": 12,
      "points_possible": 15
    },
    {
      "criterion_id": "analytical_problem_solving",
      "evidence": [
        {"source": "resume", "quote": "identifying that 65 to 70% of false positives arose from visually similar road sign classes"}
      ],
      "points_awarded": 14,
      "points_possible": 20
    },
    {
      "criterion_id": "communication_and_storytelling",
      "evidence": [
        {"source": "resume", "quote": "Analyzed datasets across 3+ programs to enable evidence-based decision-making"}
      ],
      "points_awarded": 12,
      "points_possible": 20
    }
  ]$s$::jsonb,
  array['SQL', 'Python', 'Power BI', 'Data visualization'],
  array['Excel', 'Business storytelling'],
  array['The resume states reporting accuracy improved by 25%, the introduction said about thirty percent.'],
  $a$Dashboards and visualization is the best evidenced criterion: the Unessa Foundation internship names Power BI, a named team, and a measured reduction in reporting time. Python analysis is evidenced on both a social dataset and a computer vision model, though the analysis described is model evaluation rather than business analysis. SQL is claimed directly in the introduction and supported indirectly by database work on the backend internship, but no query, schema or data cleaning task is described. Structured problem solving rests on a single piece of evidence, the false-positive analysis on road signs, which is diagnostic work but not on a business question. Communication and storytelling is the weakest area: the sources describe what was built and measured, not any instance of presenting or explaining it to someone else.$a$,
  'shortlist', 'approved',
  now() - interval '5 days'
)
on conflict (id) do nothing;

insert into candidates (
  id, job_id, name, email, transcript, resume_text,
  screening_score, screening_band, sub_scores,
  matched_skills, unevidenced_skills, resume_intro_conflicts,
  assessment, recommendation, state, created_at
) values (
  'aaaaaaa1-0000-4000-8000-000000000003',
  '11111111-1111-4111-8111-111111111111',
  'Priyanshu Singh',
  'dispriyanshu47@gmail.com',
  $t$Hello, I am Priyanshu Singh, a final year Computer Engineering student at Thapar Institute with a CGPA of 8.61. The project I would point to first is a profit diagnostic on a large industrial manufacturer. Their revenue had grown from eighty two billion euros to ninety six billion, but operating profit had fallen from eleven billion down to five. I broke that into KPI components and used SQL group by and join queries along with pivot analysis to compare profitability across regions and product categories. The drivers turned out to be raw material inflation, logistics cost and discounting. I also built a driver drowsiness detection model on a sixty six thousand image dataset and reached about ninety one percent validation accuracy, where most of my effort went into reducing false negatives rather than chasing the headline number. On tools I use Excel, SQL, Python with Pandas and Scikit-learn, R, and Power BI. I have also mentored fifty plus students at an NGO, which is where I got most of my practice explaining things to people who do not share my background.$t$,
  $r$Priyanshu Singh. B.Tech Computer Engineering, Thapar Institute of Engineering and Technology, August 2023 to August 2027, CGPA 8.61.

PROJECTS
Bosch Profit Diagnostic. SQL, Excel, Power BI, Python (Pandas). August 2026. Diagnosed a profit paradox by analyzing why revenue increased from EUR 82B to EUR 96B while operating profit declined from EUR 11B to EUR 5B, using hypothesis-driven business analysis and KPI decomposition. Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories, identifying raw-material inflation, logistics costs and discounting as the primary drivers of margin erosion.

Driver Drowsiness Detection. Python, TensorFlow, Keras, NumPy, Scikit-learn. October 2025. Analyzed a 66K+ image dataset to evaluate model performance and validate prediction reliability, achieving 91.34% validation accuracy. Preprocessed and structured image data using OpenCV and NumPy, then benchmarked results across 4+ Scikit-learn evaluation metrics to assess model robustness and reduce false-negative risk.

PrepForge. React, Node, Express, MongoDB, Tailwind, JWT. April 2026. Full-stack placement preparation platform tracking 400+ DSA problems. Designed a responsive dashboard with 8+ reusable components, progress analytics and personalized learning insights.

EXPERIENCE
Epic Global Digital Solutions, Web Development Trainee, June 2026. Applied full-stack web development concepts using the MERN stack. Built 15+ REST API endpoints and 8+ UI components.

Josh Welfare Society (NGO), July 2025. Mentored 50+ students through subject teaching and personalized academic guidance. Conducted substance-abuse awareness campaigns across 5 government schools and participated in 5+ community outreach programs.

SKILLS
Analytics: MS Excel, SQL, Python (Pandas, NumPy, Scikit-learn), R, MATLAB.
Business tools: Power BI, MS Office, Git, GitHub.
Methods: Process improvement, root-cause analysis, forecasting, scenario and sensitivity analysis, stakeholder presentation.
Programming: JavaScript, React, Node, MongoDB, MySQL.$r$,
  61, 'borderline',
  $s$[
    {
      "criterion_id": "sql_and_data_extraction",
      "evidence": [
        {"source": "introduction", "quote": "used SQL group by and join queries along with pivot analysis to compare profitability across regions and product categories"}
      ],
      "points_awarded": 16,
      "points_possible": 25
    },
    {
      "criterion_id": "python_or_r_analysis",
      "evidence": [
        {"source": "resume", "quote": "benchmarked results across 4+ Scikit-learn evaluation metrics to assess model robustness and reduce false-negative risk"}
      ],
      "points_awarded": 13,
      "points_possible": 20
    },
    {
      "criterion_id": "business_intelligence_tooling",
      "evidence": [
        {"source": "resume", "quote": "Business tools: Power BI, MS Office, Git, GitHub"}
      ],
      "points_awarded": 10,
      "points_possible": 15
    },
    {
      "criterion_id": "analytical_problem_solving",
      "evidence": [
        {"source": "introduction", "quote": "I broke that into KPI components"},
        {"source": "resume", "quote": "identifying raw-material inflation, logistics costs and discounting as the primary drivers of margin erosion"}
      ],
      "points_awarded": 13,
      "points_possible": 20
    },
    {
      "criterion_id": "communication_and_storytelling",
      "evidence": [
        {"source": "introduction", "quote": "I got most of my practice explaining things to people who do not share my background"}
      ],
      "points_awarded": 9,
      "points_possible": 20
    }
  ]$s$::jsonb,
  array['SQL', 'Excel', 'Python', 'Power BI', 'Data visualization'],
  array['Business storytelling'],
  array[]::text[],
  $a$The profit diagnostic is the one piece of work that matches the rubric closely, and it carries evidence for three criteria at once: SQL with named constructs, KPI decomposition, and a stated conclusion about margin drivers. Outside it the evidence thins. Python analysis is evidenced on a model evaluation task rather than a business dataset. Dashboards and visualization is supported only by Power BI appearing in a skills list, with no dashboard, audience or metric named anywhere in either source. Structured problem solving is real but sits on a single project. Communication is claimed through mentoring 50+ students, which is a fair signal for explaining to a non-expert audience, but no instance of presenting an analysis appears. The pattern is one strong relevant project and limited evidence of repeating it.$a$,
  'review', 'screened',
  now() - interval '4 days'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Candidates: Business Analytics & Insights Intern
-- ---------------------------------------------------------------------
--
-- The same two people against a different rubric, which is the clearest
-- demonstration that the rubric is the contract: the transcripts and
-- resumes are identical, the criteria are not, and the scores move.

insert into candidates (
  id, job_id, name, email, transcript, resume_text,
  screening_score, screening_band, sub_scores,
  matched_skills, unevidenced_skills, resume_intro_conflicts,
  assessment, recommendation, state, created_at
) values (
  'bbbbbbb2-0000-4000-8000-000000000001',
  '22222222-2222-4222-8222-222222222222',
  'Vishard Mehta',
  'vishard2005@gmail.com',
  $t$Hi, I am Vishard Mehta, a final year Computer Science student at Thapar Institute, and most of my work is in business and quantitative analysis. The piece I am proudest of is an analysis of two hundred and forty billion dollars of US Medicare Part D drug spending across three and a half thousand products. I built a reconciled bridge that split the growth into price, volume and mix effects, and found that price rather than patient volume drove fifty nine percent of a seventy seven billion dollar increase. I then built a three scenario forecast that back tested to a one point seven percent error, and a priority scoring model whose top ten output matched three of the ten drugs the government actually selected for price negotiation. I have also spent six months as a quantitative analyst on a live forecasting tournament with my own capital staked, finishing in the top twelve percent globally, and I did a profit diagnostic on a large manufacturer using SQL and Power BI. Day to day I work in SQL, Python with Pandas, Excel and Power BI, and what I care about is getting from a messy dataset to a decision somebody can act on.$t$,
  $r$Vishard Mehta. B.Tech Computer Science and Engineering, Thapar Institute of Engineering and Technology, 2023 to 2027, CGPA 8.78.

EXPERIENCE
Raio Quantum, Summer Intern, June to August 2026. Developed an enterprise-grade relational schema for a multi-entity transactional system, optimizing query read paths with partial indexes. Built a ranked search and record-matching system using BM25 scoring, synonym expansion and Levenshtein fuzzy matching to resolve inconsistent free-text queries, validated by 27 automated tests.

Numerai, Quantitative Analyst (independent), January to June 2026. Forecast obfuscated financial time series for a live hedge fund tournament with personal capital staked on model performance, reaching a top 12% global rank on 60-day risk-adjusted contribution. Designed a regime-gated ensemble of specialist models using cross-validation to eliminate temporal leakage.

PROJECTS
Bosch Profit Diagnostic. SQL, Excel, Power BI, Python (Pandas). Diagnosed a profit paradox by analyzing why revenue increased while operating profit declined, using hypothesis-driven business analysis and KPI decomposition. Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories, identifying raw-material inflation, logistics costs and discounting as the primary drivers of margin erosion.

Medicare Part D Spending Analysis. Python (Pandas), Matplotlib, CMS public data. Analyzed $240bn of US Medicare Part D drug spending across 3,575 products from 2018 to 2022, building a reconciled bridge splitting growth into price, volume and mix effects. Produced a three-scenario forecast back-tested to a 1.7% error. Developed a priority-scoring model ranking drugs on spend, price-led growth and lack of generic competition.

Querix. Python, React, TypeScript, DuckDB, FastAPI. Analytics tool letting non-technical users query structured data in plain English, generating visualizations and written insights from CSV and Parquet sources.

SKILLS
Analytics: MS Excel, SQL, Python (Pandas, NumPy, Scikit-learn), R, MATLAB.
Tools and reporting: PowerPoint, Power BI, Matplotlib, GitHub.
Methods: Forecasting, scenario and sensitivity analysis, hypothesis testing, root-cause analysis.

ACHIEVEMENTS
2x Kaggle Expert, 17 public datasets, 14 medals, peak global rank 87.
Microsoft Learn Student Chapter, led technical execution for flagship events with 2000+ participants.
Amazon Machine Learning Summer School 2026.$r$,
  81, 'strong',
  $s$[
    {
      "criterion_id": "sql_and_large_datasets",
      "evidence": [
        {"source": "resume", "quote": "Analyzed $240bn of US Medicare Part D drug spending across 3,575 products from 2018 to 2022"},
        {"source": "resume", "quote": "Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories"}
      ],
      "points_awarded": 20,
      "points_possible": 25
    },
    {
      "criterion_id": "python_and_statistical_analysis",
      "evidence": [
        {"source": "introduction", "quote": "I then built a three scenario forecast that back tested to a one point seven percent error"},
        {"source": "resume", "quote": "Designed a regime-gated ensemble of specialist models using cross-validation to eliminate temporal leakage"}
      ],
      "points_awarded": 17,
      "points_possible": 20
    },
    {
      "criterion_id": "dashboarding_and_kpis",
      "evidence": [
        {"source": "introduction", "quote": "I did a profit diagnostic on a large manufacturer using SQL and Power BI"}
      ],
      "points_awarded": 11,
      "points_possible": 15
    },
    {
      "criterion_id": "structured_problem_solving",
      "evidence": [
        {"source": "introduction", "quote": "found that price rather than patient volume drove fifty nine percent of a seventy seven billion dollar increase"},
        {"source": "resume", "quote": "using hypothesis-driven business analysis and KPI decomposition"}
      ],
      "points_awarded": 18,
      "points_possible": 20
    },
    {
      "criterion_id": "insight_storytelling",
      "evidence": [
        {"source": "resume", "quote": "Developed a priority-scoring model ranking drugs on spend, price-led growth and lack of generic competition"},
        {"source": "introduction", "quote": "what I care about is getting from a messy dataset to a decision somebody can act on"}
      ],
      "points_awarded": 15,
      "points_possible": 20
    }
  ]$s$::jsonb,
  array['SQL', 'Python', 'Excel', 'Dashboards and KPI tracking', 'Forecasting', 'Stakeholder communication'],
  array['Tableau'],
  array[]::text[],
  $a$The Medicare Part D work maps almost directly onto this rubric. It is a large commercial dataset, the growth is decomposed into price, volume and mix, and the forecast is back-tested rather than presented unchecked, which covers SQL on large datasets, statistical analysis and hypothesis-driven problem solving. Healthcare claims and spend data is also the domain this role names as a plus. Dashboards and KPI tracking is the weakest criterion: Power BI is named but no dashboard, KPI choice or business consumer of it is described anywhere. Tableau does not appear in either source. Insight storytelling is evidenced through a priority-scoring model whose output was compared against a real policy decision, which is closer to a recommendation than a presentation.$a$,
  'shortlist', 'screened',
  now() - interval '3 days'
)
on conflict (id) do nothing;

insert into candidates (
  id, job_id, name, email, transcript, resume_text,
  screening_score, screening_band, sub_scores,
  matched_skills, unevidenced_skills, resume_intro_conflicts,
  assessment, recommendation, state, created_at
) values (
  'bbbbbbb2-0000-4000-8000-000000000002',
  '22222222-2222-4222-8222-222222222222',
  'Priyanshu Singh',
  'dispriyanshu47@gmail.com',
  $t$Hello, I am Priyanshu Singh, a final year Computer Engineering student at Thapar Institute with a CGPA of 8.61. The project I would point to first is a profit diagnostic on a large industrial manufacturer. Their revenue had grown from eighty two billion euros to ninety six billion, but operating profit had fallen from eleven billion down to five. I broke that into KPI components and used SQL group by and join queries along with pivot analysis to compare profitability across regions and product categories. The drivers turned out to be raw material inflation, logistics cost and discounting. I also built a driver drowsiness detection model on a sixty six thousand image dataset and reached about ninety one percent validation accuracy, where most of my effort went into reducing false negatives rather than chasing the headline number. On tools I use Excel, SQL, Python with Pandas and Scikit-learn, R, and Power BI. I have also mentored fifty plus students at an NGO, which is where I got most of my practice explaining things to people who do not share my background.$t$,
  $r$Priyanshu Singh. B.Tech Computer Engineering, Thapar Institute of Engineering and Technology, August 2023 to August 2027, CGPA 8.61.

PROJECTS
Bosch Profit Diagnostic. SQL, Excel, Power BI, Python (Pandas). August 2026. Diagnosed a profit paradox by analyzing why revenue increased from EUR 82B to EUR 96B while operating profit declined from EUR 11B to EUR 5B, using hypothesis-driven business analysis and KPI decomposition. Performed SQL (GROUP BY, JOIN) and pivot-based analysis to evaluate profitability across regions and product categories, identifying raw-material inflation, logistics costs and discounting as the primary drivers of margin erosion.

Driver Drowsiness Detection. Python, TensorFlow, Keras, NumPy, Scikit-learn. October 2025. Analyzed a 66K+ image dataset to evaluate model performance and validate prediction reliability, achieving 91.34% validation accuracy. Preprocessed and structured image data using OpenCV and NumPy, then benchmarked results across 4+ Scikit-learn evaluation metrics to assess model robustness and reduce false-negative risk.

PrepForge. React, Node, Express, MongoDB, Tailwind, JWT. April 2026. Full-stack placement preparation platform tracking 400+ DSA problems. Designed a responsive dashboard with 8+ reusable components, progress analytics and personalized learning insights.

EXPERIENCE
Epic Global Digital Solutions, Web Development Trainee, June 2026. Applied full-stack web development concepts using the MERN stack. Built 15+ REST API endpoints and 8+ UI components.

Josh Welfare Society (NGO), July 2025. Mentored 50+ students through subject teaching and personalized academic guidance. Conducted substance-abuse awareness campaigns across 5 government schools and participated in 5+ community outreach programs.

SKILLS
Analytics: MS Excel, SQL, Python (Pandas, NumPy, Scikit-learn), R, MATLAB.
Business tools: Power BI, MS Office, Git, GitHub.
Methods: Process improvement, root-cause analysis, forecasting, scenario and sensitivity analysis, stakeholder presentation.
Programming: JavaScript, React, Node, MongoDB, MySQL.$r$,
  58, 'borderline',
  $s$[
    {
      "criterion_id": "sql_and_large_datasets",
      "evidence": [
        {"source": "introduction", "quote": "used SQL group by and join queries along with pivot analysis to compare profitability across regions and product categories"}
      ],
      "points_awarded": 15,
      "points_possible": 25
    },
    {
      "criterion_id": "python_and_statistical_analysis",
      "evidence": [
        {"source": "resume", "quote": "benchmarked results across 4+ Scikit-learn evaluation metrics to assess model robustness and reduce false-negative risk"}
      ],
      "points_awarded": 12,
      "points_possible": 20
    },
    {
      "criterion_id": "dashboarding_and_kpis",
      "evidence": [
        {"source": "resume", "quote": "Designed a responsive dashboard with 8+ reusable components, progress analytics and personalized learning insights"}
      ],
      "points_awarded": 10,
      "points_possible": 15
    },
    {
      "criterion_id": "structured_problem_solving",
      "evidence": [
        {"source": "resume", "quote": "using hypothesis-driven business analysis and KPI decomposition"},
        {"source": "introduction", "quote": "The drivers turned out to be raw material inflation, logistics cost and discounting"}
      ],
      "points_awarded": 12,
      "points_possible": 20
    },
    {
      "criterion_id": "insight_storytelling",
      "evidence": [
        {"source": "introduction", "quote": "I got most of my practice explaining things to people who do not share my background"}
      ],
      "points_awarded": 9,
      "points_possible": 20
    }
  ]$s$::jsonb,
  array['SQL', 'Python', 'Excel', 'Dashboards and KPI tracking', 'Forecasting'],
  array['Tableau', 'Stakeholder communication'],
  array[]::text[],
  $a$Hypothesis-driven problem solving is evidenced once and evidenced properly: the profit diagnostic starts from a business question, decomposes the metric and names the drivers it landed on. The rest of the rubric is thinner against this role than against a general analyst role, because this one asks specifically about large and complex commercial datasets. The dataset described is a financial statement analysis rather than sales, claims or transaction data, and the 66K image dataset is large but not commercial. Dashboards and KPI tracking is evidenced by a dashboard inside a student project, where the KPIs are learning progress rather than business performance. Insight storytelling rests on mentoring rather than on any stakeholder-facing analysis. Forecasting appears in the skills list with no worked example. Worth a review conversation given one genuinely relevant project.$a$,
  'review', 'screened',
  now() - interval '2 days'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Interviews
-- ---------------------------------------------------------------------
--
-- Two, in different states, because Candidate Detail renders differently
-- for each (screens.md section 4):
--
--   Hitesh Yadav   approved, not started    the interview link is shown
--   Vishard Mehta  evaluated                the result link is shown
--
-- Tokens here are fixed so the seeded interview link is stable across
-- restarts. The real ones are secrets.token_urlsafe(32).

insert into interviews (id, candidate_id, token, plan, state_object, total_questions, status, created_at)
values (
  'cccccccc-0000-4000-8000-000000000002',
  'aaaaaaa1-0000-4000-8000-000000000002',
  'demo-hitesh-yadav-junior-business-analyst-01',
  null,
  '{}'::jsonb,
  null,
  'not_started',
  now() - interval '2 days'
)
on conflict (id) do nothing;

insert into interviews (
  id, candidate_id, token, plan, state_object,
  total_questions, status, started_at, completed_at, created_at
) values (
  'cccccccc-0000-4000-8000-000000000001',
  'aaaaaaa1-0000-4000-8000-000000000001',
  'demo-vishard-mehta-junior-business-analyst-01',
  $plan${
    "questions": [
      {"slot": 1, "intent": "Orient on background and what kind of analysis they actually do.", "criterion_ids": ["analytical_problem_solving"], "depth": "opening"},
      {"slot": 2, "intent": "Get them onto one concrete project so later slots have something to anchor to.", "criterion_ids": ["analytical_problem_solving"], "depth": "opening"},
      {"slot": 3, "intent": "Separate their own contribution from the project as a whole.", "criterion_ids": ["sql_and_data_extraction"], "depth": "opening"},
      {"slot": 4, "intent": "Press on the SQL and data preparation behind the headline result.", "criterion_ids": ["sql_and_data_extraction"], "depth": "probing"},
      {"slot": 5, "intent": "Probe the analysis method, since screening evidence was strong on outcome and thin on technique.", "criterion_ids": ["python_or_r_analysis"], "depth": "probing"},
      {"slot": 6, "intent": "Test dashboards and stakeholder communication together, the two thinnest criteria at screening.", "criterion_ids": ["business_intelligence_tooling", "communication_and_storytelling"], "depth": "deep"}
    ]
  }$plan$::jsonb,
  $state${
    "questions_asked": [
      {"slot": 1, "question": "To start, tell me about your background and the kind of analysis work you have been doing.", "criterion_ids": ["analytical_problem_solving"]},
      {"slot": 2, "question": "Pick one project from that and walk me through it. What was the question you were trying to answer?", "criterion_ids": ["analytical_problem_solving"]},
      {"slot": 3, "question": "On the Medicare analysis, what was your own contribution as opposed to the project overall?", "criterion_ids": ["sql_and_data_extraction"]},
      {"slot": 4, "question": "You said the bridge was reconciled. What did you have to fix in the CMS data before the price and volume split held together?", "criterion_ids": ["sql_and_data_extraction"]},
      {"slot": 5, "question": "How did you separate a price effect from a mix effect when a drug moved between spending tiers across years?", "criterion_ids": ["python_or_r_analysis"]},
      {"slot": 6, "question": "If a brand lead had ten minutes and no interest in your method, what would you put in front of them from this analysis?", "criterion_ids": ["business_intelligence_tooling", "communication_and_storytelling"]}
    ],
    "answers": [
      {"slot": 1, "transcript": "I am a final year computer science student and most of my work has been in business and quantitative analysis rather than in software.", "response_time_seconds": 41},
      {"slot": 2, "transcript": "The Medicare Part D one. The question was why US drug spending grew by seventy seven billion dollars over five years.", "response_time_seconds": 63},
      {"slot": 3, "transcript": "All of it. The data preparation, the bridge, the forecast and the priority model were mine.", "response_time_seconds": 52},
      {"slot": 4, "transcript": "The main problem was that drug identifiers are not stable across years, so a naive year on year join loses products.", "response_time_seconds": 88},
      {"slot": 5, "transcript": "I fixed the basket. Price effect is the change in unit cost holding the prior year quantity, mix is what is left after price and volume.", "response_time_seconds": 94},
      {"slot": 6, "transcript": "One chart and one sentence. Price drove fifty nine percent of the increase, and the ten drugs to watch are on the second slide.", "response_time_seconds": 57}
    ],
    "topics_discussed": [
      "business and quantitative analysis background",
      "Medicare Part D spending growth",
      "individual ownership of the analysis",
      "data reconciliation and identifier drift",
      "price volume mix decomposition",
      "communicating a finding to a brand lead"
    ],
    "claims_made": [
      "Analysed 240bn dollars of Medicare Part D spending across 3,575 products",
      "Built a reconciled bridge splitting growth into price, volume and mix",
      "Did the data preparation, bridge, forecast and priority model personally",
      "Drug identifiers are not stable year on year, so a naive join loses products",
      "Held the prior year quantity fixed to isolate the price effect",
      "Back-tested a three scenario forecast to a 1.7 percent error"
    ],
    "criteria_covered": [
      "analytical_problem_solving",
      "sql_and_data_extraction",
      "python_or_r_analysis",
      "business_intelligence_tooling",
      "communication_and_storytelling"
    ],
    "criteria_remaining": [],
    "depth_by_topic": {
      "Medicare Part D spending growth": 3,
      "data reconciliation and identifier drift": 2,
      "price volume mix decomposition": 2,
      "communicating a finding to a brand lead": 1
    }
  }$state$::jsonb,
  6,
  'evaluated',
  now() - interval '2 days' - interval '14 minutes',
  now() - interval '2 days',
  now() - interval '3 days'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Turns
-- ---------------------------------------------------------------------
--
-- Slots 1 to 3 are the fixed openers (backend.md 5.3). From slot 4 the
-- questions quote the candidate back to themselves, which is the whole
-- point of carrying the state object across turns (CLAUDE.md, "Interview
-- context is the product"). A demo transcript where the questions could
-- have been written in advance would show none of that.

insert into interview_turns (
  id, interview_id, slot, question, criterion_ids,
  answer_text, answer_scores, response_time_seconds, asked_at, answered_at
) values
(
  'dddddddd-0000-4000-8000-000000000001',
  'cccccccc-0000-4000-8000-000000000001',
  1,
  'To start, tell me about your background and the kind of analysis work you have been doing.',
  array['analytical_problem_solving'],
  $ans$I am a final year computer science student and most of my work has been in business and quantitative analysis rather than in software. Two things take up most of it. I spent six months forecasting financial time series for a live tournament with my own money staked on the results, which is a fast way to learn that a model you like is not the same as a model that works. And I have done a few analyses on public data where the point was to answer a business question rather than to get a good score, the largest being on US drug spending.$ans$,
  $sc$[{"criterion_id": "analytical_problem_solving", "evidence": "the point was to answer a business question rather than to get a good score", "points_awarded": 14, "points_possible": 20}]$sc$::jsonb,
  41,
  now() - interval '2 days' - interval '14 minutes',
  now() - interval '2 days' - interval '13 minutes'
),
(
  'dddddddd-0000-4000-8000-000000000002',
  'cccccccc-0000-4000-8000-000000000001',
  2,
  'Pick one project from that and walk me through it. What was the question you were trying to answer?',
  array['analytical_problem_solving'],
  $ans$The Medicare Part D one. The question was why US drug spending grew by seventy seven billion dollars over five years, because the public argument was that it was volume, more people on more drugs. I did not want to assume that. So I built a bridge that reconciled the total change and split it into three parts, price, volume and mix, across three and a half thousand products. Price came out at fifty nine percent of the increase. Volume was much smaller than the public framing suggested.$ans$,
  $sc$[{"criterion_id": "analytical_problem_solving", "evidence": "I built a bridge that reconciled the total change and split it into three parts, price, volume and mix", "points_awarded": 18, "points_possible": 20}]$sc$::jsonb,
  63,
  now() - interval '2 days' - interval '13 minutes',
  now() - interval '2 days' - interval '12 minutes'
),
(
  'dddddddd-0000-4000-8000-000000000003',
  'cccccccc-0000-4000-8000-000000000001',
  3,
  'On the Medicare analysis, what was your own contribution as opposed to the project overall?',
  array['sql_and_data_extraction'],
  $ans$All of it, it was solo. The data preparation, the bridge, the forecast and the priority model were mine. The part that took longest was not the analysis, it was getting the source data into a state where the bridge reconciled to the published totals. I would say seventy percent of the time was cleaning and joining, and the actual decomposition was a couple of days.$ans$,
  $sc$[{"criterion_id": "sql_and_data_extraction", "evidence": "seventy percent of the time was cleaning and joining", "points_awarded": 15, "points_possible": 25}]$sc$::jsonb,
  52,
  now() - interval '2 days' - interval '12 minutes',
  now() - interval '2 days' - interval '11 minutes'
),
(
  'dddddddd-0000-4000-8000-000000000004',
  'cccccccc-0000-4000-8000-000000000001',
  4,
  'You said the bridge was reconciled. What did you have to fix in the CMS data before the price and volume split held together?',
  array['sql_and_data_extraction'],
  $ans$Three things. Drug identifiers are not stable across years, brand and generic entries get renamed and split, so a naive year on year join silently loses products and the totals stop tying out. I matched on a normalised name and manufacturer instead and checked the unmatched set by hand. Second, the spend and claim counts are suppressed below a threshold for privacy, so some rows have a value and no denominator. I kept those out of the rate calculation but inside the total, otherwise the bridge does not reconcile. Third, units are inconsistent, some products are per dose and some per package, which makes unit cost meaningless if you average across them.$ans$,
  $sc$[{"criterion_id": "sql_and_data_extraction", "evidence": "a naive year on year join silently loses products and the totals stop tying out", "points_awarded": 22, "points_possible": 25}]$sc$::jsonb,
  88,
  now() - interval '2 days' - interval '11 minutes',
  now() - interval '2 days' - interval '9 minutes'
),
(
  'dddddddd-0000-4000-8000-000000000005',
  'cccccccc-0000-4000-8000-000000000001',
  5,
  'How did you separate a price effect from a mix effect when a drug moved between spending tiers across years?',
  array['python_or_r_analysis'],
  $ans$I fixed the basket. Price effect is the change in unit cost holding the prior year quantity constant, volume is the change in quantity holding the prior year price constant, and mix is the residual, which is where the tier movement lands. That way the three parts add back to the actual total by construction and I am not deciding case by case which bucket something belongs in. The residual being small was the check. If mix had come out large I would have assumed I had a data problem rather than a finding, because a large unexplained residual usually means the join is wrong.$ans$,
  $sc$[{"criterion_id": "python_or_r_analysis", "evidence": "If mix had come out large I would have assumed I had a data problem rather than a finding", "points_awarded": 17, "points_possible": 20}]$sc$::jsonb,
  94,
  now() - interval '2 days' - interval '9 minutes',
  now() - interval '2 days' - interval '7 minutes'
),
(
  'dddddddd-0000-4000-8000-000000000006',
  'cccccccc-0000-4000-8000-000000000001',
  6,
  'If a brand lead had ten minutes and no interest in your method, what would you put in front of them from this analysis?',
  array['business_intelligence_tooling', 'communication_and_storytelling'],
  $ans$One chart and one sentence. The chart is the bridge, four bars, start, price, volume, mix, end, because it shows the whole argument at once and you can see that the price bar is most of the gap. The sentence is that price drove fifty nine percent of the increase, so a volume-led response is aimed at the wrong thing. Then I would keep the ten drugs to watch on the next slide, ranked, with the reason each one is on the list. The method goes in an appendix and I would only open it if someone pushed on the number. I have not built a live dashboard for this, it was a static deck, so if the ask were ongoing tracking I would need to rebuild it in Power BI.$ans$,
  $sc$[{"criterion_id": "business_intelligence_tooling", "evidence": "I have not built a live dashboard for this, it was a static deck", "points_awarded": 9, "points_possible": 15}, {"criterion_id": "communication_and_storytelling", "evidence": "price drove fifty nine percent of the increase, so a volume-led response is aimed at the wrong thing", "points_awarded": 16, "points_possible": 20}]$sc$::jsonb,
  57,
  now() - interval '2 days' - interval '7 minutes',
  now() - interval '2 days' - interval '6 minutes'
)
on conflict do nothing;

-- ---------------------------------------------------------------------
-- Result
-- ---------------------------------------------------------------------
--
-- The dimension scores are the accumulated turn scores by dimension, and
-- overall is the weighted average from app/core/heuristics.py:
-- 0.5 technical + 0.25 communication + 0.25 experience. Here that is
-- 0.5(82) + 0.25(76) + 0.25(78) = 79.5, so 80 is inside the 2 point
-- tolerance the validator allows. Seed data that ignored the weights
-- would look fine on screen and fail the moment anyone recomputed it.

insert into interview_results (
  interview_id, overall_score, technical_score, communication_score,
  experience_score, band, strengths, concerns, recommendation, created_at
) values (
  'cccccccc-0000-4000-8000-000000000001',
  80, 82, 76, 78, 'strong',
  array[
    'Named three specific defects in the source data unprompted, including that unstable drug identifiers make a naive year on year join lose products silently, which is the kind of failure that produces a confident wrong answer.',
    'Chose a fixed-basket decomposition so that price, volume and mix add back to the actual total by construction, and explained why that was preferable to classifying movements case by case.',
    'Treated a large residual as evidence of a data problem rather than a finding, which is a real check rather than a stated intention to be careful.',
    'Led with the decision rather than the method when asked how to present to a brand lead, and put the argument in one chart and one sentence.'
  ],
  array[
    'Volunteered that no live dashboard was built and that ongoing tracking would need rebuilding in Power BI, so dashboard work remains unevidenced in both the screening sources and the interview.',
    'All of the strongest evidence comes from a single solo project. Nothing in the interview showed the same analysis under a deadline, a changing brief, or disagreement from a stakeholder.',
    'SQL was described in terms of what was cleaned and joined rather than how. No query construct, schema decision or performance consideration was named.'
  ],
  'shortlist',
  now() - interval '2 days'
)
on conflict (interview_id) do nothing;
