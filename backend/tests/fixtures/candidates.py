"""Candidate fixtures for screening tests and the consistency harness.

Written by hand so the tests measure the scorer, not whatever a model
happened to produce that day. The golden candidate is deliberately mixed:
strong on Python and SQL, thin on system design, with one factual
disagreement between the resume and the introduction. A candidate who is
uniformly excellent or uniformly poor would not exercise the interesting
paths.
"""

from __future__ import annotations

GOLDEN_TRANSCRIPT = """\
Hi, I'm Priya Nair. I've been a backend engineer for about five years now, \
mostly working in Python. For the last three years I was at Zoho building \
internal Django services, and before that I was at a smaller startup doing \
a mix of Flask and data work.

The thing I'm proudest of is a recommendation system we built for the \
internal marketplace. We started with straightforward collaborative \
filtering on purchase history. The hard part was the cold start problem, \
because most of our catalogue turned over every quarter, so a lot of items \
had no interaction data at all. We ended up falling back to a popularity \
model weighted by category for anything with fewer than fifty interactions, \
and blended the two scores with a weight that shifted as data came in. That \
took the click-through rate on new items from roughly two percent to about \
nine percent.

On the database side I've done a lot of PostgreSQL work. I spent a while \
tracking down a slow dashboard query that was doing a sequential scan over \
about forty million rows, and adding a composite index on the tenant and \
created_at columns took it from eleven seconds down to under two hundred \
milliseconds. I've also done schema design for multi tenant systems and \
handled a few tricky migrations where we had to backfill without locking \
the table.

I write tests, mostly pytest, and I care about them. I'm less experienced \
with large scale distributed system design, honestly. I've read a fair \
amount about it but I haven't personally designed anything that needed to \
handle serious scale across multiple services.

I like explaining technical work to people who aren't engineers. At Zoho I \
was often the person who'd sit with the support team and walk them through \
what had actually gone wrong in an incident.\
"""

GOLDEN_RESUME = """\
Priya Nair
priya.nair@example.com

EXPERIENCE

Backend Engineer, Zoho
2023 to present
Built and maintained internal Django services for the marketplace team.
Designed and shipped a recommendation service handling 40 million rows of
interaction data. Owned PostgreSQL schema design and query performance for
the team. Mentored two junior engineers through their first six months.

Software Engineer, Kaleido Systems
2021 to 2023
Flask APIs and data pipeline work. Built ETL jobs in Python and wrote the
reporting layer used by the operations team.

SKILLS
Python, Django, Flask, PostgreSQL, REST APIs, pytest, Docker, Redis

EDUCATION
B.Tech Computer Science, 2021\
"""

# The resume says 2023 to present, which is roughly two years at Zoho. The
# introduction says three. A correct screening records that as a neutral
# difference and does not dock points for it.
EXPECTED_CONFLICT_TOPIC = "zoho"

GOLDEN_SKILLS = [
    "Python",
    "Django",
    "PostgreSQL",
    "REST APIs",
    "Docker",
    "Kubernetes",
]
