import time
import os

from app import create_app

app = create_app()
scheduler = app.scheduler

if __name__ == "__main__":
    typer = None
    print("Worker started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("Stopped.")
