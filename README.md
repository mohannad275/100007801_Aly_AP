# Automated Pencil Production Line

**Student:** Mohannad Aly  
**Student ID:** 100007801  
**Course:** Advanced Programming, Applied Mechatronics  
**Instructor:** Esteban Pozo  
**Submission title:** `100007801_Aly_AP`

This repository contains a complete simulation of a six-stage pencil manufacturing line. It includes a dependency-free Python backend, browser-based HMI, product quality control, machine faults, InfluxDB time-series storage, a pre-provisioned Grafana dashboard, Docker Compose deployment, automated tests, a GitHub Pages website, and the final project report.

## Production stages

1. Wooden body feed
2. Graphite core insertion
3. Ferrule installation
4. Eraser insertion
5. Final quality inspection
6. Accept/reject sorting

A product can be rejected for a cracked or missing body, broken or misaligned graphite, low ferrule force, missing or incorrectly inserted eraser, incorrect final length, or a visual surface defect. Machine faults are separate from product defects and include conveyor jams, sensor timeouts, safety-interlock openings, and motor overtemperature.

## Quick start with Docker

1. Install Docker Desktop.
2. Open a terminal in this folder.
3. Start the complete stack:

```bash
docker compose up --build
```

Open:

- HMI: `http://localhost:8000`
- Grafana: `http://localhost:3000`
- InfluxDB: `http://localhost:8086`

Default Grafana login: `admin` / `PencilGrafana2026!`  
Default InfluxDB login: `admin` / `PencilLine2026!`

Stop the stack with:

```bash
docker compose down
```

To delete stored data and start clean:

```bash
docker compose down -v
```

## Local preview without Docker

The HMI can run without InfluxDB for a quick demonstration:

```bash
# macOS or Linux
INFLUXDB_ENABLED=false python app.py

# Windows PowerShell
$env:INFLUXDB_ENABLED="false"; python app.py
```

Then open `http://localhost:8000`. The HMI will show that database telemetry is offline, but all controls and production logic remain available.

## Tests

No external test package is required:

```bash
python run_tests.py
```

The test suite checks production, stopping and resetting, emergency-stop acknowledgement, settings validation, injected faults, JSON API responses, and HMI static-file serving.

## Project structure

```text
app.py                           Application entry point
production_line/                 State machine, HTTP API, InfluxDB writer
static/                          Live browser HMI
website/                         Static GitHub Pages project website
grafana/                         Data-source and dashboard provisioning
tests/                           Automated unit and API tests
docker-compose.yml               App + InfluxDB + Grafana stack
Dockerfile                       Container image for the Python HMI
100007801_Aly_AP.pdf             Final report
100007801_Aly_AP.docx            Editable report
```

## Website deployment

The repository contains `.github/workflows/pages.yml`. Create a GitHub repository named `100007801_Aly_AP`, push this project to the `main` branch, then select **Settings → Pages → Source: GitHub Actions**. The expected site address is:

`https://mohannad275.github.io/100007801_Aly_AP/`

## AI disclosure

ChatGPT was used to help plan, generate, review, and test parts of the source code and documentation. The report appendix contains the relevant prompts, outputs, detected errors, corrections, and benefits, as required by the assignment.
