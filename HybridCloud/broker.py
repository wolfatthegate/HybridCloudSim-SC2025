# broker.py

from HybridCloud.dependencies import *
from abc import ABC, abstractmethod

class BaseBroker(ABC):
    def __init__(self, env, job, devices, job_records_manager):
        """
        Base class for all brokers.
        """
        self.env = env
        self.job = job
        self.devices = devices
        self.job_records_manager = job_records_manager

    @abstractmethod
    def assign_device(self):
        """
        Assign a job to an appropriate quantum device.
        """
        pass

    @abstractmethod
    def run(self):
        """
        Run the broker's main functionality for job processing.
        """
        pass
    
    
class SerialBroker(BaseBroker):
    def __init__(self, env, job, devices, job_records_manager, qcloud, printlog=False):
        super().__init__(env, job, devices, job_records_manager)
        """
        Initialize the ParallelBroker.

        Parameters:
        - env: SimPy environment.
        - job_id: ID of the job being handled.
        - job: The QJob object representing the job.
        - devices: List of quantum devices.
        - log_event_callback: Callback function for logging job events.
        - qcloud: Reference to the QCloud instance for job allocation.
        """
        self.qcloud = qcloud
        self.log_event = (job_records_manager.log_job_event
                          if hasattr(job_records_manager, "log_job_event") else None)
        self.printlog = printlog
        
    def assign_device(self):
        """
        Assign a job to a random available device.
        """
        device = random.choice(self.devices)
        while device.maint_lock:
            print(f'{self.env.now:.2f}: Job {self.job.job_id} waiting. {device.name} under maintenance...')
            yield self.env.timeout(1)
        return device

    def run(self):
        """
        Assign a device and process the job.
        """
        device = yield from self.assign_device()

        # Process the job
        with device.resource.request(priority=2) as req:
            yield req
            yield from device.process_job(self.job, self.env.now)

            
# Parallel Broker

