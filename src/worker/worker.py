import time

def run_worker():
    while True:
        print("Worker is running...")
        time.sleep(5) 

if __name__ == "__main__":
    run_worker()