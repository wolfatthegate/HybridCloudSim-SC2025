# hybridcloud.py

class HybridCloud:
    def __init__(self, env, qpu_devices, cpu_devices, job_records_manager=None, printlog=True):
        self.env = env
        self.qpus = qpu_devices
        self.cpus = cpu_devices
        self.job_records = {}  # Dictionary to track job lifecycle events
        self.job_records_manager = job_records_manager

    def log_job_event(self, job_id, event_type, timestamp):
        """
        Logs a job event with a timestamp.

        Parameters:
        - job_id: The ID of the job.
        - event_type: The type of event ('arrival', 'start', or 'finish').
        """
        if job_id not in self.job_records:
            self.job_records[job_id] = {}
        self.job_records[job_id][event_type] = timestamp        

    def get_event_logger(self):
        """
        Returns a callback function for logging job events.
        """
        return self.log_job_event
    
    def submit_job(self, job):
        job.phase = "quantum"
        job.iteration = 0
        self.env.process(self.execute(job))