class ParallelBroker(BaseBroker):
    def __init__(self, env, job, devices, job_records_manager, qcloud, printlog=False):
        super().__init__(env, job, devices, job_records_manager)
        self.qcloud = qcloud
        self.log_event = (job_records_manager.log_job_event
                          if hasattr(job_records_manager, "log_job_event") else None)
        self.printlog = printlog
         
    # implement abstract method
    def assign_device(self, *args, **kwargs):
        device_type = kwargs.get("device_type")
        needed = kwargs.get("needed", 1)
        return self._pick_device_by_capacity(device_type, needed)
    
    def _phase_start(self, job, phase, device):
        job.phase = phase
        if self.log_event:
            self.log_event(job.job_id, f"{phase.lower()}_start", round(self.env.now, 4))
        # print(f"{self.env.now:.2f}: Job {job.job_id} PHASE START: {phase} on {device.name}")

    def _phase_end(self, job, phase, device):
        if self.log_event:
            self.log_event(job.job_id, f"{phase.lower()}_finish", round(self.env.now, 4))
        # print(f"{self.env.now:.2f}: Job {job.job_id} PHASE END:   {phase} on {device.name}")

    def _required_units(self, phase, job):
        if phase == "QPU":
            return max(1, getattr(job, "num_qubits", 1))
        # CPU requires a tuple (cpu_units, mem_bw)
        return self._cpu_needs(job)

    def _fits_physical(self, device, job):
        req = getattr(job, "num_qubits", 1)
        return hasattr(device, "number_of_qubits") and device.number_of_qubits >= req

    
    def _cpu_needs(self, job):
        cpu_units = int(getattr(job, "cpu_units", 8))
        mem_bw    = int(getattr(job, "mem_bw", 20))
        return cpu_units, mem_bw
    
    def _pick_device_by_capacity(self, device_type, needed):
        """
        For QPU: 'needed' is qubits.
        For CPU: 'needed' is a tuple (cpu_units, mem_bw).
        """
        if device_type == "CPU":
            need_cpu, need_bw = needed
            candidates = [
                d for d in self.devices
                if getattr(d, "type", None) == "CPU"
                and not getattr(d, "maint_lock", False)
                and getattr(getattr(d, "container", None), "level", 0) >= need_cpu
                and getattr(getattr(d, "mem_bw",    None), "level", 0) >= need_bw
            ]
        else:
            # QPU path unchanged, but keep your _fits_physical check
            candidates = [
                d for d in self.devices
                if getattr(d, "type", None) == "QPU"
                and not getattr(d, "maint_lock", False)
                and getattr(getattr(d, "container", None), "level", 0) >= needed
                and self._fits_physical(d, self.job)
            ]

        if candidates:
            # choose the most free device to reduce blocking
            if device_type == "CPU":
                candidates.sort(key=lambda d: (d.container.level, d.mem_bw.level), reverse=True)
            else:
                candidates.sort(key=lambda d: d.container.level, reverse=True)
            return candidates[0]
        return None

    def _record_phase_metrics(self, job, phase, iter_idx):
        # pull stamps
        recs = getattr(self.job_records_manager, "records", {})
        row = recs.get(job.job_id, {})
        start_key  = f"{phase}_start"
        finish_key = f"{phase}_finish"
        arrive_key = f"{phase}_arrive"

        t_arr = row.get(arrive_key)
        t_s   = row.get(start_key)
        t_f   = row.get(finish_key)

        # sanity guard
        if t_arr is None or t_s is None or t_f is None:
            if self.printlog:
                print(f"{self.env.now:.2f}: WARN: missing stamps for Job {job.job_id} {phase} (arr={t_arr}, start={t_s}, fin={t_f})")
            return

        wait = round(t_s - t_arr, 4)
        svc  = round(t_f - t_s, 4)
        turn = round(t_f - t_arr, 4)

        # store with iteration-aware keys
        self.job_records_manager.log_job_event(job.job_id, f"{phase}_wait_{iter_idx}", wait)
        self.job_records_manager.log_job_event(job.job_id, f"{phase}_svc_{iter_idx}", svc)
        self.job_records_manager.log_job_event(job.job_id, f"{phase}_turn_{iter_idx}", turn)

        print(f"{self.env.now:.2f}: Job {job.job_id} {phase.upper()} metrics (iter {iter_idx}): "
              f"wait={wait}, svc={svc}, turn={turn}")

    def _rec(self, job_id):
        """
        Shorthand to access a job's record dict safely.
        """
        return getattr(self.job_records_manager, "records", {}).get(job_id, {})

    def run(self):
        job = self.job
        if not hasattr(job, "iteration"):
            job.iteration = 0
        if not hasattr(job, "iterations"):
            job.iterations = 1

        while job.iteration < job.iterations:
            # ---------- QPU phase ----------
            q_needed = self._required_units("QPU", job)
            qpu = None
            while qpu is None:
                qpu = self._pick_device_by_capacity("QPU", q_needed)
                if qpu is None:
                    yield self.env.timeout(0.5)  # wait for capacity to free up

            self._phase_start(job, "QPU", qpu)

            # Reserve qubits (this is the concurrency gate)
 
            qpu_qubits = getattr(job, "num_qubits", 1)
            if self.printlog:
                print(f"{self.env.now:.2f}: Job {job.job_id} requires {qpu_qubits} qubits; "
      f"{qpu.name} has {qpu.container.level}/{qpu.number_of_qubits} free")
            if self.printlog:               
                print(f"{self.env.now:.2f}: Job {job.job_id} processing on qpu")
            yield from qpu.process_job(job, self.env.now)
            
            if self.printlog:
                print(f"{self.env.now:.2f}: Job {job.job_id} finished processing on qpu")
                
            self._phase_end(job, "QPU", qpu)
            self._record_phase_metrics(job, "qpu", job.iteration)

            # ---------- CPU phase ----------
            c_needed = self._required_units("CPU", job)   # (cpu_units, mem_bw)
            cpu = None
            while cpu is None:
                cpu = self._pick_device_by_capacity("CPU", c_needed)
                if cpu is None:
                    yield self.env.timeout(0.5)

            self._phase_start(job, "CPU", cpu)
            # print(f"{self.env.now:.2f}: Job {job.job_id} processing on cpu")
            yield from cpu.process_job(job, self.env.now)
            # print(f"{self.env.now:.2f}: Job {job.job_id} back in broker now.")
            self._phase_end(job, "CPU", cpu)
            self._record_phase_metrics(job, "cpu", job.iteration)
            
            job.iteration += 1
            
            if self.printlog:
                print(f"{self.env.now:.2f}: Job {job.job_id} ITERATION {job.iteration}/{job.iterations} complete")
            
            if job.iteration >= job.iterations:
                row = self._rec(job.job_id)
                t0 = row.get("arrival", row.get("qpu_arrive"))
                tf = row.get("cpu_finish")
                if t0 is not None and tf is not None:
                    makespan = round(tf - t0, 4)
                    self.job_records_manager.log_job_event(job.job_id, "makespan", makespan)
                    if self.printlog:
                        print(f"{self.env.now:.2f}: Job {job.job_id} MAKESPAN={makespan}")