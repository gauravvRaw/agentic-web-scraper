A demo of what the tool would like.

Currently, it consists of a streamlit frontend that takes an query, after which an LLM (GPT-4o-mini via OpenRouter) decides on what field to extract, instructs
that to the scraper. The results are then presented by the LLM in plain English as well as in the dashboard tab.

So it works scraps through only one source as of now, but can be scaled by adding a worker for each scraping job, while the scraper itself can be turned into a
content-agnostic interface and the agent can do the heavylifting on creating the model for the site.
