# AI prompts and correction log

The following material is included in the report annex in condensed form.

## Prompt 1 - architecture

**Prompt:** Design a complete Python simulation of an automated pencil production line for an Advanced Programming project. It must include at least four assembly stages, product defects with explicit reasons, Start/Stop/Reset controls, an HMI, InfluxDB, Grafana, Docker, automated tests, and clear separation between product defects and machine faults.

**Output used:** A proposed state-machine architecture, six production stages, REST-like JSON endpoints, asynchronous telemetry writing, and a Docker Compose service layout.

**Review and correction:** The first design used a third-party web framework, which added an unnecessary dependency. It was replaced with Python's standard-library `ThreadingHTTPServer` so the simulation can run without package installation. The database writer was also moved to a background queue so an unavailable database cannot stop the production line.

## Prompt 2 - quality logic

**Prompt:** Generate realistic quality-control rules for a pencil line, including measurements and defect reasons for body feeding, graphite insertion, ferrule pressing, eraser insertion, and final inspection.

**Output used:** Measurements for body length, graphite offset, ferrule force, eraser depth, final length, and surface score; product defect categories; and accept/reject sorting.

**Review and correction:** An initial approach applied the full configured defect probability at every stage, which made the final defect rate much higher than the HMI setting. It was corrected by converting the final-product probability into an equivalent per-stage probability: `1 - (1 - p)^(1/5)`.

## Prompt 3 - HMI and database

**Prompt:** Create an industrial browser HMI with Start, Stop, Reset, Acknowledge, Emergency Stop, live process stages, production statistics, fault display, event log, recent product table, and settings. Add InfluxDB line-protocol fields and a provisioned Grafana dashboard.

**Output used:** HTML/CSS/JavaScript HMI, HTTP API calls, InfluxDB measurements, Grafana data-source YAML, and dashboard JSON.

**Review and correction:** The HMI was tested against the live API. HTML escaping was added to data inserted into the product table and event log. InfluxDB communication was given timeouts, a bounded queue, health checks, and one retry to avoid blocking the simulation.

## Prompt 4 - testing and documentation

**Prompt:** Write automated tests and a submission-ready report explaining the product, implementation, tools, weaknesses, AI use, and future improvements.

**Output used:** Unit and API tests, documentation structure, deployment instructions, website content, and report draft.

**Review and correction:** All tests were executed locally. The report was rendered to PDF and every page was visually reviewed. The documentation clearly states that the software is an educational simulation and that the standard-library HTTP server would need replacement and security hardening for real industrial deployment.

## Benefits of the AI tool

ChatGPT accelerated brainstorming, code scaffolding, test-case design, documentation organization, and consistency checking across the Python, JavaScript, Docker, InfluxDB, Grafana, website, and report files. Human review remained necessary to validate probabilities, concurrency, error handling, security limitations, deployment assumptions, and visual layout.
