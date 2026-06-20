# Demonstration procedure

## Before the presentation

1. Install and open Docker Desktop.
2. Extract the project folder.
3. Run `docker compose up --build` from the project root.
4. Wait until the terminal shows that `pencil-hmi`, `pencil-influxdb`, and `pencil-grafana` are running.
5. Open the HMI at `http://localhost:8000`.
6. Open Grafana at `http://localhost:3000` and log in with `admin` / `PencilGrafana2026!`.
7. Open **Dashboards → SRH Project → Automated Pencil Production Line**.

## Recommended live demonstration

1. Press **Start** and show the six production stages.
2. Wait for several products and explain good/rejected counters.
3. Increase defect probability to 25% and press **Apply settings**.
4. Show a rejected product and its exact reason in Quality Control and Operator Log.
5. Open Grafana and show total count, temperature, state, yield, and cycle time.
6. Return to the HMI and press **Test fault**.
7. Explain the FAULT state, alarm banner, and blocked restart.
8. Press **Acknowledge**, then **Start**.
9. Demonstrate **Emergency Stop**, acknowledge it, and restart.
10. Press **Stop**, then **Reset**.

## Troubleshooting

- Check service status: `docker compose ps`
- View logs: `docker compose logs -f`
- Rebuild after changes: `docker compose up --build`
- Completely reset databases: `docker compose down -v`
- If ports are occupied, stop other programs using ports 8000, 8086, or 3000.
