# job.py

class Job:
    def __init__(self, job_id, arrival_time, priority):
        self.job_id = job_id
        self.arrival_time = arrival_time
        self.priority = priority
        self.start_time = None
        self.end_time = None

    def __repr__(self):
        return (f"Job(job_id={self.job_id}, "
                f"arrival_time={self.arrival_time:.2f}, "
                f"priority={self.priority})")